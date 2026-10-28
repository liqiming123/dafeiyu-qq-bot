#!/usr/bin/env python3
"""把 persona/大肥鱼.md 写进 AstrBot 的 personas 表，并把它设为默认人格。

AstrBot 的人格存在 data/astrbot/data_v4.db 的 personas 表里，
WebUI 的「人格」页面改了也是写这里。改完人格文本后跑一次本脚本，
再 `docker compose restart astrbot` 生效。
"""

import io
import pathlib
import sqlite3
import datetime
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PERSONA_FILE = ROOT / "persona" / "大肥鱼.md"
DB = ROOT / "data" / "astrbot" / "data_v4.db"
PERSONA_ID = "大肥鱼"

prompt = io.open(PERSONA_FILE, encoding="utf-8").read().strip()
now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

con = sqlite3.connect(DB)
row = con.execute("select id from personas where persona_id=?", (PERSONA_ID,)).fetchone()
if row:
    con.execute(
        "update personas set system_prompt=?, updated_at=? where persona_id=?",
        (prompt, now, PERSONA_ID),
    )
    print(f"已更新人格 {PERSONA_ID}（{len(prompt)} 字）")
else:
    con.execute(
        "insert into personas (created_at, updated_at, persona_id, system_prompt,"
        " begin_dialogs, tools, skills, custom_error_message, folder_id, sort_order)"
        " values (?, ?, ?, ?, '[]', 'null', 'null', null, null, 0)",
        (now, now, PERSONA_ID, prompt),
    )
    print(f"已创建人格 {PERSONA_ID}（{len(prompt)} 字）")
con.commit()
con.close()
