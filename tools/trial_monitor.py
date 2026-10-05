# -*- coding: utf-8 -*-
"""试用监测任务：国庆小测答题情况采集（全程只读）。

流程：
  1. 确认服务器探针 /tmp/trial_probe.py 存在（缺失则用 scp 上传本地副本 C:\\temp\\srv_trial_probe.py）
  2. ssh 执行探针（纯 SELECT，绝不写库）→ 取回 JSON
  3. 写三份产物到 materials/07-试用数据/：
     _raw/snapshot_*.json（原始快照） / 监测时间线.csv（追加） / 国庆小测监测报告.md（覆盖更新）
  4. stdout 打印摘要（计划任务日志用）

调度：Windows 计划任务 FallLearnTrialMonitor（每小时）。
隐私：报告与 CSV 只含学号；昵称不落盘不进材料。materials/ 已在 .gitignore，永不入库、按需上传大赛系统前人工复核。
"""
import csv
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

KEY = r"C:\Users\Administrator\.ssh\falllearn_deploy"
HOST = "root@121.199.161.117"
REMOTE_PY = "/opt/falllearn/backend/venv/bin/python /tmp/trial_probe.py"
LOCAL_PROBE = Path(__file__).with_name("srv_trial_probe.py")
OUT_DIR = Path(r"E:\lilei\platform\materials\07-试用数据")
RAW_DIR = OUT_DIR / "_raw"
CSV_PATH = OUT_DIR / "监测时间线.csv"
MD_PATH = OUT_DIR / "国庆小测监测报告.md"
RUN_LOG = OUT_DIR / "monitor_run.log"

CLUSTER_NAMES = {
    "morse": "Morse 评估", "env": "环境防控", "five": "五步处置",
    "fracture": "骨折识别", "record": "记录上报", "cpr": "CPR 启动", "general": "通用",
}

# 服务器端一致性备份脚本（经 ssh stdin 执行；VACUUM INTO 只读源库、写新快照文件，不写任何数据行）
BACKUP_SRC = """
import os, sqlite3, time
DB = "/opt/falllearn/backend/falllearn.db"
OUT_DIR = "/opt/falllearn/backups"
OUT = os.path.join(OUT_DIR, "falllearn_%s.db" % time.strftime("%Y%m%d_%H%M%S"))
os.makedirs(OUT_DIR, exist_ok=True)
c = sqlite3.connect(DB)
c.execute("VACUUM INTO ?", (OUT,))
c.close()
print(OUT)
"""


def sh(args, timeout=60):
    """执行本地命令并返回 (rc, stdout, stderr)。"""
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def ssh(cmd, timeout=60):
    return sh(["ssh", "-i", KEY, HOST, cmd], timeout)


def ssh_stdin(src, timeout=90):
    """经 ssh stdin 在服务器执行 python 脚本（python -）。"""
    r = subprocess.run(["ssh", "-i", KEY, HOST, "/opt/falllearn/backend/venv/bin/python -"],
                       input=src, capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def daily_backup():
    """每天第一次采集时：服务器一致性快照 + scp 下载到本地 _backups/（学生做题数据的保险）。

    只读语义：VACUUM INTO 不修改源库；服务器侧仅保留最近 7 份，本地全保留。"""
    today = time.strftime("%Y%m%d")
    bdir = OUT_DIR / "_backups"
    bdir.mkdir(parents=True, exist_ok=True)
    if list(bdir.glob("falllearn_%s_*.db" % today)):
        return
    rc, out, err = ssh_stdin(BACKUP_SRC)
    if rc != 0:
        print("每日备份失败:", err[:200])
        return
    srv_path = out.strip().splitlines()[-1]
    name = srv_path.replace("\\", "/").split("/")[-1]
    # scp 对含中文的本地路径不可靠：先下到 C:\temp 再本地移动
    tmp = Path(r"C:\temp") / name
    rc, _, err = sh(["scp", "-i", KEY, "%s:%s" % (HOST, srv_path), str(tmp)], timeout=120)
    if rc != 0:
        print("备份下载失败:", err[:200])
        return
    # 完整性校验：scp 超时可能留下截断文件（实测踩过：本地 655KB vs 服务器 1.5MB）
    rc, out, _ = ssh("stat -c %%s %s" % srv_path)
    srv_size = int(out.strip()) if out.strip().isdigit() else -1
    local_size = tmp.stat().st_size
    if local_size != srv_size:
        tmp.unlink(missing_ok=True)
        print("备份校验失败：本地 %d != 服务器 %d（已删除截断文件，明日重试）" % (local_size, srv_size))
        return
    shutil.move(str(tmp), str(bdir / name))
    sh(["ssh", "-i", KEY, HOST, "ls -1t /opt/falllearn/backups/*.db 2>/dev/null | tail -n +8 | xargs -r rm -f"])
    print("每日备份完成:", name)


def ensure_probe():
    rc, out, _ = ssh("test -f /tmp/trial_probe.py && echo OK")
    if "OK" not in out:
        if not LOCAL_PROBE.exists():
            raise SystemExit("服务器缺探针且本地副本不存在：%s" % LOCAL_PROBE)
        rc, _, err = sh(["scp", "-i", KEY, str(LOCAL_PROBE), "%s:/tmp/trial_probe.py" % HOST])
        if rc != 0:
            raise SystemExit("scp 探针失败: %s" % err[:200])
        print("已上传探针到服务器 /tmp/trial_probe.py")


def collect():
    rc, out, err = ssh(REMOTE_PY, timeout=90)
    if rc != 0:
        raise SystemExit("探针执行失败 rc=%s: %s" % (rc, err[:300]))
    return json.loads(out.strip().splitlines()[-1])


def fmt_ts(ts):
    return datetime.fromtimestamp(int(ts)).strftime("%m-%d %H:%M") if ts else "-"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ensure_probe()
    j = collect()
    try:
        daily_backup()  # 备份失败不中断采集
    except Exception as e:
        print("每日备份异常:", repr(e))
    now = datetime.now()
    stamp = now.strftime("%Y-%m-%d %H:%M:%S")

    exam = j["exam"]
    att = j["attempts"]
    students = j["students_real"]
    total = j["students_real_total"]
    attempts = j["real_attempts"]
    done = [a for a in attempts if a["status"] == "done"]
    open_by = {a["student_no"] for a in attempts if a["status"] == "open"}
    done_nos = {a["student_no"] for a in done}
    scores = [a["score"] for a in done]
    avg = round(sum(scores) / len(scores), 1) if scores else "-"
    full = sum(1 for s in scores if s == j["max_score"])
    dist = Counter(scores)
    max_s = j["max_score"]

    # 逐题正确率（与题干/簇合并）
    per_q = {x["question_id"]: x for x in j.get("per_question", [])}
    q_rows = []
    for it in j["items"]:
        x = per_q.get(it["question_id"], {"n": 0, "ok": 0})
        rate = round(x["ok"] * 100 / x["n"]) if x["n"] else None
        q_rows.append({"seq": it["seq"], "stem": it["stem"][:38], "cluster": CLUSTER_NAMES.get(it["cluster_id"], it["cluster_id"]),
                       "n": x["n"], "ok": x["ok"], "rate": rate})

    # 快照 JSON（原始数据，本地留存）
    snap_path = RAW_DIR / ("snapshot_%s.json" % now.strftime("%Y%m%d_%H%M%S"))
    snap_path.write_text(json.dumps({"collected_at": stamp, **j}, ensure_ascii=False, indent=1), encoding="utf-8")

    # 时间线 CSV（追加，utf-8-sig 便于 Excel）
    header = ["采集时间", "注册学生", "开卷", "完成", "进行中", "完成率%", "平均分", "满分人数",
              "今日登录", "今日签到", "今日AI问答", "今日开卷(全部)"]
    ta = j["today_activity"]
    row = [stamp, total, att["real"], att["done"], att["open"],
           round(att["done"] * 100 / total) if total else 0, avg, full,
           ta["logins"], ta["checkins"], ta["ai_asks"], ta["practice_started"]]
    new_csv = not CSV_PATH.exists()
    with open(CSV_PATH, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new_csv:
            w.writerow(header)
        w.writerow(row)

    # 未完成名单（学号）
    pending = [s["student_no"] for s in students if s["student_no"] not in done_nos]

    # —— 报告 ——
    L = []
    L.append("# 国庆小测 · 答题情况监测报告")
    L.append("")
    L.append("> 数据来源：平台生产库只读探针（纯 SELECT，不写任何数据）；采集时间 **%s**" % stamp)
    L.append("> 小测：%s / 满分 %d 分 / 限时 10 分钟 / 截止 %s"
             % (exam["title"], max_s, fmt_ts(exam.get("due_at"))))
    L.append("> 口径：真实注册学生（自动排除 S2026001-3 三个演示账号）；**全部只显示学号，不含昵称**")
    L.append("")
    L.append("## 一、完成情况总览")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append("| 真实注册学生 | %d 人 |" % total)
    L.append("| 已开卷 | %d 人 |" % att["real"])
    L.append("| **已完成** | **%d 人（%d%%）** |" % (att["done"], round(att["done"] * 100 / total) if total else 0))
    L.append("| 进行中（未交卷） | %d 人（%s） |" % (att["open"], "、".join(sorted(open_by)) or "-"))
    L.append("| 未开始 | %d 人 |" % (total - att["real"]))
    L.append("")
    L.append("## 二、成绩")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append("| 平均分 | %s / %d |" % (avg, max_s))
    L.append("| 满分 | %d 人（%d%%） |" % (full, round(full * 100 / len(done)) if done else 0))
    L.append("| 得分分布 | %s |" % "，".join("%d分×%d人" % (s, c) for s, c in sorted(dist.items(), reverse=True)))
    if j.get("durations_min"):
        ds = j["durations_min"]
        L.append("| 用时 | 最快 %.1f 分钟 / 中位 %.1f / 最慢 %.1f（限时 10 分钟，无超时） |"
                 % (ds[0], ds[len(ds) // 2], ds[-1]))
    L.append("")
    L.append("## 三、逐题正确率（教学参考）")
    L.append("")
    L.append("| # | 知识簇 | 题干（截断） | 作答 | 正确 | 正确率 |")
    L.append("|---|---|---|---|---|---|")
    for q in q_rows:
        L.append("| %d | %s | %s | %d | %d | %s |" % (q["seq"], q["cluster"], q["stem"], q["n"], q["ok"],
                                                      ("%d%%" % q["rate"]) if q["rate"] is not None else "-"))
    weak = [q for q in q_rows if q["rate"] is not None and q["rate"] < 100]
    if weak:
        L.append("")
        L.append("**教学提示**：%s 正确率未达 100%%，建议在班级群提示复习对应知识点"
                 "（学生端：错题本「学这一簇」/ 知识地图该簇抽屉）。" % "、".join("第%d题(%s)" % (q["seq"], q["cluster"]) for q in weak))
    else:
        L.append("")
        L.append("全部题目正确率 100%（当前完成样本下）。")
    L.append("")
    L.append("## 四、未完成名单（学号，共 %d 人）" % len(pending))
    L.append("")
    L.append("、".join(pending) if pending else "（无——全员完成）")
    L.append("")
    L.append("## 五、按天完成趋势")
    L.append("")
    L.append("| 日期 | 完成人数 |")
    L.append("|---|---|")
    for r in j.get("done_by_day", []):
        L.append("| %s | %d |" % (r["day"], r["c"]))
    L.append("")
    L.append("## 六、平台今日活跃（真实学生）")
    L.append("")
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append("| 今日登录 | %d 人 |" % ta["logins"])
    L.append("| 今日签到 | %d 人 |" % ta["checkins"])
    L.append("| 今日 AI 问答 | %d 次 |" % ta["ai_asks"])
    L.append("| 今日开卷（全部练习） | %d 次 |" % ta["practice_started"])
    L.append("| 待复习错题（累计） | %d 条 |" % ta["wrong_active"])
    L.append("")
    L.append("> 口径说明：登录数 = 登录页登录（注册成功自动进入不计入）；签到/AI 问答/开卷为平台行为记录。")
    L.append("## 七、累计学习数据（真实学生，可作应用成效口径）")
    L.append("")
    cum = j["cumulative"]
    L.append("| 指标 | 数值 |")
    L.append("|---|---|")
    L.append("| 完成练习/考试 | %d 组 |" % cum["practice_done_all"])
    L.append("| 错题本累计 | %d 条（其中已掌握 %d） |" % (cum["wrong_records_total"], cum["wrong_mastered"]))
    L.append("| AI 问答累计 | %d 次 |" % cum["chat_total"])
    L.append("| 积分累计 | %d 分 |" % cum["points_total"])
    L.append("")
    L.append("## 附：引用口径（回填《应用案例与教学成效数据》时用）")
    L.append("")
    L.append("截至 %s：三个班级通过邀请码注册学生 %d 人；教师布置的国庆小测已完成 %d/%d（%d%%），"
             "平均 %s 分（满分 %d），满分率 %d%%；平台累计完成练习 %d 组、AI 问答 %d 次、错题本 %d 条（已掌握 %d）。"
             % (stamp, total, att["done"], total, round(att["done"] * 100 / total) if total else 0,
                avg, max_s, round(full * 100 / len(done)) if done else 0,
                cum["practice_done_all"], cum["chat_total"], cum["wrong_records_total"], cum["wrong_mastered"]))
    L.append("")
    L.append("> 隐私说明：本报告仅含平台内自动生成的学号与成绩，不含姓名/昵称/联系方式；"
             "原始快照在 `_raw/`（同样不含昵称）。提交大赛材料包前请整体复核。")
    MD_PATH.write_text("\n".join(L), encoding="utf-8")

    summary = ("[%s] 注册 %d | 开卷 %d | 完成 %d（%d%%）| 平均 %s/%d | 满分 %d | 未完成 %d"
               % (stamp, total, att["real"], att["done"], round(att["done"] * 100 / total) if total else 0,
                  avg, max_s, full, len(pending)))
    with open(RUN_LOG, "a", encoding="utf-8") as f:
        f.write(summary + "\n")
    print(summary)
    print("报告: %s" % MD_PATH)


if __name__ == "__main__":
    main()
