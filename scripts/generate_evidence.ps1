# Evidence Package Generation Script (PowerShell)
# CLIENT SPEC Lines 428-437: Submission checklist

Write-Host "📦 Generating Evidence Package..." -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan

# Create evidence directory
New-Item -ItemType Directory -Force -Path evidence | Out-Null
Set-Location evidence

Write-Host "1️⃣ Generating SBOM (Software Bill of Materials)..." -ForegroundColor Yellow
cyclonedx-py -o sbom.json
Write-Host "✅ SBOM: evidence/sbom.json" -ForegroundColor Green

Write-Host "2️⃣ Running CI checks..." -ForegroundColor Yellow
Set-Location ..
pytest --cov=app --cov-report=xml --cov-report=html > evidence/test_report.txt 2>&1
Move-Item -Force coverage.xml evidence/ -ErrorAction SilentlyContinue
Move-Item -Force htmlcov evidence/ -ErrorAction SilentlyContinue
Write-Host "✅ Coverage: evidence/coverage.xml + evidence/htmlcov/" -ForegroundColor Green

Write-Host "3️⃣ Running security scans..." -ForegroundColor Yellow
bandit -r app/ -f json -o evidence/bandit_report.json
safety check --json > evidence/safety_report.json 2>&1
pip-audit --desc --format json > evidence/pip_audit.json 2>&1
Write-Host "✅ Security: evidence/bandit_report.json, safety_report.json, pip_audit.json" -ForegroundColor Green

Write-Host "4️⃣ Extracting NTP logs..." -ForegroundColor Yellow
Select-String -Path logs/system.log -Pattern "ntp|drift|clock" -CaseSensitive:$false | Out-File evidence/ntp_logs.txt
Write-Host "✅ NTP Logs: evidence/ntp_logs.txt" -ForegroundColor Green

Write-Host "5️⃣ Extracting timeline logs..." -ForegroundColor Yellow
Copy-Item logs/timeline.jsonl evidence/timeline_logs.jsonl -ErrorAction SilentlyContinue
Write-Host "✅ Timeline: evidence/timeline_logs.jsonl" -ForegroundColor Green

Write-Host "6️⃣ Extracting guard logs..." -ForegroundColor Yellow
Select-String -Path logs/system.log -Pattern "guard|block|maintenance" -CaseSensitive:$false | Out-File evidence/guard_logs.txt
Write-Host "✅ Guard Logs: evidence/guard_logs.txt" -ForegroundColor Green

Write-Host "7️⃣ Verifying journal integrity..." -ForegroundColor Yellow
python -c "
import asyncio
import json
from app.core.journal import verify_journal_integrity

async def check():
    result = await verify_journal_integrity()
    print(f'Journal Integrity: {result}')
    with open('evidence/journal_integrity.json', 'w') as f:
        json.dump(result, f, indent=2)

asyncio.run(check())
"
Write-Host "✅ Journal: evidence/journal_integrity.json" -ForegroundColor Green

Write-Host "8️⃣ Copying runbook..." -ForegroundColor Yellow
Copy-Item doc/RUNBOOK.md evidence/ -ErrorAction SilentlyContinue
Write-Host "✅ Runbook: evidence/RUNBOOK.md" -ForegroundColor Green

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "📦 Evidence Package Complete!" -ForegroundColor Green
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Location: ./evidence/"
Write-Host ""
Write-Host "Contents:"
Get-ChildItem evidence/ | Format-Table Name, Length, LastWriteTime
Write-Host ""
Write-Host "Next: Compress for submission"
Write-Host '  Compress-Archive -Path evidence -DestinationPath "evidence-$(Get-Date -Format yyyyMMdd).zip"'

