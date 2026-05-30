# pyweb — 社群成員管理網站

記錄社群成員資料、求職與實習心得分享，並提供一個社群動態首頁的小型網站。

## 功能

- **首頁**：站內計數與社群動態 feed。
- **登入**：管理員 / 檢視者兩組固定帳號，server-side session。
- **成員介紹**：成員基本資料、照片、Markdown 履歷與履歷 PDF。
- **求職紀錄**：實習 / 正職心得與時程表，支援附件上傳與線上預覽（office 檔走 OnlyOffice 轉 PDF）。
- **設定頁 `/settings`**：管理員可改帳密、外觀資源、系統限制。

## 技術棧

| 層 | 技術 |
|---|---|
| 前端 | Vue 3（Composition API + `<script setup>`）、Vue Router、Pinia、Element Plus、md-editor-v3、cropperjs、DOMPurify |
| 後端 | FastAPI、SQLAlchemy 2.x、Pydantic v2、SlowAPI（rate limit）、httpx + PyJWT（OnlyOffice 整合） |
| 資料庫 | SQLite + Alembic（schema migration） |
| 認證 | Server-side session（Starlette `SessionMiddleware`，簽章式 cookie，附 `password_version` 失效機制） |
| 檔案儲存 | 一律落在 `data/uploads/`（bind mount 出來，host 可直接看），不進 DB BLOB |
| 文件轉換 | OnlyOffice Document Server 8.2（office → PDF，僅在 compose network 內部曝露） |

## 專案結構

```
pyweb/
├── backend/                  # FastAPI 後端
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py            # 從 app.core.config 讀 DATABASE_URL
│   │   └── versions/         # 一支一支的 migration 檔
│   └── app/
│       ├── main.py
│       ├── database.py
│       ├── init_db.py        # 跑 alembic upgrade + 種帳號 + 種 app_configs 預設值
│       ├── reset_password.py # CLI：丟失 admin 密碼時的救援腳本
│       ├── models/           # member / job / job_attachment / app_config / site_setting / user
│       ├── schemas/          # Pydantic schemas
│       ├── routers/          # auth / members / jobs / job_attachments / activity / stats / settings / internal
│       └── core/             # config / deps / security / rate_limit / attachments / office_convert / runtime_config / audit_log / search_query
├── frontend/                 # Vue 3 + Vite 前端
│   └── src/
│       ├── views/            # Home / Login / Members / Jobs / Settings
│       ├── layouts/          # AuthLayout（navbar + outlet）
│       ├── components/       # 對話框、附件管理 / 檢視、ActivityFeed、MarqueeText 等
│       │   └── settings/     # 設定頁的各區塊
│       ├── router/
│       ├── stores/           # Pinia auth store
│       ├── api/              # axios 包裝
│       └── utils/            # attachmentTree / searchQuery / relativeTime / useCounter
├── nginx/                    # 容器內前端 nginx 設定
├── data/                     # bind mount：SQLite + uploads + logs（已 gitignore）
├── scripts/                  # rclone 備份腳本
├── docker-compose.yml
└── CLAUDE.md                 # 開發規範（給 AI 助手讀）
```

## 部署（Docker Compose）

需求：Docker Engine 24+ / Docker Compose v2+。

```bash
# 1. 準備 .env（基於 .env.docker.example 填入帳密、SESSION_SECRET、OnlyOffice JWT）
cp .env.docker.example .env
$EDITOR .env

# 2. 確保 data/ 由 host user 持有（否則 docker 會以 root 建出，container 內 uid 1000 寫不進去）
mkdir -p data

# 3. 一鍵啟動（首次會 build image 並下載 OnlyOffice ~1.4GB，約 3–5 分鐘）
docker compose up --build

# 背景跑：
docker compose up -d --build

# 看 log：
docker compose logs -f

# 結束（保留 SQLite 與上傳檔）：
docker compose down

# 結束並清掉資料：
docker compose down -v
```

開瀏覽器到 [http://localhost:8081/](http://localhost:8081/)。

### 服務拓樸

| 服務 | 鏡像來源 | 對外 port | 內部 |
|---|---|---|---|
| `frontend` | `frontend/Dockerfile`（multi-stage：node build → nginx serve） | `8081:8080` | 服務 `dist/` + 反代 `/api` → backend |
| `backend` | `backend/Dockerfile`（python:3.13-slim） | 不對外 | `:8000`，由 frontend nginx 反代 |
| `onlyoffice` | `onlyoffice/documentserver:8.2` | 不對外 | `:80`，僅在 compose network 內由 backend 呼叫 |
| `./data` | bind mount | — | 掛在 backend `/data`，存 `pyweb.db` 與 `uploads/`、`logs/` |

backend 容器啟動時會跑 `app/init_db.py`：先 `alembic upgrade head` 把 schema 帶到最新版，再依 `.env` 內的 `SEED_*` 變數 upsert 帳號，最後寫入 `app_configs` 預設值。所有步驟皆冪等，**不會覆蓋既有密碼或既有 config**。

SQLite 檔以 bind mount 落在 [data/pyweb.db](data/)，附件落在 `data/uploads/{members,jobs}/`，host 上可直接 `sqlite3 data/pyweb.db` 或拿 DBeaver 開，附件也能直接用檔案總管瀏覽。整個 `data/` 目錄已被 gitignore，但 `.gitkeep` 保留資料夾結構。要重置：`docker compose down -v && rm -rf data/pyweb.db data/uploads/*`。

### 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `SESSION_SECRET` | 是 | 簽 session cookie，請用長亂數 |
| `SESSION_MAX_AGE_SECONDS` | 否 | 預設 `86400`（一天） |
| `CORS_ORIGINS` | 否 | 同源部署用不到；保留 sane default |
| `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` | 是 | 首次啟動的 admin 帳號 |
| `SEED_VIEWER_USERNAME` / `SEED_VIEWER_PASSWORD` | 是 | 首次啟動的 viewer 帳號 |
| `ONLYOFFICE_JWT_SECRET` | 是 | backend 與 OnlyOffice 之間 JWT 簽章密鑰；`python -c "import secrets; print(secrets.token_urlsafe(32))"` 生 |

`UPLOADS_DIR`、`ONLYOFFICE_INTERNAL_URL`、`BACKEND_INTERNAL_URL` 由 `docker-compose.yml` 直接寫死，平常不用手動設。

## 資料庫遷移（Alembic）

Schema 變更走 Alembic，沒有自動 `create_all`。每次啟動 `init_db.py` 會自動 `alembic upgrade head` 把資料庫帶到最新版；只有「第一次從舊版升級」需要手動動一下。

### 一般工作流程

| 情境 | 指令 |
|---|---|
| 全新環境部署 | `docker compose up -d --build`（`init_db` 會自動 upgrade 到最新） |
| 改了 `app/models/*.py` | `docker compose run --rm backend alembic revision --autogenerate -m "描述"`，**檢查產生的檔案再 commit**，下次啟動就會帶上 |
| 想看目前的版本 | `docker compose exec backend alembic current` |
| 想看完整歷史 | `docker compose exec backend alembic history` |
| 回退一版（小心） | `docker compose exec backend alembic downgrade -1` |

> **⚠️ Autogenerate 不是萬靈丹。** Alembic 會猜測 column add / drop / rename，但抓不到 server_default 變化、複雜的 enum 值新增、或某些 SQLite ALTER 限制。產生 migration 後**一定要打開檔案手動檢查**再 commit。

### 從舊版（沒有 Alembic）升級既有部署

如果你的 `pyweb.db` 是 Alembic 加進來之前就在跑的（裡面已經有 `users` / `members` / `site_settings` / `internships` 但沒有 `alembic_version` 表），第一次升級必須先告訴 Alembic「資料庫已經是 baseline 狀態」，**否則 upgrade 會試圖再 CREATE TABLE 而炸掉**。

正式流程：

```bash
# 1. 拉新版 code、停服務
git pull
docker compose down

# 2. 一次性 stamp baseline
docker compose run --rm backend alembic stamp 0001

# 3. 重新啟動 — backend 容器會自動 alembic upgrade head 把 0001 之後的 migration 跑完
docker compose up -d --build
```

驗證一下：

```bash
docker compose exec backend python -c "
import sqlite3
con = sqlite3.connect('/data/pyweb.db')
print('alembic_version:', con.cursor().execute('SELECT version_num FROM alembic_version').fetchone())
"
```

之後就跟一般流程一樣：每次部署只要 `docker compose up -d --build`。

### 測試環境

`pytest` 跑的 in-memory DB **不**走 Alembic，直接用 `Base.metadata.create_all`（[backend/tests/conftest.py](backend/tests/conftest.py)）——測試只關心當下的 ORM 是不是正確、不需要驗 migration 序列。Migration 本身的正確性由 commit message 內手動 stamp / upgrade 的端到端驗證 + 產生環節的人工 review 把關。

## 帳號（種子資料）

由 `backend/app/init_db.py` 建立兩個固定角色：

| 角色 | 權限 |
|---|---|
| `admin` | 增、刪、改、查；可在 `/settings` 修改兩個帳號的 username 與密碼，並調整系統限制 |
| `viewer` | 僅查 |

帳號的初始 username / 密碼來自 `.env`：

```
SEED_ADMIN_USERNAME=...
SEED_ADMIN_PASSWORD=...
SEED_VIEWER_USERNAME=...
SEED_VIEWER_PASSWORD=...
```

> **⚠️ `.env` 的 `SEED_*` 只在「首次初始化」生效。** `init_db.py` 對既有帳號一律跳過、**不會覆蓋密碼或更名**。事後想改：
>
> - **推薦**：登入 admin → 右上角 → `/settings` → 帳號管理 → 改 username / 密碼。
> - **救援（忘記 admin 密碼）**：`docker compose exec backend python -m app.reset_password admin <new_pw>` —— 會 rotate 密碼並 bump `password_version`，任何既有 session cookie 一併失效。
> - **完全重置**：`docker compose down -v && rm -rf data/pyweb.db data/uploads/*`（會清掉所有資料）。

登入只認密碼（不問 username），所以兩個帳號的密碼必須不同；UI 在改密碼時會擋住撞號。

## 自動備份到雲端（rclone）

排程腳本 [scripts/pyweb-backup.sh](scripts/pyweb-backup.sh) 走「**hot snapshot → 打包整個 data/ → 上傳 → 清舊**」流程，**不停服務**。流程：

1. `sqlite3 .backup` + `?immutable=1` 對 `pyweb.db` 做 atomic 快照到 tmp
2. `cp -a data/.` → tmp/data/（整個 data 目錄，**未來新加子資料夾自動包進去**）
3. 拿 step 1 的 atomic snapshot 覆蓋 tmp/data/pyweb.db（取代有 torn page 風險的 live 版本）
4. 刪掉 tmp/data/pyweb.db-wal、pyweb.db-shm（SQLite 內部協調用、備份意義為零）
5. `tar czf` → `pyweb-STAMP.tar.gz` → rclone 上傳 → 清舊

**腳本本身可以放公開 repo — secret 都在 `~/.config/rclone/rclone.conf`，已寫進 `.gitignore`**。

> **⚠️ Trade-off**：因為**不停服務**，理論上有兩個小破口：
> - DB 的 `?immutable=1` 會跳過 `-wal` 內尚未 checkpoint 的資料（SQLite 預設每 1000 page / ~4 MB 自動 checkpoint，社群網站平常 WAL 是空的）
> - `cp -a data/` 跟 backend 寫附件有 ~幾十毫秒 race window，極小機率抓到正在寫一半的附件
>
> 凌晨備份 + 網站幾天才更新一次，實務上等同 0 風險。要 100% 數學保證，看 git history 找回「停服務」版本即可。

### 一次性設定（host 端）

```bash
# 1. 安裝
sudo apt install rclone sqlite3

# 2. 設定 Drive OAuth（互動式，會跳瀏覽器一次拿到 refresh token）
rclone config
# - 選 New remote, 命名 e.g. pyweb_backup, 選 Google Drive
# - 一路按預設, 在跳瀏覽器那步登入授權
# 進階：再建一個 crypt remote 疊在 pyweb_backup 上做 client-side 加密
#   rclone config → New remote → crypt → 指向 pyweb_backup:pyweb-encrypted

# 3. 鎖緊 config 權限（內含 OAuth refresh token，等同永久存取權）
chmod 600 ~/.config/rclone/rclone.conf
```

### 手動跑一次驗證

```bash
cd /path/to/pyweb
PYWEB_DATA_DIR=./data RCLONE_REMOTE=pyweb_backup:pyweb-backups bash scripts/pyweb-backup.sh
```

預期輸出：

```
[20260505-070000] Snapshotting pyweb.db...
[20260505-070000] Verifying DB integrity...
[20260505-070000] Mirroring ./data/...
[20260505-070000] Bundling...
[20260505-070000] Uploading 18M → pyweb_backup:pyweb-backups/
[20260505-070000] Pruning archives older than 30d
[20260505-070000] Backup complete
```

### 排程

**重要：用自己的 user crontab，不要用 sudo / root 的 crontab。** 以 root 跑會把 `data/` 內的檔案 owner 改成 root，導致 container 內 `pyweb` (uid 1000) 寫不進去 → 站上上傳全部失敗。腳本開頭已經加了 `$EUID -eq 0` 拒絕保護。

```cron
# crontab -e（你自己的 user，不要 sudo crontab）
0 3 * * * cd /home/me/pyweb && RCLONE_REMOTE=pyweb_backup:pyweb-backups bash scripts/pyweb-backup.sh >> /home/me/pyweb-backup.log 2>&1
```

或 systemd timer（log 走 journalctl 更乾淨）：

```ini
# /etc/systemd/system/pyweb-backup.service
[Service]
Type=oneshot
User=me
WorkingDirectory=/home/me/pyweb
Environment=RCLONE_REMOTE=pyweb_backup:pyweb-backups
ExecStart=/usr/bin/bash scripts/pyweb-backup.sh

# /etc/systemd/system/pyweb-backup.timer
[Timer]
OnCalendar=*-*-* 03:00:00 UTC
Persistent=true
[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now pyweb-backup.timer
```

### 環境變數

| 變數 | 預設 | 說明 |
|---|---|---|
| `PYWEB_DATA_DIR` | `./data` | 含 `pyweb.db` / `uploads/` / `logs/` 的目錄 |
| `RCLONE_REMOTE` | `gdrive:pyweb-backups` | rclone remote + 資料夾 |
| `RETENTION_DAYS` | `30` | 保留幾天的備份；超過會被 `rclone delete` 清掉 |

### Restore

備份檔 unpack 出來就是一個完整的 `data/` 資料夾，整個取代現有的 `data/` 即可：

```bash
# 1. 從 Drive 拉備份
rclone copy gdrive:pyweb-backups/pyweb-20260101-030000.tar.gz .

# 2. 停服務、整個換掉 data/
docker compose stop backend
rm -rf data
tar xzf pyweb-20260101-030000.tar.gz   # 解壓後直接出現一個 data/ 目錄

# 3. 確認 owner（應該是 uid 1000，host 上對應 jenkins 或你的 host user）
ls -la data/

# 4. 重啟
docker compose start backend
```

### Secret 守則

- **絕對不要 commit `~/.config/rclone/rclone.conf`** — 內含 OAuth refresh token，外洩等同 Drive 永久存取權；萬一外洩到 console.cloud.google.com 撤銷該 client、重跑 `rclone config`
- 若用了 `crypt` remote，密碼也在同一個檔案裡（rclone 用 `obscure` 編碼，**不是加密**）
- public repo 可用 `gitleaks` / `trufflehog` 掃 history 確認沒有歷史 commit 不小心混進 token
