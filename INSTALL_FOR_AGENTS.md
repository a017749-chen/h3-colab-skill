# Install guide for AI agents

You were asked to install **h3-multimodal-colab**. Follow these steps in order.

## Step 1 — Tell the user first, and wait for "yes"

Before installing anything, explain in the user's language:

1. **What it does**: it lets you (the agent) generate pictures, talking videos, video extensions and voice
   lines with MiniMax H3 on **the user's own Google Colab GPU**. You write the prompts; Colab does the work;
   the files come back to this computer; the GPU is released afterwards.
2. **Subscription**: at least **Google AI Pro** (it includes Colab compute units). AI Plus is not enough.
3. **Cost**: L4 ≈ 1.5 units per hour (about an RTX 4060), G4 ≈ 11 units per hour (about an RTX Pro 6000).
   AI Pro gives about 400 units a month. Every start installs ComfyUI and downloads about 50–60 GB of models
   **on Colab** (3–5 minutes), not on this computer.
4. **What gets installed on this computer**: `uv`, Python 3.12 and Google's `google-colab-cli` 0.7.4
   (an isolated tool), plus this skill folder. Nothing else.
5. **Login**: once. You will show a Google sign-in link; the user signs in **with the AI Pro account**,
   clicks Allow and pastes the code back to you.

Only continue after the user agrees.

## Step 2 — Install

Clone (or download) `https://github.com/dseditor/h3-colab-skill`, then:

- Windows (PowerShell): `powershell -ExecutionPolicy Bypass -File install\install.ps1`
- macOS / Linux: `bash install/install.sh`

Pass a folder as the first argument if your skills live somewhere unusual
(e.g. `install.ps1 -SkillsDir C:\path\to\skills`). By default it copies the skill into every agent
skills folder it finds: `~/.claude/skills`, `~/.codex/skills`, `~/.hermes/skills`, `~/.agents/skills`.

## Step 3 — Login (needs the user)

```
python <skill>/scripts/colab_login.py url
```
Give the printed link to the user. When they paste the code:
```
python <skill>/scripts/colab_login.py code <CODE>
python <skill>/scripts/h3run.py check
```
`check` prints the remaining compute units when everything works.

## Step 4 — First run

Read `<skill>/SKILL.md`. Make a tiny first batch (one 5-second 480P video on L4) so the user sees the
whole loop and the real time on their account before anything bigger.
