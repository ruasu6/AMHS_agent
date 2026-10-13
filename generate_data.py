"""產生模擬的 AMHS(OHT)搬運紀錄,寫入 SQLite。

資料是假的,刻意埋了三個「可被 Agent 發現」的現象:
1. BAY3 的搬運時間明顯偏長(瓶頸 bay)
2. 早上 8~10 點、晚上 20~22 點是尖峰(搬運量大、時間變長)
3. 少數 OHT 車輛(OHT-07)異常搬運時間特別長
"""
import random
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "amhs.db"
DAYS = 7
SEED = 42

BAYS = ["BAY1", "BAY2", "BAY3", "BAY4", "BAY5"]
STOCKERS = ["STK01", "STK02", "STK03"]
VEHICLES = [f"OHT-{i:02d}" for i in range(1, 13)]
PEAK_HOURS = {8, 9, 10, 20, 21, 22}

# 各 bay 搬運時間基準(秒);BAY3 是瓶頸
BAY_BASE = {"BAY1": 90, "BAY2": 100, "BAY3": 170, "BAY4": 95, "BAY5": 105}

SCHEMA = """
DROP TABLE IF EXISTS transport_log;
CREATE TABLE transport_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    carrier_id    TEXT NOT NULL,      -- FOUP 編號
    lot_id        TEXT NOT NULL,
    from_port     TEXT NOT NULL,      -- 起點(Stocker 或 Equipment Port)
    to_port       TEXT NOT NULL,      -- 終點
    bay           TEXT NOT NULL,      -- 目的地所屬 bay
    vehicle_id    TEXT NOT NULL,      -- OHT 車輛編號
    start_time    TEXT NOT NULL,      -- 命令開始時間 (ISO)
    end_time      TEXT NOT NULL,      -- 搬運完成時間 (ISO)
    transport_sec REAL NOT NULL,      -- 搬運秒數
    status        TEXT NOT NULL       -- COMPLETED / FAILED / TIMEOUT
);
CREATE INDEX idx_start ON transport_log(start_time);
CREATE INDEX idx_bay ON transport_log(bay);
"""


def make_rows():
    rng = random.Random(SEED)
    start_day = datetime(2026, 10, 1)
    rows = []
    for d in range(DAYS):
        for hour in range(24):
            n = rng.randint(180, 240) if hour in PEAK_HOURS else rng.randint(70, 120)
            for _ in range(n):
                t0 = start_day + timedelta(days=d, hours=hour, seconds=rng.randint(0, 3599))
                bay = rng.choices(BAYS, weights=[20, 20, 25, 15, 20])[0]
                vehicle = rng.choice(VEHICLES)
                base = BAY_BASE[bay]
                if hour in PEAK_HOURS:
                    base *= 1.35
                sec = max(20, rng.gauss(base, base * 0.18))
                if vehicle == "OHT-07" and rng.random() < 0.35:
                    sec *= rng.uniform(2.5, 4.0)  # 異常車輛
                r = rng.random()
                status = "COMPLETED"
                if r < 0.01:
                    status = "FAILED"
                elif r < 0.025:
                    status = "TIMEOUT"
                    sec *= 2
                src = rng.choice(STOCKERS + [f"{b}-EQ{rng.randint(1, 8):02d}" for b in BAYS])
                dst = f"{bay}-EQ{rng.randint(1, 8):02d}"
                if src == dst:
                    src = rng.choice(STOCKERS)
                t1 = t0 + timedelta(seconds=sec)
                rows.append((
                    f"FOUP{rng.randint(1, 600):04d}",
                    f"LOT{rng.randint(10000, 99999)}",
                    src, dst, bay, vehicle,
                    t0.isoformat(timespec="seconds"),
                    t1.isoformat(timespec="seconds"),
                    round(sec, 1), status,
                ))
    return rows


def main():
    rows = make_rows()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.executemany(
        "INSERT INTO transport_log (carrier_id, lot_id, from_port, to_port, bay, vehicle_id,"
        " start_time, end_time, transport_sec, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()
    print(f"已產生 {len(rows)} 筆搬運紀錄 -> {DB_PATH}")


if __name__ == "__main__":
    main()
