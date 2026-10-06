# 社群活躍度

登入後開啟 `/activity`，或點導覽列「活動」旁的「活躍度」。首頁也有入口。

## 指標與查詢

- 文字訊息：每筆 `message_events` 計 1 則，依 `sent_at` 統計。
- 語音參與：每筆 `voice_samples` 計 1 個人分鐘，依 `sampled_at` 統計。這是頻道內的估計參與時間，不是實際發言時長；掃描間隔不同時仍依目前 Bot 的每筆一分鐘契約計算。
- 訊息與語音分開呈現，不合併為任意加權的貢獻分數。
- 活躍成員：符合條件且有任一訊息或語音紀錄的 Discord 使用者去重計數。
- 活躍日：符合條件且有任一紀錄的日期數。每日平均值以整個日期範圍（含無活動日）為分母。
- 所有圖表、摘要、排行均共用已套用的條件；圖表的訊息／語音切換不需重新查詢。

可選 1 至 366 天（含首尾日期）、時區、每日小時範圍、星期、最多 50 位成員及 50 個頻道。日期以所選時區解讀，預設台北。開始小時包含、結束小時不包含；18–24 點包含 23:59，排除隔日 00:00。跨午夜範圍如 22–02 點代表各個所選日期中的 00–02 與 22–24 點，星期也按該筆紀錄的當地日期計算。夏令時間切換依 IANA 時區處理。

點選熱圖日期、成員、頻道、時段可深入查詢。條件寫入 URL，重新整理、上一頁及分享網址可重現同一查詢（接收者仍須登入並具備權限）。點「重設」回到近一年、全天、全部成員與頻道。

## 權限與資料來源

`GET /api/activity/options` 提供成員、頻道 ID、紀錄起訖與最近收錄時間。

`GET /api/activity/analytics` 回傳摘要、逐日、逐小時、星期×小時、成員及頻道的彙總。

兩者使用現有 session 登入與完成個人資料檢查。僅查詢設定中的 Discord 群組，不能由請求切換群組；非管理員不包含已停權網站帳號的紀錄。管理員的成員預覽仍沿用專案既有的前端預覽機制。

成員以 `Discord user_id → users.discord_id → members.user_id` 關聯姓名。未註冊成員的資料仍會計入，名稱以完整 Discord ID 顯示。現有資料未保存頻道名稱，因此使用頻道 ID，不額外向 Discord 查詢或推測名稱。

目前零筆紀錄不能區分「沒有活動」與「Bot 尚未回補」，頁面不會生成示意數據。語音歷史比訊息短時，也不推測未收錄的語音時間。

```text
GET /api/activity/analytics?start_date=2026-10-01&end_date=2026-10-05&timezone=Asia%2FTaipei&hour_start=18&hour_end=24
```

多選參數使用重複 key，例如 `user_ids=101&user_ids=102&weekdays=0&weekdays=4`。星期 0 為週一、6 為週日。查詢條件均驗證並綁定 SQL 參數，不提供任意 SQL 執行入口。

## 實作與驗證

沿用 PostgreSQL 現有的 guild/time、guild/user/time 與 guild/channel/time 索引，不新增資料表、不修改 Bot 寫入 API、不需要 migration。兩種來源在資料庫內彙總，使用 `GROUPING SETS` 一次產生各維度結果，不把原始訊息傳到瀏覽器。

前端使用既有 Vue 與 Element Plus、原生 SVG 與 CSS，沒有加入新的圖表套件或外部 CDN。網址條件、非同步查詢取消、空資料、載入及錯誤狀態都有測試。

設計參考：[GitHub 每日貢獻圖](https://docs.github.com/en/account-and-profile/concepts/contributions-on-your-profile)、[Grafana 網址與篩選變數](https://grafana.com/docs/grafana/latest/visualizations/dashboards/build-dashboards/create-dashboard-url-variables/)，配合專案既有靛藍與青綠色系。
