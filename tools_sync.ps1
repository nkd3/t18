# Teevra18 — One-click sync: guard → autodoc → commit-if-needed → push
# Usage: powershell -ExecutionPolicy Bypass -File C:\T18\tools_sync.ps1

Set-StrictMode -Version 3.0
Continue = 'Stop'

# 0) Go to project
Set-Location C:\T18

# 1) Activate venv (ignore errors if already active)
try { & C:\T18\.venv\Scripts\Activate.ps1 | Out-Null } catch {}

# 2) Secret guard (abort on fail)
python C:\T18\tools_guard_secrets.py
if (1 -ne 0) {
  Write-Host "❌ Secret guard failed — aborting push."
  exit 1
}

# 3) AutoDoc → Notion + local README
python C:\T18\tools_autodoc_to_notion.py

# 4) Stage docs update
git add docs\README_AUTODOC.md

# 5) Commit only if something is staged
git diff --cached --quiet
 = (1 -ne 0)

if () {
   = Get-Date -Format 'yyyy-MM-dd_HH-mm'
  git commit -m "docs: AutoDoc sync " | Out-Null
  Write-Host "✅ Committed AutoDoc changes."
} else {
  Write-Host "ℹ️  No changes to commit (AutoDoc identical)."
}

# 6) Push
git push

Write-Host "✅ Sync complete."
