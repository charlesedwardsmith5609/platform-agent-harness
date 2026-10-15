# Bootstrap a local dogfood trial (Windows).
# Usage:
#   .\setup\trial-local.ps1
#   .\setup\trial-local.ps1 -Worktree
#   .\setup\trial-local.ps1 -Smoke
param(
    [switch]$Worktree,
    [switch]$Smoke,
    [string]$Worker = "trial-local"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$args = @()
if ($Worktree) { $args += "--worktree" }
if ($Smoke) { $args += "--smoke" }
if ($Worker) { $args += @("--worker", $Worker) }

python setup/trial_local.py @args
exit $LASTEXITCODE
