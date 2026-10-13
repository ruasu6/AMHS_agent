# AMHS 搬運瓶頸分析 Agent

用自然語言問問題,Agent 自動寫 SQL、查詢、畫圖、匯出 Excel,協助工程師快速找出 AMHS(OHT)搬運瓶頸。

> 資料為**模擬資料**(`generate_data.py` 產生),不含任何公司真實資料。

## 為什麼做這個

AMHS 每天產生大量搬運紀錄。要找瓶頸,工程師通常得手寫 SQL、貼進 Excel、做圖,耗時又依賴個人經驗。
這個 Agent 把「問問題 → 查資料 → 看圖 → 出報表」縮成一句話。

## 架構

```
使用者提問 ──► agent.py (Claude tool-use 迴圈)
                  │
                  ├─► run_sql      唯讀 SQL(單一 SELECT、限 200 筆)
                  ├─► plot_chart   bar / line 圖 → output/*.png
                  └─► export_excel 報表 → output/*.xlsx
                  │
               amhs.db (SQLite,transport_log)
```

## 快速開始

```bash
pip install -r requirements.txt
python generate_data.py              # 產生約 2 萬筆模擬搬運紀錄
export ANTHROPIC_API_KEY=你的key
python agent.py                      # 互動模式
python agent.py "哪個 bay 的搬運時間最長?"
```

## 範例問題

- 哪個 bay 的平均搬運時間最長?畫成長條圖
- 尖峰時段是幾點?哪個時段搬運最慢?
- 有沒有搬運時間特別異常的 OHT 車輛?
- 匯出 BAY3 搬運時間超過 300 秒的紀錄成 Excel
- TIMEOUT 比例最高的是哪個 bay?

資料內刻意埋了三個現象,可驗證 Agent 是否找得到:
**BAY3 偏慢**、**8~10 點與 20~22 點尖峰**、**OHT-07 車輛異常**。

## 安全設計

| 風險 | 對策 |
|---|---|
| Agent 產生會改資料的 SQL | 只允許單一 SELECT;關鍵字黑名單;SQLite 以 `mode=ro` 唯讀開啟 |
| 查詢過大拖垮資料庫 | 每次最多回傳 200 筆 |
| Agent 無限迴圈 | 單次提問最多 8 輪工具呼叫 |
| Agent 答錯 | System prompt 要求先查資料再下結論,並提醒工程師以現場資料確認 |

## 接到真實環境時的調整

- 資料來源改為 Oracle / MS-SQL:替換 `tools.py` 的連線與 SQL 方言(`strftime` → `TO_CHAR` / `DATEPART`)
- 資料庫帳號只給 SELECT 權限,並限制可查的 view,不要直接開原始表
- 加上異常警示(例如搬運時間 > 平均 + 3σ 時通知)
- 用 Streamlit 做簡單網頁,讓 MFG / CIM 同仁也能直接使用

## 檔案

| 檔案 | 說明 |
|---|---|
| `generate_data.py` | 產生模擬資料到 `amhs.db` |
| `tools.py` | 工具實作與工具定義 |
| `agent.py` | Agent 主程式 |
