# -*- coding: utf-8 -*-
"""为全部题目批量生成讲解（explanation 列）。

规则：正确答案选项文本为主体 + 该簇知识点首句补充 + 来源文档；判断题单独句式。
可重复运行（幂等：每次全量重算 explanation，选项/答案不变）。
用法（服务器）：cd /opt/falllearn/backend && venv/bin/python tools/gen_explanations.py
"""
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
sys.stdout.reconfigure(encoding="utf-8")

from knowledge_seed import KNOWLEDGE_POINTS  # noqa: E402

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "falllearn.db")
CLUSTER_CN = {"morse": "Morse 评估", "env": "环境防控", "five": "五步处置",
              "fracture": "骨折识别", "record": "记录上报", "cpr": "CPR 启动", "general": "养老护理通识"}
FIRST_SENT = {}
for cid, pts in KNOWLEDGE_POINTS.items():
    FIRST_SENT[cid] = [(t, c.split("。")[0] + "。") for t, c in pts]


def short_src(s):
    if not s:
        return "养老护理职业技能标准与教材"
    return s.replace("\\", "/").split("/")[-1].replace(".md", "")


def build(stem, qtype, options, answer, cluster, source_doc, qid):
    src = short_src(source_doc)
    pts = FIRST_SENT.get(cluster)
    point = ""
    if pts:
        title, first = pts[qid % len(pts)]
        point = "本题关联知识点「%s」：%s" % (title, first)
    def opt_text(a):
        out = []
        for ch in a:
            i = ord(ch) - 65
            if 0 <= i < len(options):
                out.append(options[i])
        return "；".join(out) if out else ""
    if qtype == "判断":
        right = "正确" if answer.strip().upper().startswith("A") else "错误"
        body = "正确答案：%s。%s" % (right, point) if point else "正确答案：%s。" % right
    else:
        txt = opt_text(answer)
        body = "正确答案 %s（%s）。%s" % (answer, txt, point) if point else "正确答案 %s（%s）。" % (answer, txt)
    return "%s依据：《%s》。" % (body, src)


def main():
    d = sqlite3.connect(os.path.abspath(DB))
    d.row_factory = sqlite3.Row
    rows = d.execute("SELECT id, stem, qtype, options, answer, cluster_id, source_doc FROM questions").fetchall()
    n = 0
    for r in rows:
        try:
            opts = json.loads(r["options"]) if r["options"] else []
        except Exception:
            opts = []
        exp = build(r["stem"], r["qtype"], opts, r["answer"], r["cluster_id"], r["source_doc"], r["id"])
        d.execute("UPDATE questions SET explanation=? WHERE id=?", (exp, r["id"]))
        n += 1
    d.commit()
    print("已生成讲解:", n, "题")
    for r in d.execute("SELECT id, explanation FROM questions LIMIT 2"):
        print(" 示例 #%d %s" % (r["id"], r["explanation"][:90]))
    d.close()


if __name__ == "__main__":
    main()
