# Runs ON the Colab VM through `colab exec`: prints the batch status as one JSON line (short, so it never times out).
import json, subprocess
from pathlib import Path

JOB = Path("/content/h3job")
try:
    st = json.loads((JOB / "status.json").read_text(encoding="utf-8"))
except Exception:
    st = {"stage": "not started", "jobs": {}, "done": False}
st["alive"] = bool(subprocess.run(["pgrep", "-f", "h3job/remote_job.py"], capture_output=True, text=True).stdout.strip())
if not st["alive"] and not st.get("done"):
    tail = (JOB / "remote_job.log").read_text(errors="ignore")[-1500:] if (JOB / "remote_job.log").exists() else ""
    st.update(done=True, stage="crashed", error=st.get("error") or ("the batch process exited\n" + tail))
st["log"] = st.get("log", [])[-8:]
print("H3STATUS " + json.dumps(st, ensure_ascii=False))
