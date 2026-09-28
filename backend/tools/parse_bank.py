# -*- coding: utf-8 -*-
r"""题库解析+标注（块式解析 v3）：
江苏 2023 题库 txt（答案在题干括号内，选项散排，部分缺选项/跨页）+ KB 模拟真题 md（40 题）
→ E:\lilei\platform\backend\seed\questions_seed.json
标注：cluster（6 簇+通用）、difficulty（1-3）启发式
"""
import json
import os
import re
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")

JS = r"E:\lilei\research\txt\jiangsu_theory_q.txt"
MOCK = r"E:\lilei\跌倒-岗课赛证知识库\04-证\模拟真题（跌倒专项）.md"
OUT = r"E:\lilei\platform\backend\seed\questions_seed.json"

CLUSTERS = {
    "Morse评估": ["morse", "morris", "跌倒风险评", "风险评估", "评估量表", "hfha", "berg", "fesi", "再评估", "风险分层", "高危", "中危", "低危", "跌倒风险"],
    "环境防控": ["地面", "环境危险", "环境因素", "照明", "扶手", "助行器", "助行器具", "滑倒", "防滑", "卫生间", "床栏", "杂物", "危险物品", "跌倒预防", "预防措施", "防跌倒", "跌倒高危", "跌倒高风险", "跌倒危险"],
    "五步处置": ["意识", "搬动", "制动", "伤情", "脉搏", "报告医生", "不急于扶", "不要急于", "先评估", "急救", "应急处置", "五步", "呼救", "安抚", "保暖", "体位", "跌倒后", "倒地", "搬抬", "搬运"],
    "骨折识别": ["骨折", "股骨颈", "髋部", "夹板", "骨擦", "异常活动", "局部肿胀"],
    "记录上报": ["记录", "上报", "不良事件", "登记", "交班", "事件记录", "记录单", "报告单", "填写"],
    "CPR启动": ["心肺复苏", "胸外按压", "人工呼吸", "心脏骤停", "脉搏消失", "除颤", "aed"],
}


def cluster_of(text):
    t = text.lower()
    scores = {}
    for name, kws in CLUSTERS.items():
        s = sum(2 for k in kws if k in t)
        if s:
            scores[name] = s
    if not scores:
        return "通用"
    return max(scores, key=lambda k: (scores[k], -list(CLUSTERS).index(k)))


def difficulty_of(qtype, text):
    if qtype == "多选":
        return 2
    if qtype == "判断":
        return 1
    if re.search(r"下列.*(不包括|除外|错误|不属于|不正确)", text):
        return 2
    if re.search(r"(一位|某位|老人在|老年人.*发生|跌倒后|场景中|案例)", text):
        return 2
    if re.search(r"\d+\s*(分钟|分|秒|次|条|项|个)", text):
        return 2
    return 1


def find_options(block2):
    """在答案已置空的块里定位选项区：取最后一个 A 标记，其后依次存在 B/C/D 标记。
    标记 = 字母（前为行首/空白/左括号，后为空白或非 ASCII 汉字）。返回 (opts, 首字母位置)。"""
    mark_re = {L: re.compile(rf"(?:^|[\s　(（])({L})(?=[\s　]|[^\x00-\x7f])") for L in "ABCD"}
    candidates = []
    for ma in mark_re["A"].finditer(block2):
        letter_pos = [ma.start(1)]
        ok = True
        for L in "BCD":
            found = None
            for m2 in mark_re[L].finditer(block2, letter_pos[-1]):
                if m2.start(1) > letter_pos[-1]:
                    found = m2
                    break
            if found is None:
                ok = False
                break
            letter_pos.append(found.start(1))
        if ok:
            candidates.append(letter_pos)
    if not candidates:
        return {}, -1
    letter_pos = candidates[-1]  # 选项区在题干之后，取最后一个合法 A
    opts = {}
    for i, L in enumerate("ABCD"):
        s = letter_pos[i] + 1
        e = letter_pos[i + 1] if i + 1 < 4 else len(block2)
        opts[L] = block2[s:e].strip().strip("　").strip()
    return opts, letter_pos[0]


# ---------- 江苏 txt（块式） ----------
def parse_jiangsu():
    raw = open(JS, encoding="utf-8").read()
    raw = re.sub(r"--- PAGE \d+ ---", "\n", raw)
    lines = [l.rstrip() for l in raw.split("\n")]
    cut = len(lines)
    for i, l in enumerate(lines):
        if "第二部分" in l:
            cut = i
            break
    lines = lines[:cut]

    section = None
    blocks = []  # [num, type, block_text]
    for l in lines:
        s = l.strip()
        if not s or re.match(r"^\d{1,3}$", s):
            continue
        if re.match(r"^一、单项选择题", s):
            section = "单选"
            continue
        if re.match(r"^二、多项选择题", s):
            section = "多选"
            continue
        if re.match(r"^三、判断题", s):
            section = "判断"
            continue
        m = re.match(r"^(\d{1,3})[\.、．]\s*(.+)$", s)
        if m:
            blocks.append([int(m.group(1)), section or "单选", m.group(2)])
        elif blocks:
            blocks[-1][2] += "\n" + s

    bank, bad_opt, bad_ans = [], 0, 0
    for num, qtype, block in blocks:
        am = re.search(r"[（(]\s*([A-F]{1,4})\s*[)）]", block)
        if not am:
            bad_ans += 1
            continue
        ans = re.sub(r"\s+", "", am.group(1)).upper()
        # 先置空答案括号，避免把 ( A ) 里的字母当选项标记
        block2 = re.sub(r"[（(]\s*[A-F]{1,4}\s*[)）]", "（　）", block)
        opts, opt_start = find_options(block2)
        if qtype in ("单选", "多选") and len(opts) < 4:
            bad_opt += 1
            continue
        stem = block2[:opt_start] if opt_start >= 0 else block2
        stem = re.sub(r"\n+", " ", stem).strip()
        bank.append({
            "origin": "江苏2023真题",
            "type": qtype,
            "stem": stem,
            "options": [opts.get(k, "") for k in "ABCD"] if qtype != "判断" else [],
            "answer": ans,
            "source_doc": "江苏2023养老护理职业技能竞赛理论题库",
        })
    print(f"江苏: 块 {len(blocks)}, 入库 {len(bank)}, 缺选项 {bad_opt}, 无答案 {bad_ans}")
    return bank


# ---------- 模拟真题 md ----------
def parse_mock():
    raw = open(MOCK, encoding="utf-8").read()
    body = raw.split("## 详细内容", 1)[1]
    qtype = None
    blocks = []
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("###"):
            if "单项选择题" in s:
                qtype = "单选"
            elif "多项选择题" in s:
                qtype = "多选"
            elif "判断题" in s:
                qtype = "判断"
            continue
        if s.startswith("#"):
            continue
        m = re.match(r"^(\d+)[\.、]\s*(.+)$", s)
        if m:
            blocks.append([qtype or "单选", m.group(2)])
        elif blocks and s:
            blocks[-1][1] += "\n" + s

    bank = []
    for qtype, block in blocks:
        am = re.search(r"\*\*答案：\s*([A-F]{1,4})\*\*[（(]([^)）]*)[)）]?", block)
        if not am:
            print("  MOCK 跳过(无答案):", block[:40].replace("\n", " "))
            continue
        ans, src = am.group(1), (am.group(2) or "").strip()
        # 先删答案行，避免 D 选项吞掉 **答案** 与来源
        block_na = re.sub(r"\*\*答案.*$", "", block, flags=re.M)
        opts, opt_start = find_options(block_na)
        if qtype in ("单选", "多选") and len(opts) < 4:
            print("  MOCK 跳过(缺选项):", block[:40].replace("\n", " "))
            continue
        stem = block_na[:opt_start] if opt_start >= 0 else block_na
        stem = re.sub(r"[（(]\s*[　 ]*\s*[)）]", "（　）", stem)
        stem = re.sub(r"\n+", " ", stem).strip()
        bank.append({
            "origin": "模拟编写",
            "type": qtype,
            "stem": stem,
            "options": [opts.get(k, "") for k in "ABCD"] if qtype != "判断" else [],
            "answer": ans,
            "source_doc": f"04-证/模拟真题（跌倒专项）.md（{src}）" if src else "04-证/模拟真题（跌倒专项）.md",
        })
    print(f"模拟: 入库 {len(bank)} 题")
    return bank


js = parse_jiangsu()
mk = parse_mock()
allq = js + mk
for q in allq:
    full = q["stem"] + " " + " ".join(q["options"])
    q["cluster"] = cluster_of(full)
    q["difficulty"] = difficulty_of(q["type"], full)

print("\n题型:", dict(Counter(q["type"] for q in allq)))
print("来源:", dict(Counter(q["origin"] for q in allq)))
print("簇:", dict(Counter(q["cluster"] for q in allq)))
print("难度:", dict(Counter(q["difficulty"] for q in allq)))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(allq, f, ensure_ascii=False, indent=1)
print("\n写入", OUT, len(allq), "题")

for i in (0, 1, 5, 300, 588, 589, 628, len(allq) - 1):
    if 0 <= i < len(allq):
        q = allq[i]
        print(f"\n--- 抽检 #{i} [{q['type']}/{q['cluster']}/d{q['difficulty']}] {q['origin']}")
        print("Q:", q["stem"][:90])
        print("opts:", [o[:24] for o in q["options"]])
        print("ans:", q["answer"])