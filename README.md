# pyweb — 社群成員管理網站

記錄社群成員資料、求職與實習心得分享，並提供一個社群動態首頁的小型網站。

## 功能

- **首頁**：站內計數與社群動態 feed。
- **登入**：成員走 Discord OAuth；另有管理員 / 檢視者兩組密碼帳號作為備援。皆為 server-side session。詳見「帳號與登入」。
- **成員介紹**：成員基本資料、照片、Markdown 履歷與履歷 PDF。
- **求職紀錄**：實習 / 正職心得與時程表，支援匿名發表、附件上傳與線上預覽（office 檔走 OnlyOffice 轉 PDF）。
- **活動紀錄 `/events`**：聚餐、出遊、比賽與講座的照片與文字紀錄，依日期排列並可依年份 / 標籤篩選。
- **留言與愛心**：求職紀錄與活動紀錄皆可留言、按愛心並查看按讚名單。留言以純文字呈現，只有作者本人能編輯，管理員可刪除。
- **審核佇列 `/review`**：成員發表的求職 / 活動紀錄先進入待審核狀態，管理員核可後才公開；待審核內容只有作者本人與管理員看得到。
- **設定頁 `/settings`**：管理員可改帳密、管理成員與角色、發註冊邀請、設定 Discord 伺服器、調整外觀資源與系統限制。

## 技術棧

| 層 | 技術 |
|---|---|
| 前端 | Vue 3（Composition API + `<script setup>`）、Vue Router、Pinia、Element Plus、md-editor-v3、cropperjs、DOMPurify |
| 後端 | FastAPI、SQLAlchemy 2.x、Pydantic v2、SlowAPI（rate limit）、httpx + PyJWT（OnlyOffice 整合） |
| 資料庫 | PostgreSQL 17 + Alembic（自動搬移舊 SQLite） |
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
│       ├── models/           # user / member / job / event / job_attachment / post_status
│       │                     # / app_config / site_setting / pending_discord_link / registration_invite
│       ├── schemas/          # Pydantic schemas
│       ├── routers/          # auth / members / jobs / events / job_comments / job_likes
│       │                     # / event_comments / event_likes / job_attachments / event_photos
│       │                     # / timeline / stats / settings / internal
│       └── core/             # config / deps / security / post_visibility / rate_limit / attachments
│                             # / office_convert / runtime_config / audit_log / search_query
│                             # / member_display / job_serialize / discord_oauth / discord_link / discord_register
├── frontend/                 # Vue 3 + Vite 前端
│   └── src/
│       ├── views/            # Home / Login / Members / Jobs / Events / Settings
│       ├── layouts/          # AuthLayout（navbar + outlet）
│       ├── components/       # 共用對話框、TimelineFeed、MarqueeText、CommentThread、LikeButton、LikersDialog 等
│       │   ├── jobs/         # 求職頁元件（卡片 / 篩選 / 排序 / 附件管理）
│       │   ├── events/       # 活動頁元件（時間軸 / 詳情 / 表單 / 照片管理）
│       │   ├── members/      # 成員頁元件（表單 / 照片格 / 履歷檢視）
│       │   └── settings/     # 設定頁的各區塊
│       ├── composables/      # 可重用邏輯（useDeleteWithPassword / useUrlQuerySync / useDialogRouteSync / useMediaQuery / useOutsideClick / 各頁專屬…）
│       ├── router/
│       ├── stores/           # Pinia：auth + jobs/events/members 清單（createListStore SWR 快取）
│       ├── api/              # axios 包裝
│       └── utils/            # attachmentTree / searchQuery / relativeTime / safeId / apiError / useCounter
├── nginx/                    # 容器內前端 nginx 設定
├── data/                     # bind mount：PostgreSQL + uploads + logs（已 gitignore）
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
bash scripts/deploy.sh

# 背景跑：
docker compose up -d --build

# 看 log：
docker compose logs -f

# 結束（保留資料庫與上傳檔）：
docker compose down
```

開瀏覽器到 [http://localhost:8081/](http://localhost:8081/)。

### 服務拓樸

| 服務 | 鏡像來源 | 對外 port | 內部 |
|---|---|---|---|
| `frontend` | `frontend/Dockerfile`（multi-stage：node build → nginx serve） | `8081:8080` | 服務 `dist/` + 反代 `/api` → backend |
| `backend` | `backend/Dockerfile`（python:3.13-slim） | 不對外 | `:8000`，由 frontend nginx 反代 |
| `onlyoffice` | `onlyoffice/documentserver:8.2` | 不對外 | `:80`，僅在 compose network 內由 backend 呼叫 |
| `postgres` | `postgres:17` | `127.0.0.1:5432` | PostgreSQL，持久化於 `data/postgresql/` |
| `db-init` | `backend/Dockerfile` | 不對外 | 一次性準備目錄與持久化連線密碼 |
| `adminer` | Adminer 6.1.1 | `8119:8080` | 沿用 `SQLITE_WEB_PASSWORD` 的資料庫管理介面 |
| `./data` | bind mount | — | 掛在 backend `/data`，存 PostgreSQL、舊 SQLite 備份與 `uploads/`、`logs/` |

既有 Jenkins CD 會自動執行 `scripts/deploy.sh`，不需要新增 secret、修改 `.env` 或手動執行 migration。首次切換會停寫、保留 SQLite 完整快照、逐表驗證後匯入 PostgreSQL；後續部署沿用 PostgreSQL 資料。API、登入 cookie、Bot token 與上傳檔路徑維持不變。

完整流程、資料位置、失敗重試與還原方式見 [PostgreSQL 部署與資料保留](docs/postgresql-migration.md)。舊 sqlite-web 已由 Adminer 取代，沿用 8119 與 `.env` 中的 `SQLITE_WEB_PASSWORD`。Adminer 發布主機 `8119`，供另一台 nginx 反向代理；PostgreSQL 只綁定 `127.0.0.1:5432`；[Adminer 與 HeidiSQL 連線方式](docs/postgresql-migration.md#adminer-與-heidisql)。

### 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `SESSION_SECRET` | 是 | 簽 session cookie，請用長亂數 |
| `SESSION_MAX_AGE_SECONDS` | 否 | 預設 `86400`（一天） |
| `SESSION_SECURE` | 否 | 預設 `false`。正式站走 HTTPS 時設 `true`，session cookie 才會帶 `Secure`（只透過 HTTPS 送）。純 HTTP 下開 `true` 會導致 cookie 不回送、登不進去 |
| `CORS_ORIGINS` | 否 | 同源部署用不到；保留 sane default |
| `SEED_ADMIN_USERNAME` / `SEED_ADMIN_PASSWORD` | 是 | 首次啟動的 admin 帳號 |
| `SEED_VIEWER_USERNAME` / `SEED_VIEWER_PASSWORD` | 是 | 首次啟動的 viewer 帳號 |
| `ONLYOFFICE_JWT_SECRET` | 是 | backend 與 OnlyOffice 之間 JWT 簽章密鑰；`python -c "import secrets; print(secrets.token_urlsafe(32))"` 生 |
| `DISCORD_CLIENT_ID` / `DISCORD_CLIENT_SECRET` | 否 | Discord OAuth 應用憑證。留空則停用 Discord 登入（只剩密碼登入） |
| `DISCORD_REDIRECT_URI` | 否 | OAuth callback，須為公開網址且與 Discord 應用設定**完全一致**，如 `https://<域名>/api/auth/discord/callback` |
| `DISCORD_GUILD_ID` | 否 | 初始允許登入的 Discord 伺服器 ID；之後可在設定頁改（DB 值優先） |

`UPLOADS_DIR`、`ONLYOFFICE_INTERNAL_URL`、`BACKEND_INTERNAL_URL` 由 `docker-compose.yml` 直接寫死，平常不用手動設。

## 資料庫遷移（Alembic）

Schema 變更走 Alembic，沒有自動 `create_all`。每次啟動 `init_db.py` 會自動 `alembic upgrade head` 把資料庫帶到最新版；從既有 SQLite 升級也會自動搬移與驗證。

### 一般工作流程

| 情境 | 指令 |
|---|---|
| 全新環境部署 | `docker compose up -d --build`（`init_db` 會自動 upgrade 到最新） |
| 改了 `app/models/*.py` | `docker compose run --rm backend alembic revision --autogenerate -m "描述"`，**檢查產生的檔案再 commit**，下次啟動就會帶上 |
| 想看目前的版本 | `docker compose exec backend alembic current` |
| 想看完整歷史 | `docker compose exec backend alembic history` |
| 回退一版（小心） | `docker compose exec backend alembic downgrade -1` |

> **⚠️ Autogenerate 不是萬靈丹。** Alembic 會猜測 column add / drop / rename，但抓不到 server_default 變化、複雜的 enum 值新增、或某些 SQLite ALTER 限制。產生 migration 後**一定要打開檔案手動檢查**再 commit。

### SQLite 搬移與測試環境

來源 SQLite 必須有 Alembic revision；既有 `0028`～`0030` 資料庫會自動在副本升級、匯入，原檔保留。無 revision 的古老資料庫會停止搬移，避免猜測 schema 造成遺失。

CI 使用 PostgreSQL 17。一般測試在每個 worker 的獨立 schema 執行一次完整 migrations，每項測試後清空資料並重設流水號；遷移、真實 HTTP、並行寫入與 SQLite 搬移測試保留各自的獨立 schema。執行方法見 [測試說明](docs/postgresql-migration.md#測試)。

## 帳號與登入

三種角色，兩條登入路徑：

| 角色 | 登入方式 | 權限 |
|---|---|---|
| `admin` | Discord OAuth 或密碼 | 全部增刪改查；在 `/settings` 管理成員與帳號、發成員註冊邀請、設定 Discord 伺服器與系統限制。成員可被提權為 admin，此時走 Discord 登入、沒有自己的密碼 |
| `member` | Discord OAuth | 瀏覽全部內容、發自己的求職／活動紀錄（進審核佇列）、編修自己的個資 |
| `viewer` | 密碼 | 僅查（過渡期的舊唯讀帳號） |

- **admin / viewer** 由 `backend/app/init_db.py` 依 `.env` 的 `SEED_*` 建立，走密碼登入（登入只認密碼、不問 username，所以兩者密碼必須不同；UI 改密碼時會擋撞號）。

> **⚠️ 登入頁的密碼表單預設是隱藏的。** Discord 是唯一可見的登入路徑；密碼表單仍在 DOM 裡，但 `Login.vue` 用一個寫死的 `showPasswordLogin = ref(false)` 把它 `v-show` 掉。這是**刻意**的 break-glass 設計，不是遺留垃圾 —— Discord 掛掉時，開發者工具把那個元素的 `display` 清掉就能用：
>
> ```js
> document.querySelector('[data-test="password-login"]').style.display = ''
> ```
>
> 後端的密碼登入端點從未關閉，所以這只是 UI 層的隱藏，不是安全邊界。
>
> 另外：「哪一個帳號才是**那個** admin」由 `app/core/deps.py` 的 `password_account_by_role()` 唯一決定（條件是「角色相符**且**有密碼」）。因為 Discord 管理員身上沒有密碼，這條規則才能在有多位管理員時仍然指向種子帳號。任何要解析憑證帳號的程式碼都必須走它，不能只用角色去查。
- **member** 走 **Discord OAuth**：管理員在 `/settings` 產生一次性註冊邀請連結（48 小時、單次使用），新成員用該連結經 Discord 授權後建立 member 帳號並補完個資；之後每次登入都會即時重驗 Discord 伺服器成員資格（離開伺服器即失去存取）。Discord 相關設定見上方環境變數表，留空則停用 Discord 登入、只剩密碼登入。

admin / viewer 的初始 username／密碼來自 `.env`：

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
> - 若要完全重建環境，先停止服務並備份整個 `data/`；不要只刪 SQLite，正式資料已在 PostgreSQL。

登入只認密碼（不問 username），所以兩個帳號的密碼必須不同；UI 在改密碼時會擋住撞號。

## Discord 活躍度資料收集

Bot 可透過 `POST /api/activity/batches` 每五分鐘批次寫入文字訊息事件與語音取樣。包含 migration、群組限定的 Bot 憑證、重送去重與整批交易；目前提供資料收集，統計圖表後續加入。

部署方式、憑證建立／撤銷、完整欄位、curl 與 Python 範例請見 [Discord 活躍度資料寫入 API](docs/activity-ingestion.md)。

## 自動備份到雲端（rclone）

排程腳本 [scripts/pyweb-backup.sh](scripts/pyweb-backup.sh) 使用 PostgreSQL `pg_dump` 建立一致的資料庫備份，驗證 dump 目錄後，連同 uploads、logs、密碼、origin 與 SQLite 備份打包、上傳，再清除過期 archive。既有 cron 與 rclone 參數不需改動。

運作中的 `data/postgresql/` 不會直接複製。附件仍為 live copy；若要求資料庫與附件完全同時間點，備份期間需停止 backend 寫入。

### 一次性設定（host 端）

```bash
# 1. 安裝
sudo apt install rclone

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
[20260505-070000] Dumping PostgreSQL...
[20260505-070000] Copying uploads and recovery metadata...
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
| `PYWEB_DATA_DIR` | `./data` | 含 PostgreSQL / uploads / logs / 遷移備份的目錄 |
| `RCLONE_REMOTE` | `gdrive:pyweb-backups` | rclone remote + 資料夾 |
| `RETENTION_DAYS` | `30` | 保留幾天的備份；超過會被 `rclone delete` 清掉 |

### Restore

備份含 `data/postgres.dump` 與附件／憑證，不含運作中的 PGDATA。還原時先停止服務、保留原 data、解壓 archive、啟動 postgres，成功執行 `pg_restore` 後才啟動 backend。完整指令見 [備份與還原](docs/postgresql-migration.md#備份與還原)。

### Secret 守則

- **絕對不要 commit `~/.config/rclone/rclone.conf`** — 內含 OAuth refresh token，外洩等同 Drive 永久存取權；萬一外洩到 console.cloud.google.com 撤銷該 client、重跑 `rclone config`
- 若用了 `crypt` remote，密碼也在同一個檔案裡（rclone 用 `obscure` 編碼，**不是加密**）
- public repo 可用 `gitleaks` / `trufflehog` 掃 history 確認沒有歷史 commit 不小心混進 token
