# -*- coding: utf-8 -*-
"""跌倒专项题库导入：解析知识库两份「跌倒专项」练习题文档 → 标注六簇 → 入 questions 表。

来源（均为项目知识库自有资料，含答案）：
  1) knowledge/04-证/养老护理员理论练习题（跌倒专项120题）.md   （实际 123 题）
  2) knowledge/04-证/健康照护师理论练习题（跌倒专项160题）.md   （实际 163 题）

用法：
  python import_dedicated_bank.py                  # dry-run：只统计与抽样，不写库
  python import_dedicated_bank.py --commit          # 写入本地库 + 追加 seed JSON
  python import_dedicated_bank.py --db /opt/falllearn/backend/falllearn.db --commit   # 写服务器库

标注策略（v2，2026-10-04 修正）：
  - **只用题干匹配**（不含选项——选项中的"骨折/拐杖"等词曾污染分类）；
  - 优先级：cpr > fracture > record > env > morse > five（五步处置最后兜底，其词最宽）；
  - 与现有库重复的题：若原记录在 general，则**补标**为六簇（不新增重复行）。
"""
import argparse
import json
import os
import re
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KB = os.path.join(ROOT, "knowledge", "04-证")
SEED = os.path.join(ROOT, "backend", "seed", "questions_seed.json")
DEFAULT_DB = os.path.join(ROOT, "backend", "falllearn.db")
ORIGIN = "跌倒专项题库"
CLUSTER_CN = {"morse": "Morse评估", "env": "环境防控", "five": "五步处置",
              "fracture": "骨折识别", "record": "记录上报", "cpr": "CPR启动"}

SOURCES = [
    ("养老护理员理论练习题（跌倒专项120题）.md", "04-证/养老护理员理论练习题（跌倒专项120题）.md"),
    ("健康照护师理论练习题（跌倒专项160题）.md", "04-证/健康照护师理论练习题（跌倒专项160题）.md"),
]

# 优先级：越靠前越特异
RULES = [
    ("cpr", ["心肺复苏", "胸外按压", "人工呼吸", "心脏骤停", "呼吸心跳骤停", "脉搏消失", "除颤", "aed",
             "气道", "噎食", "窒息", "海姆立克"]),
    ("fracture", ["骨折", "股骨颈", "髋部", "夹板", "骨擦", "异常活动", "肢体固定", "脊柱", "颈椎", "腰椎",
                  "轴线", "平托", "搬运", "担架", "畸形", "颅骨", "清水样", "耳鼻", "安全转运"]),
    ("record", ["记录", "报告", "上报", "不良事件", "登记", "交接班", "交班", "填写", "文书", "事件分析",
                "根因", "报告制度"]),
    ("env", ["环境", "地面", "照明", "扶手", "防滑", "滑倒", "卫生间", "浴室", "床栏", "床档", "床单位",
             "防滑垫", "夜灯", "通道", "障碍物", "助行器", "拐杖", "手杖", "辅助器具", "轮椅", "防滑鞋",
             "杂物", "物品摆放", "呼叫铃", "呼叫器", "门槛", "光线"]),
    ("morse", ["步态", "morse", "评估", "量表", "风险等级", "风险分层", "高危", "中危", "低危", "风险识别",
               "危险因素", "评估时机", "复评", "评分", "打分", "风险因素", "警示标识", "风险信号",
               "镇静催眠", "药物因素", "生理因素", "高风险人群", "危险性", "死亡率", "控制能力",
               "内在因素", "健康危险因素"]),
    ("five", ["跌倒后", "跌倒发生", "摔倒", "坠床", "扶起", "意识", "搬动", "制动", "呼救", "急救", "体位",
              "平卧", "头偏", "冷敷", "出血", "肿胀", "疼痛", "伤情", "安抚", "保暖", "就地", "不要急于",
              "初步处置", "应急处置", "减少活动", "观察伤情", "紧急处理", "应对方法", "防护要点",
              "应对职责", "跌倒基本知识", "处理方式", "创伤", "急性期", "伤后"]),
]


def norm(text):
    """归一化题干用于去重比对。"""
    return re.sub(r"[\s（　）()。，,？?、：:；;·\-—]+", "", (text or "").replace("（　）", ""))


def cluster_of(text):
    for name, kws in RULES:
        if any(k in text for k in kws):
            return name
    # 兜底：题干含"跌倒"语境时按语义细分（全部题目均为跌倒专项，兜底不引入跨技能点噪声）
    if "预防跌倒" in text or "防跌倒" in text:
        return "env"
    if "跌倒风险" in text or "跌倒评估" in text:
        return "morse"
    if "跌倒" in text:
        return "five"
    # 职责/措施/知识要求类（题干短短未含"跌倒"，但均属跌倒专项题）
    if "预防措施" in text or "防范措施" in text:
        return "env"
    if any(k in text for k in ("工作内容", "应掌握", "应能", "知识要求", "可采取的措施", "诊断", "包扎")):
        return "five"
    return None


def difficulty_of(qtype, text):
    if qtype == "多选":
        return 2
    if qtype == "判断":
        return 1 if len(text) < 30 else 2
    if re.search(r"(不包括|除外|错误|不属于|不正确|不是)", text):
        return 2
    if re.search(r"(一位|某位|老人在|老年人.*发生|跌倒后|案例|李奶奶|王奶奶)", text):
        return 2
    if re.search(r"\d+\s*(分钟|分|秒|次|条|项|个|度|小时)", text):
        return 2
    return 1


def parse_doc(path):
    out = []
    for ln in open(path, encoding="utf-8").read().split("\n"):
        s = ln.strip()
        m = re.match(r"^(\d{1,3})[.、]\s*(.+)$", s)
        if not m:
            continue
        num, body = int(m.group(1)), m.group(2).strip()
        mj = re.match(r"^(.*?)[（(]\s*([√×xX])\s*[)）][。\s]*$", body)
        if mj and "→" not in body:
            text = mj.group(1).strip()
            ans = "A" if mj.group(2) in "√xXx" else "B"
            out.append(dict(num=num, qtype="判断", stem="（　）" + text, options=[], answer=ans))
            continue
        ma = re.search(r"→\s*\*\*([A-F]{1,4})\*\*\s*$", body)
        if not ma:
            continue
        ans = ma.group(1)
        qpart = body[:ma.start()].strip()
        parts = re.split(r"\s+([A-F])[.、]\s*", qpart)
        if len(parts) < 5:
            continue
        stem = parts[0].strip()
        opts = [parts[i + 1].strip() for i in range(1, len(parts), 2)]
        qtype = "多选" if len(ans) > 1 else "单选"
        out.append(dict(num=num, qtype=qtype, stem=stem, options=opts, answer=ans))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    exist = {norm(r["stem"]): (r["id"], r["cluster_id"]) for r in
             conn.execute("SELECT id, stem, cluster_id FROM questions")}
    maxid = conn.execute("SELECT COALESCE(MAX(id),0) FROM questions").fetchone()[0]
    print(f"库：{args.db}\n现有题 {len(exist)} 道（max id {maxid}）\n")

    all_new, recluster, skipped_dup, skipped_cluster = [], [], 0, []
    for fn, rel in SOURCES:
        rows = parse_doc(os.path.join(KB, fn))
        print(f"[{fn}] 解析出 {len(rows)} 题")
        for r in rows:
            key = norm(r["stem"])
            cl = cluster_of(r["stem"])          # 只用题干
            hit = exist.get(key)
            if hit:
                qid, old_cl = hit
                if cl and (old_cl in ("general", "", None)):
                    recluster.append((qid, old_cl, cl, r["stem"][:42]))
                else:
                    skipped_dup += 1
                continue
            if cl is None:
                skipped_cluster.append((fn, r["num"], r["stem"][:44]))
                continue
            exist[key] = (maxid, cl)
            r["cluster_id"] = cl
            r["difficulty"] = difficulty_of(r["qtype"], r["stem"])
            r["source_doc"] = f"{rel}（第 {r['num']} 题）"
            all_new.append(r)

    from collections import Counter
    cnt = Counter(r["cluster_id"] for r in all_new)
    print(f"\n可入库新题：{len(all_new)}　重复跳过 {skipped_dup}　可补标(general→六簇) {len(recluster)}"
          f"　规则未命中 {len(skipped_cluster)}")
    print("新题分簇：", dict(cnt))
    print("题型：", dict(Counter(r["qtype"] for r in all_new)))
    if recluster:
        print("\n--- 补标（原 general → 六簇）抽样 8 ---")
        for qid, o, n, stem in recluster[:8]:
            print(f"  #{qid} {o}→{n}  {stem}")
    if skipped_cluster:
        print("\n--- 待人工归类（未写入）---")
        for fn, num, stem in skipped_cluster[:20]:
            print(f"  [{fn[:10]} #{num}] {stem}")
    print("\n--- 各簇抽样 2 题 ---")
    for cl in ("morse", "env", "five", "fracture", "record", "cpr"):
        for r in [x for x in all_new if x["cluster_id"] == cl][:2]:
            print(f"  {cl:<9} {r['stem'][:44]}  答案:{r['answer']}")

    if not args.commit:
        print("\n（dry-run，未写库；加 --commit 执行写入）")
        return

    nid = maxid
    for r in all_new:
        nid += 1
        conn.execute(
            "INSERT INTO questions(id,qtype,cluster_id,difficulty,stem,options,answer,source_doc,origin)"
            " VALUES(?,?,?,?,?,?,?,?,?)",
            (nid, r["qtype"], r["cluster_id"], r["difficulty"], r["stem"],
             json.dumps(r["options"], ensure_ascii=False), r["answer"], r["source_doc"], ORIGIN))
    for qid, _o, n, _s in recluster:
        conn.execute("UPDATE questions SET cluster_id=? WHERE id=?", (n, qid))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    print(f"\n✔ 新增 {len(all_new)} 题 + 补标 {len(recluster)} 题；库内总题数 {total}")
    print("--- 写入后分簇 ---")
    for r in conn.execute("SELECT cluster_id, COUNT(*) n FROM questions GROUP BY cluster_id ORDER BY n DESC"):
        print(f"  {str(r['cluster_id']):<10} {r['n']}")

    if os.path.abspath(args.db) == os.path.abspath(DEFAULT_DB):
        seed = json.load(open(SEED, encoding="utf-8"))
        n0 = len(seed)
        for r in all_new:
            seed.append({"origin": ORIGIN, "type": r["qtype"], "stem": r["stem"], "options": r["options"],
                         "answer": r["answer"], "source_doc": r["source_doc"],
                         "cluster": CLUSTER_CN[r["cluster_id"]], "difficulty": r["difficulty"]})
        for qid, o, n, _s in recluster:
            for item in seed:
                if item.get("cluster") == "通用" and norm(item.get("stem", "")) == norm(
                        dict(conn.execute("SELECT stem FROM questions WHERE id=?", (qid,)).fetchone())["stem"]):
                    item["cluster"] = CLUSTER_CN[n]
                    break
        json.dump(seed, open(SEED, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"seed JSON：{n0} → {len(seed)}")


if __name__ == "__main__":
    main()
