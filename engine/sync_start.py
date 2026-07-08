"""
sync_start.py -- Run this BEFORE you start working
Pulls latest changes from GitHub so you have the newest code.
Usage: python sync_start.py
"""
import subprocess, sys

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode

print("=" * 50)
print("  QGAI -- Sync Start (pulling latest code)")
print("=" * 50)

ret = run("git pull")
if ret == 0:
    print("\nAll good -- you have the latest code. Start working!")
else:
    print("\nPull failed. Check your internet connection or GitHub access.")
    sys.exit(1)
