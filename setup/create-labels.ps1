# Creates or reconciles GitHub labels from setup/project-taxonomy.json.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
python setup/create_labels.py @args
