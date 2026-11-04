# h3-multimodal-colab installer for Windows (PowerShell).
# 1 uv  2 Python 3.12 + google-colab-cli 0.7.4 (0.7.5 drops its websocket on Windows)  3 Windows patch
# 4 copy the skill into the agent's skills folder. Nothing is downloaded to this computer except these tools;
# the H3 models are downloaded on the Colab GPU.
param([string]$SkillsDir = "")
$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv ..."
    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}
uv python install 3.12
uv tool install --force --python 3.12 "google-colab-cli==0.7.4"
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
python "$PSScriptRoot\patch_colab_cli.py"
if (-not $?) { uv run --python 3.12 python "$PSScriptRoot\patch_colab_cli.py" }

$targets = @()
if ($SkillsDir) { $targets += $SkillsDir } else {
    foreach ($d in @("$env:USERPROFILE\.claude\skills", "$env:USERPROFILE\.codex\skills", "$env:USERPROFILE\.hermes\skills", "$env:USERPROFILE\.agents\skills")) {
        if (Test-Path (Split-Path -Parent $d)) { $targets += $d }
    }
}
if (-not $targets) { $targets = @("$env:USERPROFILE\.claude\skills") }
foreach ($t in $targets) {
    New-Item -ItemType Directory -Force $t | Out-Null
    $dest = Join-Path $t "h3-multimodal-colab"
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    Copy-Item -Recurse "$Repo\h3-multimodal-colab" $dest
    Write-Host "Skill installed: $dest"
}
colab --help | Out-Null
if ($?) { Write-Host "colab CLI OK" } else { Write-Host "colab CLI did not start, see TROUBLESHOOTING" }
Write-Host "Next: python <skill>\scripts\colab_login.py url"
