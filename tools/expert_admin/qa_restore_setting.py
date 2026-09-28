# -*- coding: utf-8 -*-
"""恢复 settings.ai_model 到空基线（测试污染清理）。"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.execute("DELETE FROM settings WHERE key='ai_model'")
d.commit()
print("settings now:", d.execute("select * from settings").fetchall())
d.close()