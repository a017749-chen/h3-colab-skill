# -*- coding: utf-8 -*-
"""Two-step Google login for google-colab-cli, so an AI agent can do it inside a chat:

  python colab_login.py url            -> prints the sign-in URL (give it to the user)
  python colab_login.py code <CODE>    -> the user pastes the code Google shows; the token is saved
  python colab_login.py status

`colab` itself asks for the code on stdin, which an agent running commands in the background cannot answer.
This does the same flow in two calls (same client, scopes, redirect and token file as colab-cli's auth.py,
Apache-2.0, Google LLC). The PKCE verifier is kept between the calls in ~/.config/colab-cli/pending_login.json.
It runs with the Python that `uv tool install google-colab-cli` created (it has google-auth-oauthlib).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

CONF = Path.home() / ".config" / "colab-cli"
TOKEN = CONF / "token.json"
PENDING = CONF / "pending_login.json"
SCOPES = ["openid", "https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email",
          "https://www.googleapis.com/auth/cloud-platform", "https://www.googleapis.com/auth/colaboratory",
          "https://www.googleapis.com/auth/drive.file"]
REDIRECT = "https://sdk.cloud.google.com/applicationdefaultauthcode.html"


def tool_python():
    """The interpreter of the uv-installed google-colab-cli (it carries the OAuth libraries)."""
    try:
        root = Path(subprocess.run(["uv", "tool", "dir"], capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        root = Path(os.environ.get("APPDATA", Path.home() / ".local" / "share")) / "uv" / "tools"
    for p in (root / "google-colab-cli" / "Scripts" / "python.exe", root / "google-colab-cli" / "bin" / "python"):
        if p.exists():
            return p
    return None


def client_config():
    from importlib import resources
    return json.loads(resources.files("colab_cli").joinpath("oauth_config.json").read_text())


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:  # not the tool's Python: run again with it
        py = tool_python()
        if not py:
            sys.exit("找不到 google-colab-cli 的 Python：請先執行安裝腳本")
        sys.exit(subprocess.run([str(py), __file__, *sys.argv[1:]]).returncode)
    CONF.mkdir(parents=True, exist_ok=True)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "status":
        print("✅ 已登入" if TOKEN.is_file() else "❌ 還沒登入")
    elif cmd == "url":
        flow = InstalledAppFlow.from_client_config(client_config(), SCOPES, autogenerate_code_verifier=True)
        flow.redirect_uri = REDIRECT
        url, state = flow.authorization_url(prompt="consent", token_usage="remote")
        PENDING.write_text(json.dumps({"verifier": flow.code_verifier, "state": state}), encoding="utf-8")
        print("請用【有 Google AI Pro 訂閱】的帳號打開這個網址登入，按允許後，把頁面上顯示的授權碼貼回來：")
        print(url)
    elif cmd == "code":
        if len(sys.argv) < 3:
            sys.exit("用法：python colab_login.py code <授權碼>")
        if not PENDING.exists():
            sys.exit("要先執行 python colab_login.py url")
        pend = json.loads(PENDING.read_text(encoding="utf-8"))
        flow = InstalledAppFlow.from_client_config(client_config(), SCOPES, state=pend["state"],
                                                   code_verifier=pend["verifier"], autogenerate_code_verifier=False)
        flow.redirect_uri = REDIRECT
        flow.fetch_token(code=sys.argv[2].strip())
        TOKEN.write_text(flow.credentials.to_json(), encoding="utf-8")
        PENDING.unlink(missing_ok=True)
        print("✅ 登入完成，token 存在", TOKEN)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
