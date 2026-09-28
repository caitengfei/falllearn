import sys, time, requests
sys.stdout.reconfigure(encoding="utf-8")
BASE = "http://127.0.0.1:8010"
t = requests.post(BASE + "/api/auth/login", json={"student_no": "S2026001", "password": "123456"}, timeout=10).json()
h = {"authorization": "Bearer " + t["token"]}
for i in range(20):
    r = requests.get(BASE + "/api/learn/history", headers=h, timeout=10).json()
    done = [x for x in r["items"] if "【岗】" in x["answer"] and "【证】" in x["answer"]]
    if len(done) >= 2:
        break
    time.sleep(6)
for x in r["items"][:3]:
    print(x["question"], "|", x["answer"][:40].replace("\n", " "), "| clusters:", x["clusters"])
print("完整四栏条数:", len([x for x in r["items"] if "【岗】" in x["answer"]]))