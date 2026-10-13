"""AMHS 搬運瓶頸分析 Agent。

用法:
    export ANTHROPIC_API_KEY=你的key
    python agent.py                      # 互動模式
    python agent.py "哪個 bay 搬運最慢?"  # 單次提問
"""
import json
import sys

import anthropic

from tools import SCHEMA_TEXT, TOOL_FUNCS, TOOLS

MODEL = "claude-sonnet-5-5"
MAX_STEPS = 8  # 限制 Agent 最多呼叫幾輪工具,避免無限迴圈

SYSTEM = f"""你是 AMHS(自動物料搬運系統)的資料分析助理,協助工程師找出搬運瓶頸。
可用工具:run_sql(查資料)、plot_chart(畫圖)、export_excel(匯出報表)。

{SCHEMA_TEXT}

規則:
- 先用 SQL 取得資料,再下結論;不要憑空猜測數字。
- 搬運時間分析請排除 status != 'COMPLETED' 的紀錄,除非使用者問的是失敗/逾時。
- 回答用繁體中文,先講結論,再列關鍵數字,最後給 1~2 個可能原因或建議的後續檢查。
- 你的結論是輔助判斷,需提醒工程師再用現場資料確認。
"""


def ask(client: anthropic.Anthropic, question: str, history: list) -> str:
    history.append({"role": "user", "content": question})
    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=MODEL, max_tokens=2000, system=SYSTEM, tools=TOOLS, messages=history
        )
        history.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        results = []
        for block in resp.content:
            if block.type == "tool_use":
                print(f"  [tool] {block.name}: {json.dumps(block.input, ensure_ascii=False)[:150]}")
                func = TOOL_FUNCS.get(block.name)
                out = func(**block.input) if func else {"error": f"未知工具 {block.name}"}
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(out, ensure_ascii=False, default=str),
                })
        history.append({"role": "user", "content": results})
    return "(已達工具呼叫上限,請把問題縮小一點再問)"


def main():
    client = anthropic.Anthropic(default_headers={"Accept-Encoding": "identity"})
    history: list = []
    if len(sys.argv) > 1:
        print(ask(client, " ".join(sys.argv[1:]), history))
        return
    print("AMHS 搬運分析 Agent(輸入 q 離開)")
    while True:
        q = input("\n你:").strip()
        if q.lower() in ("q", "quit", "exit"):
            break
        if q:
            print("\nAgent:" + ask(client, q, history))


if __name__ == "__main__":
    main()
