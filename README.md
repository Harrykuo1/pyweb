# pyweb — 社群成員管理網站

記錄社群成員資料，以及實習／求職心得分享的小型網站。

## 功能

- **登入**：兩組固定帳號（管理員 / 檢視者），JWT 認證。
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

## 帳號（種子資料）

由 `backend/app/init_db.py` 建立：

| 角色 | 權限 |
|---|---|
| `admin` | 增、刪、改、查 |
| `viewer` | 僅查 |

實際帳號／密碼於初始化時設定（請改寫 `init_db.py` 後再執行，勿將密碼入庫）。
