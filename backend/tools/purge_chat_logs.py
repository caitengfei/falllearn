# -*- coding: utf-8 -*-
"""清理 AI 问答历史（chat_logs）——保留练习/错题/掌握度/积分等真实学习记录。

用途：早期（四栏结构）问答历史会与当前"单答案 + 来源"形态不一致，演示前需清理。
      **只清 chat_logs**；attempts / answers / wrong_records / mastery / points_log /
      study_events / checkins 等学习数据一律不动（真实使用痕迹保留）。

用法：
  python purge_chat_logs.py                        # 查看现状（dry-run）
  python purge_chat_logs.py --yes                   # 清空本地库 chat_logs
  python purge_chat_logs.py --db /opt/falllearn/backend/falllearn.db --yes    # 服务器
  python purge_chat_logs.py --yes --students 1,4     # 仅清指定学生（默认全部）
"""
import argparse
import os
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "falllearn.db")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--students", default="", help="逗号分隔的学生 id；留空＝全部")
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()

    c = sqlite3.connect(args.db)
    c.row_factory = sqlite3.Row
    tot = c.execute("SELECT COUNT(*) FROM chat_logs").fetchone()[0]
    n4 = c.execute("SELECT COUNT(*) FROM chat_logs WHERE answer LIKE '%【岗】%' OR answer LIKE '%【课】%' "
                   "OR answer LIKE '%【赛】%' OR answer LIKE '%【证】%'").fetchone()[0]
    print(f"库：{args.db}")
    print(f"chat_logs 总数 {tot}（其中旧形态四栏记录 {n4}）")
    for r in c.execute("SELECT student_id, COUNT(*) n FROM chat_logs GROUP BY student_id"):
        print(f"   student_id={r['student_id']}: {r['n']} 条")

    ids = [int(x) for x in args.students.split(",") if x.strip().isdigit()]
    where = "1=1"
    params = []
    if ids:
        where = f"student_id IN ({','.join('?' * len(ids))})"
        params = ids

    if not args.yes:
        print("\n（dry-run）加 --yes 执行清理；清理后保留记录预览：")
        for t in ("attempts", "answers", "wrong_records", "mastery", "points_log", "study_events", "checkins"):
            print(f"   {t}: {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}（保留不动）")
        return

    c.execute(f"DELETE FROM chat_logs WHERE {where}", params)
    c.commit()
    print(f"\n✔ 已删除 {c.total_changes} 条 chat_logs（条件：{where}）")
    print(f"   剩余 chat_logs：{c.execute('SELECT COUNT(*) FROM chat_logs').fetchone()[0]}")
    print("   学习记录（不动）：" + "，".join(
        f"{t} {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}"
        for t in ("attempts", "answers", "wrong_records", "mastery", "points_log", "study_events", "checkins")))


if __name__ == "__main__":
    main()
