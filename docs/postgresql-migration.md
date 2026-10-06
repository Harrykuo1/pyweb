# PostgreSQL 部署與資料保留

外部 API 的網址、參數、回應、登入 cookie 和 Bot token 不變。PostgreSQL 使用 17 版，資料在 `data/postgresql/`；上傳檔案維持 `data/uploads/` 原路徑。

## 既有 CD

照原本方式推送及觸發 Jenkins 即可，不需要新增 Jenkins secret、修改 `.env` 或手動執行 SQL。Repo 的 `Jenkinsfile` 會呼叫 `scripts/deploy.sh`：

1. 舊站繼續服務期間先 build。
2. 停止舊容器及 sqlite-web，確保網站、Bot API、影片背景工作都停止寫入。
3. 自動建立持久化密碼、啟動 PostgreSQL，等待資料庫健康。
4. 新 backend 啟動時執行 Alembic；首次部署自動搬移 SQLite。
5. 搬移成功後才啟動 API，CD 等待 healthcheck 通過才成功。

第一次切換有維護時間；Bot 應保留 outbox，失敗後重送。手動部署使用 `bash scripts/deploy.sh`，確保同樣停止所有舊寫入者。不要讓外部程式直接寫入保留的 SQLite。

首次搬移會用 SQLite backup API 取得包含已提交 WAL 的一致快照，放在 `data/migration-backups/sqlite-<identity>.db`。舊版 schema 的 upgrade 只作用在快照的工作副本，原始 `data/pyweb.db` 不會被修改。支援已有 Alembic revision 的舊資料庫，例如 `0028`、`0029`、`0030`；無 revision、未知資料表、外鍵異常或資料型別不相容會停止搬移，不會略過資料或自動清空重建。

所有資料表按外鍵順序匯入，逐表比較筆數及 SHA-256 內容摘要，保留主鍵、微秒 UTC 時間、密碼雜湊、token 雜湊、二進位欄位，以及 SQL NULL／JSON null 的區別，最後校正自增序列。資料與完成標記在同一個 PostgreSQL transaction 提交；失敗會 rollback，可重跑 CD。多個 backend 同時啟動會以 advisory lock 排隊。

## 持久資料

| 路徑 | 用途 |
|---|---|
| `data/postgresql/` | 正在使用的 PostgreSQL 資料及 WAL |
| `data/.postgres-password` | 自動產生的連線密碼，權限 0600；後續部署沿用 |
| `data/.postgresql-origin.json` | 資料庫識別碼與首次匯入各表驗證結果 |
| `data/migration-backups/` | 匯入前的完整 SQLite 快照 |
| `data/pyweb.db` | 保留的原 SQLite，切換後不再更新 |
| `data/uploads/`、`data/logs/` | 原本的上傳檔和 log |

這些都是 bind mount，重建／移除容器不會刪除。密碼與 PostgreSQL 資料由 UID/GID 1000 使用，初始化容器會處理新目錄權限。PostgreSQL 不發布 host port；資料庫管理可用 `docker compose exec postgres psql -U pyweb -d pyweb`。舊的 8119 sqlite-web 服務退役，避免誤改過時資料。

後續部署以 PostgreSQL 的完成標記為準，不會再匯入 SQLite。若 origin 檔存在但 PostgreSQL volume 或標記遺失、識別碼不符，啟動會失敗，避免悄悄回到過時資料。密碼檔遺失也不會自動產生另一組密碼取代原憑證。

請保持足夠磁碟空間，首次搬移同時保留原 SQLite、備份、工作副本，以及新 PostgreSQL 與其 WAL；實際需求取決於索引與欄位大小，不能只用 SQLite 檔案大小推估。

## 驗證與失敗處理

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose exec backend alembic current
docker compose exec postgres psql -U pyweb -d pyweb -c 'SELECT id, identity, completed_at FROM database_origin;'
```

搬移／健康檢查失敗時 Jenkins 會顯示失敗，服務不會帶著部分資料上線。修復磁碟、權限或來源資料問題後，可重跑同一份 CD；原資料和快照仍在。不要用刪除 `data/postgresql/` 或 origin 檔的方式繞過保護。

切換成功且 PostgreSQL 已接受新資料後，**不能直接切回舊 SQLite 或舊版程式**，否則切換後的新增資料不會出現在舊站。此時應修復 PostgreSQL 版本，或從包含最新寫入的 PostgreSQL 備份還原。

## 備份與還原

原本的 cron、`PYWEB_DATA_DIR`、`RCLONE_REMOTE`、`RETENTION_DAYS` 繼續使用。`scripts/pyweb-backup.sh` 改為在 postgres 容器執行 `pg_dump --format=custom`，將 dump、上傳檔、密碼及 origin 檔一起打包。**不複製運作中的 `data/postgresql/`**。資料庫 dump 本身具一致性；若要求資料庫與附件完全同一時間點，請在備份期間停止 backend 寫入。

還原到同一台機器時，先保留目前整份 data，再解開 PostgreSQL 格式的新備份；下例的 archive 名稱請換成實際檔案：

```bash
docker compose down --remove-orphans
mv data "data-before-restore-$(date -u +%Y%m%d-%H%M%S)"
tar xzf pyweb-STAMP.tar.gz
# Archive contains data/postgres.dump, credentials, origin and uploads, but no PGDATA.
docker compose up -d --wait postgres
docker compose exec -T postgres pg_restore -U pyweb -d pyweb --exit-on-error --single-transaction < data/postgres.dump
docker compose up -d --wait
```

`pg_restore` 必須先成功，才啟動 backend。舊的純 SQLite 備份需使用獨立的新 data 目錄走首次搬移流程，不能覆蓋正在使用的 PostgreSQL。PostgreSQL 大版本升級也需要獨立的 dump/restore 或 pg_upgrade 流程，不能直接修改 image 大版本。

## 測試

CI 啟動真正的 PostgreSQL 17。每項 DB 測試使用獨立、測完刪除的 schema，執行完整 Alembic migrations；pytest-xdist 的 workers 不共用資料。測試不連線到正式 `pyweb` DB，也不使用 repo 的 `data/pyweb.db`。

本機可使用記憶體 tmpfs 的測試容器：

```bash
docker run -d --name pyweb-pg-test -e POSTGRES_PASSWORD=test-only -e POSTGRES_DB=pyweb_test -p 127.0.0.1:55432:5432 --tmpfs /var/lib/postgresql/data postgres:17
cd backend
TEST_DATABASE_URL='postgresql+psycopg://postgres:test-only@127.0.0.1:55432/pyweb_test' .venv/bin/pytest -n auto
# After testing:
docker rm -f pyweb-pg-test
```

測試涵蓋全部既有端點的行為、OpenAPI 契約、19 表搬移、舊登入 cookie、Bot token、WAL、重複部署、失敗 rollback／重試、遺失 volume、憑證保存、並行匯入，以及真實 HTTP 的一萬筆寫入與並行去重。SQLite 測試僅用於來源格式與搬移相容性。

### 本次開發環境驗證（2026-10-06）

- Python 3.13、PostgreSQL 17、含 ffmpeg 的容器：後端 1034 項測試全部通過，沒有略過；ruff 檢查通過。
- 前端 88 個測試檔、975 項測試通過，Docker production build 成功。
- 以現有資料的副本先演練，再實際執行部署腳本兩次：19 張表、153 筆資料的內容摘要一致，69 個上傳檔案保持一致。
- 切換前後 9 個主要讀取 API 回應逐 byte 一致，沿用切換前登入 cookie。
- 獨立測試資料的 `pg_dump`／`pg_restore` 實測通過，19 張表的內容及自增序列保留。

以上為本機演練；遠端 Jenkins／GitHub Actions 在合併推送後執行。
