"""Agent 可呼叫的工具:唯讀 SQL、畫圖、匯出 Excel。

設計重點(面試可講):
- SQL 只允許單一 SELECT,並用 SQLite 唯讀模式開啟 → 雙重保險避免誤改資料
- 查詢結果限制筆數,避免撐爆模型 context 或拖垮資料庫
- 輸出檔案一律放在 output/ 資料夾
"""
import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).parent
DB_PATH = BASE / "amhs.db"
OUT_DIR = BASE / "output"
MAX_ROWS = 200

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum)\b",
    re.IGNORECASE,
)

SCHEMA_TEXT = """資料表 transport_log(OHT 搬運紀錄,時間為 ISO 字串,例如 2026-10-01T08:15:30):
- id INTEGER 主鍵
- carrier_id TEXT  FOUP 編號
- lot_id TEXT      批號
- from_port TEXT   起點(STK01~03 或 BAYx-EQyy)
- to_port TEXT     終點
- bay TEXT         目的地所屬 bay(BAY1~BAY5)
- vehicle_id TEXT  OHT 車輛(OHT-01~OHT-12)
- start_time TEXT  命令開始時間
- end_time TEXT    搬運完成時間
- transport_sec REAL 搬運秒數
- status TEXT      COMPLETED / FAILED / TIMEOUT
資料範圍:2026-10-01 ~ 2026-10-07。SQLite 語法:小時用 strftime('%H', start_time)。"""


def _connect_readonly():
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def run_sql(query: str) -> dict:
    """執行唯讀 SQL,回傳欄位與資料(最多 MAX_ROWS 筆)。"""
    q = query.strip().rstrip(";")
    if not q.lower().startswith(("select", "with")):
        return {"error": "只允許 SELECT 查詢"}
    if ";" in q or FORBIDDEN.search(q):
        return {"error": "查詢包含不允許的語法(僅限單一 SELECT)"}
    try:
        with _connect_readonly() as conn:
            cur = conn.execute(q)
            cols = [c[0] for c in cur.description]
            rows = cur.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as e:
        return {"error": f"SQL 錯誤:{e}"}
    truncated = len(rows) > MAX_ROWS
    rows = rows[:MAX_ROWS]
    return {"columns": cols, "rows": rows, "row_count": len(rows), "truncated": truncated}


def _to_df(data: dict) -> pd.DataFrame:
    return pd.DataFrame(data["rows"], columns=data["columns"])


def plot_chart(query: str, kind: str, x: str, y: str, title: str, filename: str) -> dict:
    """依 SQL 結果畫 bar 或 line 圖,存成 PNG。"""
    if kind not in ("bar", "line"):
        return {"error": "kind 只能是 bar 或 line"}
    data = run_sql(query)
    if "error" in data:
        return data
    df = _to_df(data)
    if x not in df.columns or y not in df.columns:
        return {"error": f"欄位不存在,可用欄位:{list(df.columns)}"}
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / Path(filename).with_suffix(".png").name
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if kind == "bar":
        ax.bar(df[x].astype(str), df[y])
    else:
        ax.plot(df[x].astype(str), df[y], marker="o")
    ax.set_title(title)
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    plt.xticks(rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return {"saved": str(path)}


def export_excel(query: str, filename: str) -> dict:
    """依 SQL 結果匯出 Excel 報表。"""
    data = run_sql(query)
    if "error" in data:
        return data
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / Path(filename).with_suffix(".xlsx").name
    _to_df(data).to_excel(path, index=False)
    return {"saved": str(path), "row_count": data["row_count"]}


# 給 Claude API 的工具定義
TOOLS = [
    {
        "name": "run_sql",
        "description": "對 AMHS 搬運紀錄執行唯讀 SQL(SQLite),最多回傳 200 筆。需要資料時先呼叫這個。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "單一 SELECT 語句"}},
            "required": ["query"],
        },
    },
    {
        "name": "plot_chart",
        "description": "用 SQL 結果畫 bar 或 line 圖並存成 PNG。",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "kind": {"type": "string", "enum": ["bar", "line"]},
                "x": {"type": "string", "description": "x 軸欄位名稱"},
                "y": {"type": "string", "description": "y 軸欄位名稱"},
                "title": {"type": "string"},
                "filename": {"type": "string"},
            },
            "required": ["query", "kind", "x", "y", "title", "filename"],
        },
    },
    {
        "name": "export_excel",
        "description": "用 SQL 結果匯出 Excel 報表(.xlsx)。",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "filename": {"type": "string"}},
            "required": ["query", "filename"],
        },
    },
]

TOOL_FUNCS = {"run_sql": run_sql, "plot_chart": plot_chart, "export_excel": export_excel}
