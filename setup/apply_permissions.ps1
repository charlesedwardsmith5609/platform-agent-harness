# Materialize portable permission placeholders into gitignored local settings.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python setup/apply_permissions.py @args
