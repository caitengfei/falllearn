# -*- coding: utf-8 -*-
"""试用监测常驻循环：启动即采集一次，之后每 30 分钟一次；10-13 之后自动退出。

- 单实例保护：materials/07-试用数据/monitor.pid 存活则本实例退出
- 每轮调用同目录 trial_monitor.py 的 main()（只读采集，产物见该脚本说明）
- ssh 失败不中断循环，等下一轮重试
- 停止：taskkill /F /PID <monitor.pid 中的进程号>，或删除 Startup 的 vbs 后重启
"""
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.stdout.reconfigure(encoding="utf-8")

import trial_monitor  # noqa: E402

PID_PATH = trial_monitor.OUT_DIR / "monitor.pid"
END = datetime(2026, 10, 13, 23, 59)
INTERVAL = 30 * 60


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main():
    trial_monitor.OUT_DIR.mkdir(parents=True, exist_ok=True)
    if PID_PATH.exists():
        try:
            old = int(PID_PATH.read_text(encoding="utf-8").strip())
            if old != os.getpid() and alive(old):
                print("已有监测循环在运行 PID=%d，退出" % old)
                return
        except ValueError:
            pass
    PID_PATH.write_text(str(os.getpid()), encoding="utf-8")
    print("监测循环启动 PID=%d，每 %d 分钟采集一次，至 %s" % (os.getpid(), INTERVAL // 60, END))
    try:
        while datetime.now() < END:
            try:
                trial_monitor.main()
            except SystemExit as e:
                print("本轮采集跳过: %s" % e)
            except Exception as e:
                print("本轮采集异常: %r" % e)
            time.sleep(INTERVAL)
    finally:
        if PID_PATH.exists() and PID_PATH.read_text(encoding="utf-8").strip() == str(os.getpid()):
            PID_PATH.unlink()
    print("监测循环结束（已达 %s）" % END)


if __name__ == "__main__":
    main()
