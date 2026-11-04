# -*- coding: utf-8 -*-
"""Windows fix for google-colab-cli 0.7.4: console.py imports termios/tty (POSIX only) at module level, so every
`colab` command crashes on Windows even though only the interactive console needs them. Wrap the two imports.
Also turns off the update check (it can hang a background agent). Safe to run more than once.
Run with any Python: python patch_colab_cli.py"""
import json
import os
import subprocess
import sys
from pathlib import Path


def tool_root():
    try:
        return Path(subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        return Path(os.environ.get("APPDATA", Path.home() / ".local" / "share")) / "uv" / "tools"


def main():
    conf = Path.home() / ".config" / "colab-cli"
    conf.mkdir(parents=True, exist_ok=True)
    settings = conf / "settings.json"
    data = json.loads(settings.read_text(encoding="utf-8")) if settings.exists() else {}
    data["enable_update_check"] = False
    settings.write_text(json.dumps(data), encoding="utf-8")
    hits = list(tool_root().glob("google-colab-cli/**/colab_cli/console.py"))
    if not hits:
        sys.exit("找不到 colab_cli/console.py：google-colab-cli 裝好了嗎？")
    for p in hits:
        s = p.read_text(encoding="utf-8")
        if "termios = None" in s:
            print("已經補過：", p)
            continue
        s = s.replace("import termios\n", "try:\n    import termios\nexcept ImportError:  # Windows\n    termios = None\n", 1)
        s = s.replace("import tty\n", "try:\n    import tty\nexcept ImportError:\n    tty = None\n", 1)
        p.write_text(s, encoding="utf-8")
        print("已補丁：", p)


if __name__ == "__main__":
    main()
