# pyweb — 社群成員管理網站

記錄社群成員資料，以及實習／求職心得分享的小型網站。

## 功能

- **登入**：兩組固定帳號（管理員 / 檢視者），server-side session 認證。
- **成員介紹**：表格列出畢業年份、本名、目前就職／就讀、入群時間，可附照片與 Markdown 履歷。
- **求職紀錄**：紀錄實習與正職的求職心得（含面試題目、實作、domain 問題）、時程表，可匿名；支援依年份／公司／類型（實習 / 正職）篩選與排序。

## 技術棧

| 層 | 技術 |
|---|---|
| 前端 | Vue 3（Composition API + `<script setup>`）、Vue Router、Pinia、Element Plus、md-editor-v3、DOMPurify |
| 後端 | FastAPI、SQLAlchemy、Pydantic |
| 資料庫 | SQLite + Alembic（schema migration） |
| 認證 | Server-side session（Starlette `SessionMiddleware`，簽章式 cookie） |

## 專案結構

```
pyweb/
├── backend/        # FastAPI 後端
│   ├── alembic.ini       # Alembic schema migration 設定
│   ├── alembic/
│   │   ├── env.py        # 從 app.core.config 讀 DATABASE_URL
│   │   └── versions/     # 一支一支的 migration 檔
│   └── app/
│       ├── main.py
│       ├── database.py
│       ├── models/
│       ├── schemas/
│       ├── routers/      # auth / members / internships
│       ├── core/         # security、deps、config
│       └── init_db.py    # 跑 alembic upgrade + 種兩組帳號
├── frontend/       # Vue 3 + Vite 前端
│   └── src/
│       ├── views/
│       ├── components/
│       ├── router/
│       ├── stores/
│       ├── api/
│       └── utils/
└── CLAUDE.md       # 開發規範（給 AI 助手讀）
```

## 開發階段

| Phase | 目標 |
|---|---|
| 0 | 專案初始化（前後端骨架、`.gitignore`） |
| 1 | 資料庫 schema + 初始化兩組帳號 |
| 2 | 後端 Session 登入 API + 權限 dependency |
| 3 | 前端登入頁 + router guard + Pinia auth store |
| 4 | 成員 CRUD API + 前端列表頁 + 表單 |
| 5 | 成員照片上傳／顯示 |
| 6 | 實習紀錄 CRUD API + 前端頁面 |
| 7 | Markdown 編輯器整合 |
| 8 | 權限細節打磨（按鈕顯示、錯誤處理） |
| 9 | README 完整版 |

## 本機開發

### 後端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # 跑 pytest 用，可選
cp .env.example .env                   # 填入 SESSION_SECRET、SEED_* 等變數
python -m app.init_db                  # 跑 alembic upgrade + 種帳號
uvicorn app.main:app --reload
```

預設啟動於 `http://127.0.0.1:8000`，健康檢查：`GET /health`。

> **⚠️ 漏跑 `init_db` 會在第一次登入時 500（`no such table: users`）。** uvicorn 啟動時會自動建出空的 `pyweb.db` 檔，但裡面沒有 schema、也沒有種子帳號。`init_db` 會先跑 `alembic upgrade head` 把 schema 帶到最新版，再 upsert 帳號（兩步都是冪等的，可以重複跑）。

跑測試：

```bash
cd backend
.venv/bin/pytest        # 後端測試
cd ../frontend && npm run test   # 前端測試
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

預設啟動於 `http://127.0.0.1:5173`。

## Production-like 部署

兩種選擇：**docker-compose（推薦，一鍵）** 或 **host nginx + venv（不裝 Docker 時的替代）**。

> docker-compose 走 host port **8081**；host nginx 流程仍用 8080（兩者可同時跑、不衝突）。

### docker-compose

需求：Docker Engine 24+ / Docker Compose v2+。

```bash
# 1. 準備 .env（基於 .env.docker.example 填入帳密與 SESSION_SECRET）
cp .env.docker.example .env
$EDITOR .env

# 2. 一鍵啟動（首次會 build image，約 1–2 分鐘）
docker compose up --build

# 背景跑：
docker compose up -d --build

# 看 log：
docker compose logs -f

# 結束（保留 SQLite 資料）：
docker compose down

# 結束並清掉資料：
docker compose down -v
```

開瀏覽器到 [http://localhost:8081/](http://localhost:8081/)。三服務拓樸：

| 服務 | 鏡像來源 | 對外 port | 內部 |
|---|---|---|---|
| `backend` | `backend/Dockerfile` (python:3.13-slim) | 不對外 | `:8000` 由 nginx 反代 |
| `frontend` | `frontend/Dockerfile` (multi-stage：node build → nginx serve) | `8081:8080` | 服務 `dist/` + 反代 `/api` |
| `./data` | bind mount | — | 掛在 backend `/data`，存 `pyweb.db` |

backend 容器啟動時會跑 `app/init_db.py`，先 `alembic upgrade head` 把 schema 帶到最新版（沒有變動就 no-op），再依 `.env` 內的 `SEED_*` 變數種帳號。兩步都是冪等的，**不會覆蓋既有密碼**。

SQLite 檔以 bind mount 落在 [data/pyweb.db](data/)，host 上可直接 `sqlite3 data/pyweb.db` 或拿 DBeaver 開。整個 `data/` 目錄已被 gitignore，但 `.gitkeep` 保留資料夾結構。要重置資料：`rm data/pyweb.db && docker compose restart backend`。

### host nginx + venv（無 Docker）

模擬上線環境：把前端 build 成靜態檔，由系統 nginx 在 8080 同時服務靜態資源與反向代理 `/api` 到後端。前端走同源請求，不需要 CORS。

需求：系統已安裝 nginx（`sudo apt install nginx`）。我們的 nginx 跑在非 privileged port（8080）、log/pid 寫到 `/tmp/pyweb-nginx/`，不會動到系統 nginx。

```bash
# 1. build 前端
cd frontend && npm run build && cd ..

# 2. 確保後端在跑
cd backend
SESSION_SECRET=... SEED_ADMIN_USERNAME=... ...   # 填好 .env
.venv/bin/python -m app.init_db                  # 首次需建表 + 種帳號
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd ..

# 3. 啟動專用 nginx
./nginx/start.sh -g 'daemon on;'

# 結束
./nginx/stop.sh
```

設定檔在 [nginx/pyweb.conf.template](nginx/pyweb.conf.template)，log 在 `/tmp/pyweb-nginx/pyweb-nginx-error.log`。

## 資料庫遷移（Alembic）

Schema 變更走 Alembic，沒有自動 `create_all`。每次啟動 `init_db.py` 會自動 `alembic upgrade head` 把資料庫帶到最新版；只有「第一次從舊版升級」需要手動動一下。

### 一般工作流程

| 情境 | 指令 |
|---|---|
| 全新環境部署 | `python -m app.init_db`（會自動 upgrade 到最新） |
| 平常開發、剛 git pull | 同上，`init_db` 跑完即可 |
| 改了 `app/models/*.py` | `cd backend && alembic revision --autogenerate -m "描述"`，**檢查產生的檔案再 commit**，下次 `init_db` 就會帶上 |
| 想看目前的版本 | `cd backend && alembic current` |
| 想看完整歷史 | `cd backend && alembic history` |
| 回退一版（小心） | `cd backend && alembic downgrade -1` |

> **⚠️ Autogenerate 不是萬靈丹。** Alembic 會猜測 column add / drop / rename，但抓不到 server_default 變化、複雜的 enum 值新增、或某些 SQLite ALTER 限制。產生 migration 後**一定要打開檔案手動檢查**再 commit。

### 從舊版（沒有 Alembic）升級既有部署

如果你的 `pyweb.db` 是 Alembic 加進來之前就在跑的（裡面已經有 `users` / `members` / `site_settings` / `internships` 但沒有 `alembic_version` 表），第一次升級必須先告訴 Alembic「資料庫已經是 baseline 狀態」，**否則 upgrade 會試圖再 CREATE TABLE 而炸掉**。

正式流程：

```bash
# 1. 拉新版 code、停服務
git pull
docker compose down

# 2. 一次性 stamp baseline（在 backend/ 裡跑，或用 docker compose run）
docker compose run --rm backend alembic stamp 0001
# 純 venv 環境就改成：
# cd backend && .venv/bin/alembic stamp 0001

# 3. 重新啟動 — backend 容器會自動 alembic upgrade head 把 0001 之後的 migration 跑完
docker compose up -d --build
```

驗證一下：

```bash
docker compose exec backend python -c "
import sqlite3
con = sqlite3.connect('/data/pyweb.db')
print('alembic_version:', con.cursor().execute('SELECT version_num FROM alembic_version').fetchone())
print('internships cols:', [r[1] for r in con.cursor().execute('PRAGMA table_info(internships)')])
"
# 應看到 alembic_version=('0002',) 且 internships 多了 'kind' 欄位
```

之後就跟一般流程一樣：每次部署只要 `docker compose up -d --build`，`init_db` 會自動帶 schema 到最新版。

### 測試環境

`pytest` 跑的 in-memory DB **不**走 Alembic，直接用 `Base.metadata.create_all`（[backend/tests/conftest.py](backend/tests/conftest.py)）——測試只關心當下的 ORM 是不是正確、不需要驗 migration 序列。Migration 本身的正確性由 commit message 內手動 stamp / upgrade 的端到端驗證 + 產生環節的人工 review 把關。

## 帳號（種子資料）

由 `backend/app/init_db.py` 建立兩個固定角色：

| 角色 | 權限 |
|---|---|
| `admin` | 增、刪、改、查；可在 UI 修改兩個帳號的 username 與密碼 |
| `viewer` | 僅查 |

帳號的初始 username / 密碼來自 `.env`：

```
SEED_ADMIN_USERNAME=...
SEED_ADMIN_PASSWORD=...
SEED_VIEWER_USERNAME=...
SEED_VIEWER_PASSWORD=...
```

> **⚠️ `.env` 的 `SEED_*` 只在「首次初始化」生效。** `init_db.py` 對既有 user 一律跳過、**不會覆蓋密碼或更名**。事後想改：
>
> - **推薦**：登入 admin → 點 navbar 右上「帳號設定」→ 改 username / 密碼。
> - **完全重置**：`rm backend/pyweb.db && cd backend && .venv/bin/python -m app.init_db`（會清掉所有資料，包含成員與求職紀錄；`init_db` 會自動 alembic upgrade 出新 schema）。

登入只認密碼（不問 username），所以兩個帳號的密碼必須不同；UI 在改密碼時會擋住撞號。

## 自動備份到雲端（rclone）

排程腳本 [scripts/pyweb-backup.sh](scripts/pyweb-backup.sh) 走「**停 backend → atomic snapshot → 啟 backend → gzip → 上傳 → 清舊**」流程。停服務這幾秒讓 SQLite 自動 checkpoint WAL 並釋放所有 lock，所以拿到的快照保證 100% 完整、絕不會 corrupt。**腳本本身可以放公開 repo — secret 都在 `~/.config/rclone/rclone.conf` 不會被 commit**（已寫進 `.gitignore`）。

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

# 4. 確保跑備份的 user 在 docker group（要能下 docker compose stop / start）
sudo usermod -aG docker $USER
# 重新登入或 `newgrp docker` 讓 group 生效
```

### 手動跑一次驗證

```bash
cd /path/to/pyweb
PYWEB_DATA_DIR=./data RCLONE_REMOTE=pyweb_backup:pyweb-backups bash scripts/pyweb-backup.sh
```

預期輸出（順利的話 ~10 秒內結束）：

```
[20260505-070000] Stopping backend for clean snapshot...
[20260505-070000] Snapshotting...
[20260505-070000] Restarting backend...
[20260505-070000] Verifying integrity...
[20260505-070000] Uploading 3.2M → pyweb_backup:pyweb-backups/
[20260505-070000] Pruning archives older than 30d
[20260505-070000] Backup complete
```

### 排程

```cron
# /etc/cron.d/pyweb-backup（替換使用者名稱與路徑）
0 3 * * * youruser cd /home/youruser/pyweb && RCLONE_REMOTE=pyweb_backup:pyweb-backups bash scripts/pyweb-backup.sh >> /home/youruser/pyweb-backup.log 2>&1
```

或 systemd timer（log 走 journalctl 更乾淨）：

```ini
# /etc/systemd/system/pyweb-backup.service
[Service]
Type=oneshot
User=youruser
WorkingDirectory=/home/youruser/pyweb
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
| `PYWEB_DATA_DIR` | `./data` | 含 `pyweb.db` 的目錄 |
| `RCLONE_REMOTE` | `gdrive:pyweb-backups` | rclone remote + 資料夾 |
| `RETENTION_DAYS` | `30` | 保留幾天的備份；超過會被 `rclone delete` 清掉 |
| `COMPOSE_SERVICE` | `backend` | docker-compose.yml 裡 backend 的 service 名稱 |
| `COMPOSE_PROJECT_DIR` | 當下目錄 | `docker compose` 要在哪個目錄執行 |

### 為什麼要停服務

SQLite WAL 模式下，活著被寫入的 DB 任何形式的「外部讀」都有風險：
- `cp` / `tar` 會撞 torn page（transaction 寫到一半）
- `sqlite3 .backup` 在 read 端**仍然需要寫 `-shm` 檔**做 reader/writer 協調（這就是先前卡住的原因）
- `?immutable=1` 雖然能 bypass 鎖協調，但會跳過 `-wal` 內未 checkpoint 的資料

唯一無懈可擊的做法：讓 backend 完整下線，SQLite 在最後一個 connection 關閉時會自動 `wal_checkpoint(TRUNCATE)`，把 WAL 全部 merge 回主檔並刪掉 `-wal` / `-shm` 檔。這時候做的快照（不論用 `sqlite3 .backup` 還是 `cp`）都是 100% 完整。代價只有 3–8 秒的 downtime，半夜執行對社群網站幾乎無感。

腳本還做了 **trap-based 復原**：snapshot 或上傳失敗時 `EXIT` trap 仍會把 backend 重新拉起來，不會留下你的服務在停機狀態。

### Restore

`rclone copy` 把備份拉下來，`gunzip` 解開，停掉 backend container 後直接覆蓋 `data/pyweb.db`：

```bash
rclone copy gdrive:pyweb-backups/pyweb-20260101-030000.db.gz .
gunzip pyweb-20260101-030000.db.gz
docker compose stop backend
mv pyweb-20260101-030000.db data/pyweb.db
docker compose up -d backend
```

### Secret 守則

- **絕對不要 commit `~/.config/rclone/rclone.conf`** — 內含 OAuth refresh token，外洩等同 Drive 永久存取權；萬一外洩到 console.cloud.google.com 撤銷該 client、重跑 `rclone config`
- 若用了 `crypt` remote，密碼也在同一個檔案裡（rclone 用 `obscure` 編碼，**不是加密**）
- public repo 可用 `gitleaks` / `trufflehog` 掃 history 確認沒有歷史 commit 不小心混進 token
 