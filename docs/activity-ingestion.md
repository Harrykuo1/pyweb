# Discord 活躍度資料寫入 API

此 API 供 Discord Bot 每五分鐘批次上傳訊息事件與語音取樣。它只負責收集原始資料；統計查詢與圖表尚未加入。

## 部署與資料庫 migration

```bash
docker compose up -d --build
docker compose exec backend alembic current
```

後端啟動時自動執行 migration。此功能的 revision 是 `0030`，接在 `0029` 之後，新增三張表，不修改既有業務資料：

| 表 | 身分／去重依據 | 內容 |
| --- | --- | --- |
| `message_events` | `guild_id` + `message_id` | 成員、頻道、發送時間、回覆對象、文字長度、附件數、接收時間 |
| `voice_samples` | `guild_id` + `user_id` + `sampled_at` | 成員、頻道、實際掃描時間、接收時間 |
| `activity_ingest_tokens` | 自動產生的 `id` | 憑證名稱、可寫入群組、憑證雜湊、建立／撤銷時間 |

若要在非 Docker 環境手動升級，在 `backend/` 設定正確的環境變數後執行 `.venv/bin/alembic upgrade head`。降級至 `0029` 會刪除這三張新表與其中的資料。

## 發給 Bot 的專用憑證

在伺服器上執行，將 `123456789012345678` 換成要收集資料的 Discord 群組 ID：

```bash
docker compose exec backend python -m app.activity_tokens create \
  --guild-id 123456789012345678 --name discord-activity-bot
```

命令回傳 JSON，含 `id`、`guild_id`、`name`、`token`。明文 token 只在建立時顯示；資料庫只存 SHA-256 雜湊。把 token 放在 Bot 程式的環境變數或秘密設定中，不要放進 repo。它只能呼叫資料寫入 API，不能登入網站或取得管理員權限。

列出憑證與撤銷憑證：

```bash
docker compose exec backend python -m app.activity_tokens list
docker compose exec backend python -m app.activity_tokens revoke 1
```

`list` 不回傳明文或雜湊。撤銷後的新請求立即失效。輪替時先建立新 token、更新 Bot，再撤銷舊 token。每張憑證固定綁定建立時的群組，不隨網站 Discord 登入群組設定變更。

## 請求格式

- 方法：`POST /api/activity/batches`
- 標頭：`Authorization: Bearer <token>`、`Content-Type: application/json`
- 本機網址：`http://localhost:8081/api/activity/batches`
- 遠端 Bot：使用網站可連線的 HTTPS 網址加上 `/api/activity/batches`。Bot 不需要網站登入 cookie。
- 每批文字與語音合計 **1–1,000 筆**，JSON 本體上限 **1 MiB**。
- 同一來源 IP 每分鐘上限 **60 次**，足夠五分鐘一次上傳及分批補傳。
- `messages` 與 `voice_samples` 可省略其中一個，但不可同時沒有資料。
- 不接受未定義的欄位，避免意外上傳訊息原文。

把以下內容存成 `batch.json`。所有 Discord ID 都是**十進位數字字串**，不可傳 JSON number；可包含尚未在網站註冊的群組成員。

```json
{
  "guild_id": "123456789012345678",
  "messages": [
    {
      "message_id": "234567890123456789",
      "user_id": "345678901234567890",
      "channel_id": "456789012345678901",
      "sent_at": "2026-10-01T18:03:12.123456+08:00",
      "reply_to_user_id": "567890123456789012",
      "text_length": 18,
      "attachment_count": 1
    }
  ],
  "voice_samples": [
    {
      "user_id": "345678901234567890",
      "channel_id": "678901234567890123",
      "sampled_at": "2026-10-01T18:04:09.987654+08:00"
    }
  ]
}
```

| 欄位 | 規則 |
| --- | --- |
| `sent_at` | 訊息實際送出的時間，不是上傳時間 |
| `sampled_at` | 掃描到成員時的實際時間，保留原始精度，不捨入到分鐘 |
| `reply_to_user_id` | 回覆對象的 Discord 使用者 ID；未回覆或無法解析時傳 `null` 或省略 |
| `text_length` | 必填非負整數，建議統一使用 Unicode code point 數，Python 為 `len(message.content)`；只有附件時為 `0` |
| `attachment_count` | 必填非負整數，Discord 附件的數量，不把連結預覽 embeds 算入附件 |
| `received_at` | 由伺服器產生，Bot 不可傳入 |

所有時間必須是帶時區的 ISO 8601 字串。`Z` 與 `+08:00` 都可用，伺服器統一轉成 UTC 後儲存，保留微秒。SQLite 欄位讀出的字串可能沒有時區後綴，其值仍代表 UTC。拒絕沒有時區、數字型時間戳及超過伺服器現在時間五分鐘的未來時間；歷史補傳不設時間下限。

## 上傳範例

設定 Bot 的 `PYWEB_BASE_URL` 與 `PYWEB_ACTIVITY_TOKEN` 環境變數後：

```bash
curl --fail-with-body \
  -X POST "${PYWEB_BASE_URL%/}/api/activity/batches" \
  -H "Authorization: Bearer ${PYWEB_ACTIVITY_TOKEN}" \
  -H 'Content-Type: application/json' \
  --data-binary @batch.json
```

Python 範例使用標準函式庫，不需額外安裝套件：

```python
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

# Persist this file before uploading. Retrying must use the same IDs/times.
body = Path("batch.json").read_bytes()
request = Request(
    os.environ["PYWEB_BASE_URL"].rstrip("/") + "/api/activity/batches",
    data=body,
    headers={
        "Authorization": "Bearer " + os.environ["PYWEB_ACTIVITY_TOKEN"],
        "Content-Type": "application/json",
    },
    method="POST",
)
with urlopen(request, timeout=30) as response:
    result = json.load(response)
print(result)
# Acknowledge these records in the Bot's persistent outbox only after success.
```

成功回傳 `200`：

```json
{
  "messages": {"inserted": 1, "duplicates": 0},
  "voice_samples": {"inserted": 1, "duplicates": 0}
}
```

整批重送則回傳 `inserted: 0`、`duplicates: 1`。重複筆數包含同一批內的重複項目。每類的 `inserted + duplicates` 等於送入的該類筆數。

## Bot 收集與重試規則

1. 接收到一則新訊息，暫存一筆事件。編輯訊息不當作新訊息；此 API 採首次寫入為準，不會用重送資料覆蓋原始欄位。刪除 Discord 訊息也不自動扣掉既有計數。
2. 每分鐘掃描一次語音頻道；一次掃描使用同一個 `sampled_at`，每位成員最多產生一筆取樣。若 Bot 只收真人，請在收集時排除 Bot；目前表中不另存 Bot 標記。AFK／靜音是否排除由收集程式固定規則，避免中途改變口徑。
3. 將未送出的事件放進**持久化 outbox**，避免 Bot 重啟遺失資料。每五分鐘抓取待送資料，超過 1,000 筆或 1 MiB 就拆批，不要先合併成每人總數。
4. 上傳成功後才確認該批完成。等待回應逾時時，即使伺服器可能已寫入，也可原樣重送；原始 ID、`sent_at`、`sampled_at` 不可改成重試當下的時間。
5. 連線錯誤與 `5xx` 使用指數退避並加入隨機延遲；`429` 至少等待 60 秒再試。避免同時啟動多個 worker 重複採集同一個群組。
6. `401`／`403` 檢查憑證與群組；`413` 拆小批次；`422` 依 `detail` 中的欄位位置修正或隔離錯誤資料，保留原始資料供追查，不要無限重送錯誤批次。

語音去重不使用分鐘桶：同一個人同分鐘的兩個不同掃描時間會存成兩筆。Bot 必須維持每分鐘一次的取樣規則，才可以用「一筆約一分鐘」估算在線時數；停機漏掃不自動補算，也不能視為實際發話時間。相同瞬間以不同時區格式上傳仍視為同一次取樣。

## 原子性與錯誤回應

文字與語音在同一筆資料庫交易中提交。格式或權限有問題時整批不寫入；資料庫寫入失敗時整批回滾。已存在的來源事件維持原資料，只有新的事件會新增。

| 狀態碼 | 意義 |
| --- | --- |
| `200` | 已提交，包含新增與重複筆數 |
| `401` | 缺少、錯誤或已撤銷的 Bot token；網站登入不能取代 Bot token |
| `403` | Token 不允許寫入指定群組 |
| `413` | 超過 1 MiB |
| `422` | 格式錯誤、批次為空、筆數超限、時間或欄位無效 |
| `429` | 超過每分鐘請求上限 |
| `5xx` | 服務或資料庫錯誤，可保留原批次重試 |

## 索引與後續統計

原始資料保留群組、使用者、頻道與發生時間，並為群組時間、群組成員時間、群組頻道時間查詢建立索引。後續可依台灣時區切日期與每日時段，分析訊息量、回覆關係、語音取樣數與共同在線時間；目前沒有新增彙總表或查詢端點。
