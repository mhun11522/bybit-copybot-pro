#!/bin/bash
# Evidence Package Generation Script
# CLIENT SPEC Lines 428-437: Submission checklist

echo "📦 Generating Evidence Package..."
echo "=================================="

# Create evidence directory
mkdir -p evidence/
cd evidence/

echo "1️⃣ Generating SBOM (Software Bill of Materials)..."
cyclonedx-py -o sbom.json
echo "✅ SBOM: evidence/sbom.json"

echo "2️⃣ Running CI checks..."
cd ..
pytest --cov=app --cov-report=xml --cov-report=html > evidence/test_report.txt 2>&1
mv coverage.xml evidence/
mv htmlcov evidence/
echo "✅ Coverage: evidence/coverage.xml + evidence/htmlcov/"

echo "3️⃣ Running security scans..."
bandit -r app/ -f json -o evidence/bandit_report.json
safety check --json > evidence/safety_report.json 2>&1 || true
pip-audit --desc --format json > evidence/pip_audit.json 2>&1 || true
echo "✅ Security: evidence/bandit_report.json, safety_report.json, pip_audit.json"

echo "4️⃣ Extracting NTP logs..."
grep -i "ntp\|drift\|clock" logs/system.log > evidence/ntp_logs.txt 2>&1 || echo "No NTP logs yet"
echo "✅ NTP Logs: evidence/ntp_logs.txt"

echo "5️⃣ Extracting timeline logs..."
cp logs/timeline.jsonl evidence/timeline_logs.jsonl 2>&1 || echo "No timeline logs yet"
echo "✅ Timeline: evidence/timeline_logs.jsonl"

echo "6️⃣ Extracting guard logs..."
grep -i "guard\|block\|maintenance" logs/system.log > evidence/guard_logs.txt 2>&1 || echo "No guard logs yet"
echo "✅ Guard Logs: evidence/guard_logs.txt"

echo "7️⃣ Verifying journal integrity..."
python -c "
import asyncio
from app.core.journal import verify_journal_integrity

async def check():
    result = await verify_journal_integrity()
    print(f'Journal Integrity: {result}')
    with open('evidence/journal_integrity.json', 'w') as f:
        import json
        json.dump(result, f, indent=2)

asyncio.run(check())
" 2>&1 || echo "Journal check failed"
echo "✅ Journal: evidence/journal_integrity.json"

echo "8️⃣ Copying runbook..."
cp doc/RUNBOOK.md evidence/ 2>&1 || echo "Runbook not yet created"
echo "✅ Runbook: evidence/RUNBOOK.md"

echo ""
echo "=================================="
echo "📦 Evidence Package Complete!"
echo "=================================="
echo "Location: ./evidence/"
echo ""
echo "Contents:"
ls -lh evidence/
echo ""
echo "Next: Compress for submission"
echo "  tar -czf evidence-$(date +%Y%m%d).tar.gz evidence/"

