"""
sync_done.py -- Run this AFTER you finish working
Saves your changes and pushes to GitHub so the other person gets them.
Usage: python sync_done.py
"""
import subprocess, sys, datetime

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode

print("=" * 50)
print("  QGAI -- Sync Done (saving your work)")
print("=" * 50)

# Check if there is anything to commit
status = subprocess.run("git status --short", shell=True, capture_output=True, text=True)
if not status.stdout.strip():
    print("\nNo changes to save -- nothing to push.")
    sys.exit(0)

print("\nChanged files:")
print(status.stdout)

# Ask for a short description
msg = input("What did you change? (short description): ").strip()
if not msg:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"Update {now}"

run("git add .")
run(f'git commit -m "{msg}"')
ret = run("git push")

if ret == 0:
    print("\nDone! Your changes are saved and pushed to GitHub.")
else:
    print("\nPush failed. Check your internet or GitHub access.")
    sys.exit(1)
