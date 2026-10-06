# 手動連結尚未加入成員的 Discord 帳號

管理員開啟「設定 → 成員與帳號 → 成員名冊」，編輯「尚未加入」的成員，在「手動連結 Discord 帳號」貼上固定的 Discord 使用者 ID，再按「連結 Discord 帳號」。

取得 ID：在 Discord 開啟開發者模式，右鍵點選目標成員，複製使用者 ID。這是純數字識別碼，不是 `@username` 或群組暱稱；請先確認它屬於該成員。

## 成功後的行為

- 沿用既有 `members.user_id` 與 `users.id`，寫入 `users.discord_id`、清除 `pending_discord_username`，名冊顯示「已加入」。原本成員檔案、角色、照片、履歷及歷史內容保持不變。
- 若該 ID 有已驗證的 `pending_discord_links` 紀錄，優先沿用其名稱並移除該待連結項目；否則使用管理員輸入的使用者名稱，未提供時沿用原待加入名稱。
- 下一次本人透過 Discord OAuth 登入直接依 ID 找到原帳號，並同步最新 Discord 名稱；仍驗證 Discord 身分、群組資格與停權狀態。
- 活躍度原始資料透過同一 Discord ID 自動對應到此成員，不需重新插入。
- 此操作立即生效，編輯視窗中的其他資料仍需按「儲存」。它不會產生被連結者的 session、偽造登入紀錄或切換管理員目前的登入身分。

## API

`POST /api/members/{member_id}/discord-link`，只接受管理員網站 session，Bot Bearer token 不適用。

```json
{
  "discord_id": "123456789012345678",
  "discord_username": "example.handle"
}
```

- `discord_id`：必填字串，1–20 位數字、首位不可為 0；JSON number、暱稱、空值均不接受。
- `discord_username`：選填，最多 64 字，去除前後空白與開頭 `@`。這是顯示資料，不是驗證依據；後續 OAuth 登入會更新。
- `200`：回傳 `MemberResponse`，其中 `account_status` 為 `claimed`、`account_id` 仍為原帳號 ID。
- `401`／`403`：未登入／不是管理員。
- `404`：成員不存在。
- `409`：成員已連結、已停權、沒有待加入帳號，或 Discord ID 已連結其他帳號。不可藉此覆蓋既有身分、合併帳號或恢復停權。
- `422`：欄位或格式錯誤，亦不接受未定義欄位。

寫入使用既有唯一索引與帳號列鎖；同一個帳號不能同時綁定兩個 ID，同一 ID 也不能同時綁定兩個帳號。OAuth 的待加入配對與原有待連結處理同樣鎖定帳號，避免跨入口的覆蓋。

本功能不新增資料表或欄位，不需要新的 DB migration。原本 CD 重新部署即可。線上 API 文件位於 `/settings#api`，內容來源與維護規則見 [API 文件頁](api-documentation.md)。

## 更換已加入成員的連結

編輯已加入成員時，先點「更換 Discord 帳號」。確認提示會說明新帳號將取得此成員的存取權、舊登入將失效；按「確定更改」後才開放 ID 欄位。取消提示不會開放填寫或發出更新請求，關閉並重開編輯視窗需要重新確認。

- `GET /api/members/{member_id}/discord-link`：管理員取得目前 `discord_id`、`discord_username`；未連結時 ID 為 `null`。
- `PATCH /api/members/{member_id}/discord-link`：管理員明確確認後更換。保留原 `User.id`、`Member.id`、角色與資料，清除舊名稱並採用新 ID 的待連結名稱或新輸入名稱。

```json
{
  "discord_id": "223456789012345678",
  "discord_username": "new.example",
  "expected_discord_id": "123456789012345678",
  "confirmed": true
}
```

`expected_discord_id` 必須是剛讀取的原 ID，伺服器在帳號列鎖內比對。已被其他管理員修改、原帳號尚未連結、新 ID 已被占用、新舊 ID 相同或帳號停權均回傳 `409`。`confirmed` 為必填且只接受 JSON 布林 `true`；缺少、`false`、字串或數字均回傳 `422`。成功回傳同一成員的 `MemberResponse`。

更換會增加既有 `password_version`，使該帳號所有既有 session 失效。若管理員修改的是自己，也需要重新登入。OAuth 登入在相同帳號列鎖內再次驗證 Discord ID，並在釋放鎖前取得 session 版本，避免與管理員更換同時發生時簽發錯誤身分的有效 session。

原始訊息與語音資料仍保留各自的 Discord ID，統計姓名改依新的帳號關聯顯示；此功能不搬移原始活動紀錄。初次連結仍使用原 `POST` 端點，其不允許覆蓋既有連結的規則維持不變。讀取與更換同樣不接受 Bot token，且不需新增 DB migration。
