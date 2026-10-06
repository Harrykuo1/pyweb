# API 文件頁與維護規則

管理員登入後，在「設定 → 我的帳號下方的 API 文件」開啟 `/settings#api`。

## 使用方式

- **快速開始**：API base URL、Bot Bearer token 與網站 session 的差別、`docker compose exec`／`docker exec` 建立 token、清單、撤銷、批次上傳、去重重試、頻道名稱同步、統計查詢與常見錯誤。
- **API 參考**：從目前部署版本的 OpenAPI 取得所有 `/api/` 端點，可依路徑／功能／HTTP 方法搜尋，查看參數、請求欄位、回應與完整資料結構，也能下載 OpenAPI JSON。
- 文件是查閱與複製範例的入口，沒有直接建立 token 或執行寫入 API 的按鈕。範例只有示意值，不含真實憑證；建立 token 指令要在部署主機執行。
- 新文件資料端點 `GET /api/admin/api-docs` 使用網站 session 且要求管理員權限；未登入回傳 401、非管理員回傳 403，回應禁止快取。Bot token 不能讀取此頁資料。
- 原有業務 API 的存取權限不變。文件頁的管理員限制不代表所有列出的業務 API 都只限管理員；依各端點原本的公開、登入、角色與資源規則驗證。
- `/internal/` 屬於 Compose 內部 OnlyOffice 流程，不列入對外目錄。此功能未修改原本 FastAPI 開發用文件路徑的設定。

## 單一內容來源

- 快速開始與手寫端點說明：[`backend/app/docs/api-guide.json`](../backend/app/docs/api-guide.json)。後端 image 的 `COPY app/` 會一併包含，勿把另一份指南硬編碼到 Vue。
- API 路徑、參數、欄位型別與回應：FastAPI `app.openapi()`，隨目前程式碼產生，不手動維護第二份端點清單。
- Vue 呈現：[`ApiDocsSection.vue`](../frontend/src/components/settings/ApiDocsSection.vue)。使用純文字及程式碼區塊顯示；不執行文件內容。
- Bot 完整契約：[活躍度寫入 API](activity-ingestion.md)。圖表與統計：[社群活躍度](activity-dashboard.md)。

## 每次 API 變更都要同步

新增、修改或移除任何對外 API 時，必須在**同一個 commit** 完成：

1. 更新路由、Pydantic request／response schema，以及必要的參數描述、範例與錯誤說明，讓「API 參考」正確反映目前實作。
2. 對新增端點，在 `api-guide.json` 的 `endpoint_notes` 加上 `METHOD /api/path`、驗證方式與用途；對修改／移除端點同步修正或刪除說明。不可只依賴自動生成的路徑清單。
3. 若影響呼叫方式、驗證、token、批次限制、去重、時間意義或重試方式，同步更新指南的 `sections` 與相關 `docs/*.md`，提供可複製且使用示意值的請求／回應。
4. 不把真實 token、session cookie、密碼或個資放入文件與測試。不得在文件暗示網站 cookie 與 Bot token 可互換。
5. 更新契約與權限測試，確認管理員可讀、其他身分不可讀，範例與實際驗證規則一致；新增端點必須有文件說明。前端有變更時驗證入口、搜尋、程式碼複製與窄螢幕版面。

舊有網站 API 已由 OpenAPI 完整列出，專用串接指南目前涵蓋活動資料寫入、頻道名稱與統計查詢。後續新端點須新增人工說明，既有端點修改時也要補齊；內部服務例外應在文件中明確標示原因。
