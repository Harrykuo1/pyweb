"""Stress-test seed for pyweb.

Populates a target SQLite database with a configurable number of fake
members and jobs so list / search / detail endpoints can be soak-tested
under realistic volume. Members get a markdown resume, a real JPEG
photo (Pillow), and a real 1-page PDF (reportlab); jobs get a markdown
experience body and a structured timeline_events JSON list.

Usage from the backend/ directory:

    .venv/bin/python -m scripts.stress_seed                     # 1000 + 1000
    .venv/bin/python -m scripts.stress_seed --members 10000     # any N
    .venv/bin/python -m scripts.stress_seed --reset             # wipe + reseed

This file is intentionally NOT part of the docker image (the Dockerfile
only copies app/, not scripts/) so seeding is purely a host-side dev
tool that points at the same SQLite file the container bind-mounts. It
is safe to run while the container is up — SQLite WAL handles the
concurrency — but live HTTP traffic will pause briefly while the script
holds writes.

Dependencies are dev-only — install once with:

    .venv/bin/pip install -r requirements-dev.txt

This pulls in Pillow + reportlab which are NOT in the production
requirements.txt (and therefore not in the docker image).

Notes:
  - Photos are real JPEGs (~30-50 KB each), color-rotated by index so
    every member's photo is visually distinct. The bottom-right of
    each photo carries a "M-NNNN" tag identifying the member index.
  - PDFs are real, viewable 1-page resumes (~3-6 KB each). They use
    reportlab's built-in CJK font (STSong-Light) so Chinese names /
    institutions render correctly.
  - Every Nth member resume / job experience embeds a known token like
    [STRESS_NEEDLE_M_<idx>] / [STRESS_NEEDLE_J_<idx>] so search
    throughput tests can verify hit counts (default N = 50, so 1000
    members yields 20 needles).
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Make `from app.* import ...` work when run as `python -m scripts.stress_seed`
# from the backend/ directory.
_HERE = Path(__file__).resolve().parent
_BACKEND_ROOT = _HERE.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# Default target: ../data/pyweb.db relative to backend/, which is the
# host side of the docker bind-mount.
DEFAULT_DB_URL = f"sqlite:///{_BACKEND_ROOT.parent}/data/pyweb.db"

# ----- Fake data pools -----

SURNAMES = [
    "王", "李", "張", "劉", "陳", "楊", "黃", "趙", "吳", "周",
    "林", "蔡", "鄭", "許", "謝", "洪", "郭", "曾", "邱", "廖",
]

GIVEN = [
    "志明", "雅婷", "建宏", "怡君", "家豪", "美玲", "俊傑", "淑芬",
    "宗翰", "佳蓉", "彥廷", "詩涵", "柏翰", "怡萱", "冠霖", "于婷",
    "宇軒", "雅雯", "承翰", "曉雯", "宏文", "宛庭", "勝偉", "麗華",
]

INSTITUTIONS = [
    "國立臺灣大學", "國立清華大學", "國立交通大學", "國立成功大學",
    "國立中央大學", "國立中山大學", "國立政治大學", "國立陽明交通大學",
    "國立臺灣科技大學", "國立中興大學", "輔仁大學", "東吳大學",
    "淡江大學", "逢甲大學", "中原大學", "元智大學",
]

POSITIONS = [
    "資訊工程學系", "電機工程學系", "資訊管理學系", "資料科學與工程研究所",
    "電子工程研究所", "資訊工程研究所", "通訊工程研究所", "工業工程學系",
    "機械工程學系", "化學工程學系", "生物醫學工程學系", "統計學系",
]

COMPANIES = [
    "台積電", "聯發科", "鴻海", "和碩", "華碩", "宏碁", "聯電", "日月光",
    "Google", "Microsoft", "Meta", "Amazon", "Apple", "Netflix", "Stripe",
    "Shopify", "Cloudflare", "GitLab", "Notion", "Linear", "Vercel",
    "趨勢科技", "聯詠", "瑞昱", "聯發創新", "群聯",
]

CATEGORIES = [
    "軟體", "硬體", "資料", "PM", "韌體", "演算法", "前端", "後端",
    "Cloud", "DevOps", "QA", "資安",
]

TIMELINE_VOCAB = [
    "投遞履歷", "完成 OA", "電話面試", "技術面試一", "技術面試二",
    "主管面試", "HR 面試", "OnSite", "白板題", "System Design",
    "拿到 Offer", "回 Offer", "簽約",
]

LOREM_PARAGRAPHS = [
    "我在大學期間主要研究方向為機器學習與系統最佳化，參與過實驗室與多家業界合作的專案。",
    "實習期間負責後端 API 服務的設計與實作，導入容器化部署並建立基礎的 CI/CD pipeline。",
    "面試準備上以 LeetCode 為主，每週固定刷 3-5 題，重點在於能說清楚解題思路而不只是寫出答案。",
    "技術面 OA 多半圍繞演算法與資料結構基礎題，建議加強動態規劃與圖論相關題型。",
    "主管面除了問過去經驗外，也會問為什麼選擇這間公司、未來規劃，建議事先寫好故事線。",
    "我在準備過程中讀了《Cracking the Coding Interview》與《System Design Interview》兩本書。",
    "OnSite 當天有四輪面試，每輪 45 分鐘，題目橫跨演算法、系統設計、行為面試與專案討論。",
    "建議在面試前一週開始模擬面試，請朋友或學長姐當 interviewer，能有效降低當日緊張感。",
]


# ----- BLOB generators (lazy-import dev deps so module import doesn't
#       break when Pillow / reportlab are missing) -----


# Common system paths for CJK fonts. TTC files are font collections;
# subfontIndex=0 picks the first face, which is good enough for our
# label-and-paragraph PDF — we don't need bold variants.
_CJK_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/wqy-microhei/wqy-microhei.ttc",
    "/usr/share/fonts/wqy-zenhei/wqy-zenhei.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Songti.ttc",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simsun.ttc",
)

_CJK_FONT_NAME: str | None = None


def _ensure_cjk_pdf_font() -> str:
    """Register a CJK-capable font for reportlab, return its name.

    Prefers embedding a real TTF / TTC (so PDFs display Chinese on any
    viewer regardless of system fonts); falls back to reportlab's
    built-in STSong-Light CIDFont reference if no system CJK font is
    present. The CID fallback works in Chrome / Firefox / Adobe Reader
    via their bundled fonts but renders as blank glyphs in some
    minimal previewers.
    """
    global _CJK_FONT_NAME
    if _CJK_FONT_NAME:
        return _CJK_FONT_NAME

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    for path in _CJK_FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            pdfmetrics.registerFont(TTFont("CJK", path, subfontIndex=0))
            _CJK_FONT_NAME = "CJK"
            return _CJK_FONT_NAME
        except Exception:
            # Some TTC layouts don't load via subfontIndex=0; try plain.
            try:
                pdfmetrics.registerFont(TTFont("CJK", path))
                _CJK_FONT_NAME = "CJK"
                return _CJK_FONT_NAME
            except Exception:
                continue

    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _CJK_FONT_NAME = "STSong-Light"
    return _CJK_FONT_NAME


def _generate_photo_jpeg(idx: int) -> bytes:
    """Real ~10-20 KB JPEG with gradient + avatar circle + tag.

    The image is a vertical hue-shifted gradient with a central circle
    showing a large index number (avatar-style placeholder), confetti
    dots scattered around, and a bottom-left M-NNNN tag. Each idx gets
    visually distinct colors so a quick scan of the cards confirms
    every photo is unique.
    """
    import colorsys
    import io

    from PIL import Image, ImageDraw

    # Golden-angle hue rotation across idx for spread; each photo is a
    # vertical gradient between two analogous hues.
    base_hue = (idx * 137 / 360.0) % 1.0
    top_rgb = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(base_hue, 0.65, 0.92))
    bottom_rgb = tuple(
        int(c * 255) for c in colorsys.hsv_to_rgb((base_hue + 0.08) % 1.0, 0.55, 0.78)
    )
    accent_rgb = tuple(
        int(c * 255) for c in colorsys.hsv_to_rgb((base_hue + 0.5) % 1.0, 0.55, 0.95)
    )

    size = 480
    img = Image.new("RGB", (size, size), top_rgb)
    pixels = img.load()
    # Linear vertical gradient — cheap and visually warmer than a
    # uniform fill.
    for y in range(size):
        t = y / (size - 1)
        r = int(top_rgb[0] * (1 - t) + bottom_rgb[0] * t)
        g = int(top_rgb[1] * (1 - t) + bottom_rgb[1] * t)
        b = int(top_rgb[2] * (1 - t) + bottom_rgb[2] * t)
        for x in range(size):
            pixels[x, y] = (r, g, b)

    draw = ImageDraw.Draw(img)

    # Confetti dots — pseudo-random but seeded by idx so the layout is
    # stable per row but varies between rows.
    dot_rng = random.Random(idx * 9973 + 17)
    for _ in range(28):
        cx = dot_rng.randint(0, size)
        cy = dot_rng.randint(0, size)
        r = dot_rng.randint(3, 12)
        alpha = dot_rng.choice([accent_rgb, (255, 255, 255), (20, 20, 20)])
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=alpha)

    # Center "avatar" circle with the row number large.
    cx, cy, cr = size // 2, size // 2 - 20, 110
    draw.ellipse(
        (cx - cr, cy - cr, cx + cr, cy + cr),
        fill=(255, 255, 255),
        outline=(20, 20, 20),
        width=4,
    )
    # PIL's default font is small; the digits still read clearly at
    # close zoom.
    draw.text((cx - 52, cy - 8), f"#{idx:04d}", fill=(20, 20, 20))

    # Bottom-left tag panel.
    draw.rectangle([(24, size - 80), (size - 24, size - 24)], fill=(255, 255, 255))
    draw.text((48, size - 64), f"M-{idx:04d}  generated", fill=(40, 40, 40))

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


# Body sections live as data so the PDF renderer just iterates them
# with consistent styling. Each entry is (heading, [lines]); the
# combined size is tuned to fill an A4 page from the header down to
# the bottom margin without overflowing.
_RESUME_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("學歷", (
        "    國立大學資訊工程學系畢業，雙主修數學與計算科學。",
        "    在學期間擔任系統最佳化與機器學習實驗室的助教，",
        "    協助實驗室成員設計實驗、撰寫工具與資料整理。",
        "    曾獲書卷獎一次、學業優異獎兩次、斐陶斐榮譽會員。",
    )),
    ("工作經歷", (
        "    軟體工程實習生，主要負責後端服務的設計與部署流程建立。",
        "    工作內容包含網路服務介面的規劃與實作、資料庫查詢效能",
        "    調校、容器化部署、以及基礎的持續整合與部署流程。",
        "    學會工作坊講師，分享資料結構複習與面試準備經驗。",
        "    參與多場校園演講，介紹軟體工程實務與業界趨勢。",
    )),
    ("專案經驗", (
        "    社群成員管理系統：以前後端分離架構實作的內部工具，",
        "    支援履歷上傳、面試心得分享與全文檢索功能。",
        "    分散式追蹤實驗：於多服務環境中導入分散式追蹤工具，",
        "    協助團隊將問題定位效率提升約三成。",
        "    自動化部署腳本：將原本手動操作的部署步驟整理為腳本",
        "    與設定檔，讓新成員能在較短時間內完成環境建立。",
    )),
    ("技能專長", (
        "    熟悉常見後端框架與關聯式資料庫的設計、查詢與調校。",
        "    熟悉前端框架與相關工具鏈，能獨立完成模組開發與測試。",
        "    具備使用容器化技術與持續整合工具的實務經驗。",
        "    熟悉常見的版本控制工作流程、程式碼審查文化與分支策略。",
        "    具備英文技術文件閱讀與書寫能力，能順暢參與線上協作。",
    )),
    ("語言能力", (
        "    中文：母語，能撰寫正式報告與技術文件。",
        "    英文：聽說讀寫流利，曾擔任國際會議的志工與通譯協助。",
        "    日文：基礎程度，能進行簡單日常對話與閱讀短文。",
    )),
    ("期望工作", (
        "    希望從事後端服務開發、系統架構設計或資料工程相關職務。",
        "    對規模化系統設計、效能調校與分散式系統議題有強烈興趣。",
    )),
    ("自我介紹", (
        "    從大學一年級接觸程式設計開始，便對軟體工程的細節與權衡",
        "    取捨產生濃厚興趣。在實驗室與實習期間，逐步建立起從需求",
        "    分析、架構設計到上線維運的完整經驗。我相信好的軟體不僅",
        "    要正確運作，更要好讀好維護；期許自己在職涯中持續精進。",
    )),
)


def _generate_resume_pdf(idx: int, name: str, institution: str, position: str | None) -> bytes:
    """Real full-page PDF resume; ~10-25 KB; uses an embedded CJK font."""
    import io

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    cjk_font = _ensure_cjk_pdf_font()

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, _ = A4

    # ---- Header ----
    # Latin header so the file is recognisable even on viewers that
    # cannot render the CJK font.
    c.setFont("Helvetica-Bold", 22)
    c.drawString(72, 770, f"Resume #{idx:04d}")

    # Brand bar under the header.
    c.setFillColorRGB(0.31, 0.27, 0.90)
    c.rect(72, 760, width - 144, 3, stroke=0, fill=1)
    c.setFillColorRGB(0, 0, 0)

    c.setFont(cjk_font, 14)
    c.drawString(72, 732, f"姓名：{name}")
    c.drawString(72, 712, f"學校：{institution}")
    if position:
        c.drawString(72, 692, f"系所：{position}")

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        72, 668,
        "(Generated by pyweb stress-seed — fake data, not a real resume.)",
    )

    # ---- Body sections ----
    # 10pt body / 12pt heading / 16pt line height fits all seven
    # sections between y=640 and the page's bottom margin.
    y = 638
    line_h = 16
    for heading, lines in _RESUME_SECTIONS:
        c.setFillColorRGB(0.2, 0.22, 0.55)
        c.setFont(cjk_font, 12)
        c.drawString(72, y, heading)
        # Underline below the heading for visual rhythm.
        c.setStrokeColorRGB(0.7, 0.72, 0.85)
        c.setLineWidth(0.5)
        c.line(72, y - 3, width - 72, y - 3)
        y -= 18
        c.setFillColorRGB(0.1, 0.1, 0.1)
        c.setFont(cjk_font, 10)
        for line in lines:
            c.drawString(72, y, line)
            y -= line_h
        y -= 6  # extra gap between sections

    c.showPage()
    c.save()
    return buf.getvalue()


# ----- Row builders -----


def _random_name() -> str:
    return random.choice(SURNAMES) + random.choice(GIVEN)


def _random_paragraphs(n: int) -> str:
    # random.choices allows repeats; for ~1-2 KB of body text this is
    # plenty of variety without inflating the lookup table.
    return "\n\n".join(random.choices(LOREM_PARAGRAPHS, k=n))


def _resume_md(idx: int, needle_every: int) -> str:
    body = "\n\n".join([
        "## 學歷", _random_paragraphs(2),
        "## 經歷", _random_paragraphs(3),
        "## 技能", _random_paragraphs(2),
    ])
    if needle_every > 0 and idx % needle_every == 0:
        body += f"\n\n[STRESS_NEEDLE_M_{idx}]"
    return body


def _experience_md(idx: int, needle_every: int) -> str:
    body = "\n\n".join([
        "## 面試流程", _random_paragraphs(3),
        "## 題目", _random_paragraphs(4),
        "## 心得", _random_paragraphs(2),
    ])
    if needle_every > 0 and idx % needle_every == 0:
        body += f"\n\n[STRESS_NEEDLE_J_{idx}]"
    return body


def _timeline_events(year: int) -> list[dict] | None:
    """0-5 events with ISO-date strings (matches the TimelineEvent schema)."""
    n = random.choices([0, 1, 2, 3, 4, 5], weights=[3, 2, 3, 4, 4, 2])[0]
    if n == 0:
        return None
    days = sorted(random.sample(range(60, 360), k=n))
    events = []
    for day_of_year in days:
        d = datetime(year, 1, 1) + timedelta(days=day_of_year - 1)
        events.append({
            "date": d.strftime("%Y-%m-%d"),
            "event": random.choice(TIMELINE_VOCAB),
        })
    return events


def _make_member_row(idx: int, needle_every: int) -> dict:
    joined_at = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 1500))

    real_name = _random_name()
    institution = random.choice(INSTITUTIONS)
    position = random.choice(POSITIONS) if random.random() > 0.10 else None

    # Every seeded member gets a photo + PDF — uniform coverage makes
    # the dataset more useful for stress-testing the BLOB-deferred list
    # / detail / streaming endpoints (no need to filter).
    return {
        "graduation_year": random.randint(2018, 2027),
        "real_name": real_name,
        "institution": institution,
        "position": position,
        "photo": _generate_photo_jpeg(idx),
        "photo_content_type": "image/jpeg",
        "photo_updated_at": joined_at,
        "resume_md": _resume_md(idx, needle_every),
        "resume_pdf": _generate_resume_pdf(idx, real_name, institution, position),
        "resume_pdf_updated_at": joined_at,
        "joined_at": joined_at,
    }


def _make_job_row(idx: int, needle_every: int):
    # Imported lazily so app.* modules don't load until env is configured.
    from app.models import JobKind

    year = random.randint(2018, 2027)
    events = _timeline_events(year)
    row = {
        "job_year": year,
        "job_month": random.randint(1, 12),
        "company": random.choice(COMPANIES),
        "category": random.choice(CATEGORIES) if random.random() > 0.05 else None,
        "kind": random.choice([JobKind.INTERNSHIP, JobKind.FULLTIME]),
        "experience_md": _experience_md(idx, needle_every),
        # Authors stay anonymous ~30% of the time, mirroring the schema's
        # nullable real_name column.
        "real_name": _random_name() if random.random() > 0.30 else None,
        "timeline_md": None,  # legacy free-form column; new rows use timeline_events
        "created_at": datetime.now(timezone.utc) - timedelta(days=random.randint(1, 1500)),
    }
    # Only include the JSON column when we actually have events. The
    # SQLAlchemy JSON type with bulk_insert_mappings would otherwise
    # serialize None as the literal JSON 'null' string instead of SQL
    # NULL — which then makes `WHERE timeline_events IS NOT NULL`
    # match every row. Omitting the key falls through to the column's
    # default NULL.
    if events is not None:
        row["timeline_events"] = events
    return row


# ----- Driver -----


def seed(
    *,
    db_url: str,
    members: int,
    jobs: int,
    batch: int = 500,
    needle_every: int = 50,
    reset: bool = False,
    seed_value: int | None = None,
) -> dict:
    """Populate `db_url` with `members` members and `jobs` jobs.

    Photos / PDFs are generated by Pillow and reportlab respectively
    (their natural size, ~30-50 KB and ~3-6 KB). To install:
    `pip install -r requirements-dev.txt`.

    Returns a summary dict with timing + counts so callers (including
    tests) can assert on what was written without re-querying the DB.
    """
    if seed_value is not None:
        random.seed(seed_value)

    # Stub the env so `app.config`'s pydantic-settings validation passes
    # when this script is run from a host shell that has none of the
    # production secrets set. The script never uses login or session
    # signing — these are just here to clear the validator.
    os.environ.setdefault("SESSION_SECRET", "stress-seed-not-real")
    os.environ.setdefault("SEED_ADMIN_USERNAME", "stress-seed-admin")
    os.environ.setdefault("SEED_ADMIN_PASSWORD", "stress-seed-admin-pw")
    os.environ.setdefault("SEED_VIEWER_USERNAME", "stress-seed-viewer")
    os.environ.setdefault("SEED_VIEWER_PASSWORD", "stress-seed-viewer-pw")

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    from app.database import Base
    from app.models import Job, Member  # noqa: F401  -- registers tables

    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    summary = {
        "members_inserted": 0,
        "jobs_inserted": 0,
        "members_total": 0,
        "jobs_total": 0,
        "elapsed_seconds": 0.0,
    }

    started = time.monotonic()
    session = SessionLocal()
    try:
        if reset:
            session.execute(text("DELETE FROM jobs"))
            session.execute(text("DELETE FROM members"))
            session.commit()

        # Members
        for chunk_start in range(0, members, batch):
            end = min(chunk_start + batch, members)
            rows = [
                _make_member_row(i, needle_every)
                for i in range(chunk_start, end)
            ]
            session.bulk_insert_mappings(Member, rows)
            session.commit()
            summary["members_inserted"] = end
            print(f"  members: {end:>6}/{members}")

        # Jobs
        for chunk_start in range(0, jobs, batch):
            end = min(chunk_start + batch, jobs)
            rows = [_make_job_row(i, needle_every) for i in range(chunk_start, end)]
            session.bulk_insert_mappings(Job, rows)
            session.commit()
            summary["jobs_inserted"] = end
            print(f"  jobs:    {end:>6}/{jobs}")

        summary["members_total"] = session.execute(
            text("SELECT COUNT(*) FROM members")
        ).scalar()
        summary["jobs_total"] = session.execute(
            text("SELECT COUNT(*) FROM jobs")
        ).scalar()
    finally:
        session.close()
        engine.dispose()

    summary["elapsed_seconds"] = round(time.monotonic() - started, 2)
    return summary


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Seed pyweb's SQLite DB with fake stress-test data."
    )
    parser.add_argument("--members", type=int, default=1000)
    parser.add_argument("--jobs", type=int, default=1000)
    parser.add_argument("--batch", type=int, default=500,
                        help="Rows per commit (default 500).")
    parser.add_argument("--needle-every", type=int, default=50,
                        help="Inject [STRESS_NEEDLE_*] every Nth row (0 to disable).")
    parser.add_argument("--reset", action="store_true",
                        help="Truncate members + jobs tables before inserting.")
    parser.add_argument("--seed", type=int, default=None,
                        help="random.seed() for reproducibility.")
    parser.add_argument("--db-url", default=DEFAULT_DB_URL,
                        help=f"SQLAlchemy URL (default {DEFAULT_DB_URL}).")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    print(f"DB:    {args.db_url}")
    print(f"Plan:  {args.members} members + {args.jobs} jobs"
          + (" (reset first)" if args.reset else ""))
    print(f"Needle: every {args.needle_every} rows" if args.needle_every > 0 else "Needle: off")
    print()

    summary = seed(
        db_url=args.db_url,
        members=args.members,
        jobs=args.jobs,
        batch=args.batch,
        needle_every=args.needle_every,
        reset=args.reset,
        seed_value=args.seed,
    )

    print()
    print(f"Done in {summary['elapsed_seconds']}s")
    print(f"  members table: {summary['members_total']} rows total")
    print(f"  jobs table:    {summary['jobs_total']} rows total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
