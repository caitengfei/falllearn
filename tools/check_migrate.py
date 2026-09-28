import sqlite3
d = sqlite3.connect(r'E:\lilei\platform\backend\falllearn.db')
print('cols_wrong:', [r[1] for r in d.execute('PRAGMA table_info(wrong_records)')])
print('cols_chat:', [r[1] for r in d.execute('PRAGMA table_info(chat_logs)')])
print('idx:', [r[0] for r in d.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")])
print('unique_wrong:', d.execute("SELECT sql FROM sqlite_master WHERE name='idx_wrong_sq'").fetchone())