# -*- coding: utf-8 -*-
"""Final cleanup audit: verify no EXPERT-ux data remains anywhere."""
import sqlite3, os, sys, glob
sys.stdout.reconfigure(encoding="utf-8")
d = sqlite3.connect(r"E:\lilei\platform\backend\falllearn.db")
d.row_factory = sqlite3.Row
ok = True
def check(label, rows):
    global ok
    print(f"{label}: {len(rows)}")
    for r in rows:
        print("   ", dict(r)); ok = False

check("users EXPERT", d.execute("SELECT id, student_no, name, role FROM users WHERE name LIKE 'EXPERT-%' OR student_no LIKE 'EXPERT%'").fetchall())
check("announcements EXPERT", d.execute("SELECT id, title FROM announcements WHERE title LIKE 'EXPERT-ux%'").fetchall())
check("banners EXPERT", d.execute("SELECT id, title FROM banners WHERE title LIKE 'EXPERT-ux%'").fetchall())
check("trainings EXPERT", d.execute("SELECT id, title FROM trainings WHERE title LIKE 'EXPERT-ux%'").fetchall())
# baseline integrity
print("users:", [(r["student_no"], r["role"], r["enabled"]) for r in d.execute("SELECT student_no, role, enabled FROM users ORDER BY id")])
print("banners sort:", [(r["id"], r["sort"]) for r in d.execute("SELECT id, sort FROM banners ORDER BY sort, id")])
print("announcements total:", d.execute("SELECT COUNT(*) c FROM announcements").fetchone()["c"], "(EXPERT-qa rows belong to QA expert, left intact)")
print("trainings:", [(r["id"], r["title"]) for r in d.execute("SELECT id, title FROM trainings")])
print("enrolls:", d.execute("SELECT COUNT(*) c FROM training_enrolls").fetchone()["c"])
print("questions AI:", d.execute("SELECT COUNT(*) c FROM questions WHERE origin='AI生成'").fetchone()["c"])
# KB files
kb = r"E:\lilei\跌倒-岗课赛证知识库"
left = [p for p in glob.glob(kb + r"\**\*.md", recursive=True) if "EXPERT" in os.path.basename(p)]
print("KB EXPERT files:", left)
# uploads from my tests (I never uploaded images)
up = r"E:\lilei\platform\backend\uploads"
ups = os.listdir(up) if os.path.isdir(up) else []
print("uploads:", len(ups), "(all pre-existing / other experts)" if not any("EXPERT" in x for x in ups) else ups)
print("CLEAN" if ok and not left else "DIRTY")