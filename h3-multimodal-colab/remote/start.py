# Runs ON the Colab VM through `colab exec`: starts remote_job.py in the background and returns at once.
# A long `colab exec` can drop its websocket before it ends; a short one that only launches the job does not.
import json, subprocess, sys, time
from pathlib import Path

JOB = Path("/content/h3job")
status = JOB / "status.json"
running = subprocess.run(["pgrep", "-f", "h3job/remote_job.py"], capture_output=True, text=True).stdout.strip()
if running:
    print(json.dumps({"started": False, "reason": "a batch is already running", "pid": running}))
else:
    if status.exists():
        status.rename(JOB / f"status_{int(time.time())}.json")
    p = subprocess.Popen([sys.executable, str(JOB / "remote_job.py")], cwd=str(JOB),
                         stdout=open(JOB / "remote_job.log", "w"), stderr=subprocess.STDOUT, start_new_session=True)
    print(json.dumps({"started": True, "pid": p.pid}))
