"""跨平台启动脚本 — 不受终端类型（bash/cmd/PS）影响"""
import subprocess, sys, os, time

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "frontend")

def check(cmd, name):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"[ERROR] {name} not found")
        sys.exit(1)
    print(f"  {name}: OK")

print("=== Chongqing Housing Data Platform ===\n")
print("[1/3] Checking environment...")
check(["where", "python"], "Python")
check(["where", "node"], "Node.js")

print("\n[2/3] Init...")
db = os.path.join(BACKEND, "cq_house.db")
if not os.path.exists(db):
    print("  Seeding database...")
    subprocess.run([sys.executable, "seed_data.py"], cwd=BACKEND, check=True)
else:
    print("  Database OK")

nm = os.path.join(FRONTEND, "node_modules")
if not os.path.exists(nm):
    print("  Installing npm...")
    subprocess.run(["npm", "install"], cwd=FRONTEND, check=True)
else:
    print("  node_modules OK")

print("\n[3/3] Starting services...")
be = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8001"],
    cwd=BACKEND, creationflags=subprocess.CREATE_NEW_CONSOLE
)
fe = subprocess.Popen(
    ["npm", "run", "dev"],
    cwd=FRONTEND, creationflags=subprocess.CREATE_NEW_CONSOLE
)
time.sleep(3)

print("\n============================================")
print("  Frontend : http://localhost:5173")
print("  Swagger  : http://localhost:8001/docs")
print("============================================")
print("\nPress Ctrl+C to stop all services...")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    print("\nStopping...")
    for p in [be, fe]:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            p.kill()
    print("Done.")
