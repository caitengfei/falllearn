import json, sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r'E:\lilei\platform\backend\falllearn.db')
d.row_factory = sqlite3.Row
for r in d.execute("SELECT qtype, COUNT(*) n, SUM(CASE WHEN options IN ('[]','null','') THEN 1 ELSE 0 END) empty_opt FROM questions GROUP BY qtype"):
    print(dict(r))
for r in d.execute("SELECT id, qtype, options, answer FROM questions WHERE qtype='判断' LIMIT 3"):
    print(dict(r))
for r in d.execute("SELECT id, qtype, options, answer FROM questions WHERE qtype='单选' LIMIT 2"):
    print(dict(r))