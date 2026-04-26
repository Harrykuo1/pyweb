# pyweb — 社群成員管理網站

記錄社群成員資料，以及實習／求職心得分享的小型網站。

## 功能

- **登入**：兩組固定帳號（管理員 / 檢視者），server-side session 認證。
- **成員介紹**：表格列出畢業年份、本名、目前就職／就讀、入群時間，可附照片與 Markdown 履歷。
- **實習工作紀錄**：紀錄求職年份、公司、心得（含面試題目、實作、domain 問題）、時程表，可匿名。

## 技術棧

| 層 | 技術 |
|---|---|
| 前端 | Vue 3（Composition API + `<script setup>`）、Vue Router、Pinia、Element Plus、md-editor-v3、DOMPurify |
| 後端 | FastAPI、SQLAlchemy、Pydantic |
| 資料庫 | SQLite |
| 認證 | Server-side session（Starlette `SessionMiddleware`，簽章式 cookie） |

## 專案結構

```
pyweb/
├── backend/        # FastAPI 後端
│   └── app/
│       ├── main.py
│       ├── database.py
│       ├── models/
│       ├── schemas/
│       ├── routers/      # auth / members / internships
│       ├── core/         # security、deps、config
│       └── init_db.py    # 初始化兩組帳號
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
cp .env.example .env   # 填入 SESSION_SECRET 等變數
uvicorn app.main:app --reload
```

預設啟動於 `http://127.0.0.1:8000`，健康檢查：`GET /health`。

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
| `pyweb_data` | named volume | — | 掛在 backend `/data`，存 `pyweb.db` |

backend 容器啟動時會跑 `app/init_db.py`，依 `.env` 內的 `SEED_*` 變數種帳號。再次啟動 init 是冪等的，**不會覆蓋既有密碼**。

### host nginx + venv（無 Docker）

模擬上線環境：把前端 build 成靜態檔，由系統 nginx 在 8080 同時服務靜態資源與反向代理 `/api` 到後端。前端走同源請求，不需要 CORS。

需求：系統已安裝 nginx（`sudo apt install nginx`）。我們的 nginx 跑在非 privileged port（8080）、log/pid 寫到 `/tmp/pyweb-nginx/`，不會動到系統 nginx。

```bash
# 1. build 前端
cd frontend && npm run build && cd ..

# 2. 確保後端在跑
cd backend
SESSION_SECRET=... SEED_ADMIN_USERNAME=... ...   # 填好 .env
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd ..

# 3. 啟動專用 nginx
./nginx/start.sh -g 'daemon on;'

# 結束
./nginx/stop.sh
```

設定檔在 [nginx/pyweb.conf.template](nginx/pyweb.conf.template)，log 在 `/tmp/pyweb-nginx/pyweb-nginx-error.log`。

## 帳號（種子資料）

由 `backend/app/init_db.py` 建立：

| 角色 | 權限 |
|---|---|
| `admin` | 增、刪、改、查 |
| `viewer` | 僅查 |

實際帳號／密碼於初始化時設定（請改寫 `init_db.py` 後再執行，勿將密碼入庫）。
