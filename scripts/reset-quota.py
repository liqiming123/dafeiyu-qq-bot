#!/usr/bin/env python3
"""把大肥鱼今天的回复额度清零（手动重置用）。

额度计数存在 AstrBot 数据库的 preferences 表里（key 为 quota / out）。
改完需要重启 astrbot 才生效：

    docker compose restart astrbot
"""

import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "astrbot" / "data_v4.db"

con = sqlite3.connect(DB)
n = con.execute("delete from preferences where key in ('quota', 'out')").rowcount
con.commit()
con.close()
print(f"已清除额度状态（{n} 行）。运行 `docker compose restart astrbot` 生效。")
