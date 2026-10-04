# -*- coding: utf-8 -*-
"""审核修复（数据层）：① general 中漏标的跌倒相关题归簇；② 判断题 options 规范化（置空）。

依据：2026-10-04 多专家审核（数学家/统计学家视角的数据质量检查）。
用法：python audit_fix.py [--db path] [--commit]
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from import_dedicated_bank import DEFAULT_DB, SEED, CLUSTER_CN  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 人工判定：general 中与跌倒/六簇相关的题 → 目标簇
RECLASSIFY = {
    37: "morse",    # 慌张步态常见疾病（步态与疾病因素）
    61: "cpr",      # 食团堵塞致噎食
    245: "cpr",     # 预防噎食
    301: "morse",   # 自动态平衡
    302: "morse",   # 坐位平衡功能训练
    368: "morse",   # 画圈步态训练
    574: "morse",   # 近一月摔倒 → 能力等级（跌倒史）
    742: "cpr",     # 易致噎食的食物
    762: "morse",   # 不能进行平衡训练的情况
    776: "cpr",     # 避免噎食的正确做法
    788: "morse",   # 复杂步态训练
    954: "morse",   # 视听觉/平衡功能衰退致安全问题
    958: "cpr",     # 噎食紧急处理体位
    1032: "env",    # 轮椅转移方式选择（辅助器具/转移）
    1087: "morse",  # 静态平衡定义
    1125: "env",    # 防失智老年人坠床
    1126: "env",    # 适老环境预防跌倒
    1141: "morse",  # 步行训练与静态平衡
    1254: "record",  # 意外事件信息录入（含 3 个月内跌倒史）
    1266: "morse",  # 平地步行 50m 无摔倒风险评分
    1323: "record",  # GB 38600 应急预案要求
    1328: "env",    # 社区平衡和功能锻炼运动计划
    1347: "five",   # 跌倒无外伤时的处置（不应急促扶起）
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    c = sqlite3.connect(args.db)
    c.row_factory = sqlite3.Row

    print("=== ① 归簇（general → 六簇）===")
    moved = []
    for qid, cl in RECLASSIFY.items():
        r = c.execute("SELECT id, cluster_id, stem FROM questions WHERE id=?", (qid,)).fetchone()
        if not r:
            print(f"  ? #{qid} 不存在，跳过")
            continue
        if r["cluster_id"] != "general":
            print(f"  ? #{qid} 当前已在 {r['cluster_id']}，跳过")
            continue
        moved.append((qid, cl, r["stem"][:44]))
        if args.commit:
            c.execute("UPDATE questions SET cluster_id=? WHERE id=?", (cl, qid))
    for qid, cl, stem in moved:
        print(f"  #{qid} general → {cl}  {stem}")

    print("\n=== ② 判断题 options 规范化（应为空数组）===")
    bad = list(c.execute("SELECT id, options FROM questions WHERE qtype='判断' AND options NOT IN ('[]','')"))
    print(f"  待修正 {len(bad)} 条")
    if args.commit and bad:
        c.execute("UPDATE questions SET options='[]' WHERE qtype='判断' AND options NOT IN ('[]','')")

    if not args.commit:
        print("\n（dry-run；加 --commit 执行）")
        return

    c.commit()
    print(f"\n✔ 已提交：归簇 {len(moved)} 题、判断题规范化 {len(bad)} 条")
    print("--- 分簇 ---")
    for r in c.execute("SELECT cluster_id, COUNT(*) n FROM questions GROUP BY cluster_id ORDER BY n DESC"):
        print(f"  {str(r['cluster_id']):<10} {r['n']}")

    # seed 同步
    if os.path.abspath(args.db) == os.path.abspath(DEFAULT_DB):
        import re

        def norm(t):
            return re.sub(r"[\s（　）()。，,？?、：:；;·\-—]+", "", (t or "").replace("（　）", ""))

        seed = json.load(open(SEED, encoding="utf-8"))
        idx = {norm(x.get("stem", "")): x for x in seed}
        n_cl = n_opt = 0
        for qid, cl, _s in moved:
            row = c.execute("SELECT stem FROM questions WHERE id=?", (qid,)).fetchone()
            it = idx.get(norm(row["stem"]))
            if it is not None:
                it["cluster"] = CLUSTER_CN[cl]
                n_cl += 1
        for r in c.execute("SELECT stem FROM questions WHERE qtype='判断'"):
            it = idx.get(norm(r["stem"]))
            if it is not None and it.get("options"):
                it["options"] = []
                n_opt += 1
        json.dump(seed, open(SEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"seed 同步：归簇 {n_cl} 条、判断题 options 置空 {n_opt} 条")


if __name__ == "__main__":
    main()
