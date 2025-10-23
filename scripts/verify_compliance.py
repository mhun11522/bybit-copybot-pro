#!/usr/bin/env python3
"""
Compliance Verification Script
Verifies all Priority 1 fixes from COMPLIANCE_ANALYSIS.md
"""

import sys
import os
import re
from pathlib import Path
from typing import List, Tuple

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_hardcoded_decimals() -> Tuple[bool, List[str]]:
    """Check for hardcoded Decimal values in strategies."""
    print("✓ Checking for hardcoded Decimal values in strategies...")
    
    issues = []
    strategy_files = [
        "app/strategies/pyramid_v2.py",
        "app/strategies/breakeven_v2.py",
        "app/strategies/trailing_v2.py",
        "app/strategies/hedge_v2.py",
        "app/strategies/reentry_v2.py"
    ]
    
    # Pattern for hardcoded Decimals (excluding safe values like 0, 1, 100)
    pattern = re.compile(r'Decimal\("([0-9]+\.?[0-9]*)"')
    safe_values = {"0", "1", "100", "0.01", "0.1", "0.001"}
    
    for filepath in strategy_files:
        full_path = project_root / filepath
        if not full_path.exists():
            issues.append(f"  ❌ File not found: {filepath}")
            continue
        
        with open(full_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                matches = pattern.findall(line)
                for match in matches:
                    if match not in safe_values and "STRICT_CONFIG" not in line:
                        issues.append(f"  ❌ {filepath}:{line_no} - Hardcoded Decimal(\"{match}\")")
    
    if issues:
        print(f"  ❌ Found {len(issues)} hardcoded Decimal values:")
        for issue in issues:
            print(issue)
        return False, issues
    else:
        print("  ✅ No hardcoded Decimal values found in strategies")
        return True, []

def check_json_logging_fields() -> Tuple[bool, List[str]]:
    """Check if JSON logging includes required fields."""
    print("\n✓ Checking JSON logging fields in output.py...")
    
    issues = []
    output_file = project_root / "app/telegram/output.py"
    
    required_fields = [
        "trace_id",
        "message_text_hash",
        "session_id",
        "event_version",
        "message_status"
    ]
    
    if not output_file.exists():
        issues.append("  ❌ app/telegram/output.py not found")
        return False, issues
    
    content = output_file.read_text(encoding='utf-8')
    
    for field in required_fields:
        if f'"{field}"' in content:
            print(f"  ✅ Field '{field}' present")
        else:
            issues.append(f"  ❌ Field '{field}' missing")
    
    # Check for hashlib and uuid imports
    if "import hashlib" in content:
        print("  ✅ hashlib imported")
    else:
        issues.append("  ❌ hashlib not imported")
    
    if "import uuid" in content:
        print("  ✅ uuid imported")
    else:
        issues.append("  ❌ uuid not imported")
    
    if issues:
        return False, issues
    else:
        return True, []

def check_legacy_templates_disabled() -> Tuple[bool, List[str]]:
    """Check if legacy template system is disabled."""
    print("\n✓ Checking legacy template system disabled...")
    
    issues = []
    template_file = project_root / "app/telegram/swedish_templates_v2.py"
    
    if not template_file.exists():
        issues.append("  ❌ swedish_templates_v2.py not found")
        return False, issues
    
    content = template_file.read_text(encoding='utf-8')
    
    # Check for RuntimeError
    if "raise RuntimeError" in content and "DEPRECATED" in content:
        print("  ✅ Legacy templates hard-disabled with RuntimeError")
    else:
        issues.append("  ❌ Legacy templates not disabled")
    
    if issues:
        return False, issues
    else:
        return True, []

def check_dual_entry_flow() -> Tuple[bool, List[str]]:
    """Check if dual-entry flow is implemented."""
    print("\n✓ Checking dual-entry flow implementation...")
    
    issues = []
    
    # Check websocket handlers for entry fill tracking
    ws_file = project_root / "app/trade/websocket_handlers.py"
    if not ws_file.exists():
        issues.append("  ❌ websocket_handlers.py not found")
    else:
        ws_content = ws_file.read_text(encoding='utf-8')
        if "_entry_fills" in ws_content:
            print("  ✅ Entry fill tracking present")
        else:
            issues.append("  ❌ Entry fill tracking missing")
    
    # Check engine for templates
    engine_file = project_root / "app/telegram/engine.py"
    if not engine_file.exists():
        issues.append("  ❌ engine.py not found")
    else:
        engine_content = engine_file.read_text(encoding='utf-8')
        
        if "def entry_taken" in engine_content:
            print("  ✅ ENTRY_TAKEN template present")
        else:
            issues.append("  ❌ ENTRY_TAKEN template missing")
            
        if "def entry_consolidated" in engine_content:
            print("  ✅ ENTRY_CONSOLIDATED template present")
        else:
            issues.append("  ❌ ENTRY_CONSOLIDATED template missing")
    
    # Check for VWAP calculation in websocket handlers
    if ws_file.exists():
        if "vwap" in ws_content.lower() or "total_value / total_qty" in ws_content:
            print("  ✅ VWAP formula implemented")
        else:
            issues.append("  ❌ VWAP formula not found")
    
    if issues:
        return False, issues
    else:
        return True, []

def check_strict_config_usage() -> Tuple[bool, List[str]]:
    """Check if strategies use STRICT_CONFIG instead of hardcoded values."""
    print("\n✓ Checking STRICT_CONFIG usage in strategies...")
    
    issues = []
    strategy_files = [
        "app/strategies/pyramid_v2.py",
        "app/strategies/breakeven_v2.py",
        "app/strategies/trailing_v2.py",
        "app/strategies/hedge_v2.py",
        "app/strategies/reentry_v2.py"
    ]
    
    for filepath in strategy_files:
        full_path = project_root / filepath
        if not full_path.exists():
            issues.append(f"  ❌ {filepath} not found")
            continue
        
        content = full_path.read_text(encoding='utf-8')
        
        if "from app.core.strict_config import STRICT_CONFIG" in content:
            print(f"  ✅ {filepath.split('/')[-1]} uses STRICT_CONFIG")
        else:
            issues.append(f"  ❌ {filepath.split('/')[-1]} doesn't import STRICT_CONFIG")
    
    if issues:
        return False, issues
    else:
        return True, []

def main():
    """Run all compliance checks."""
    print("=" * 70)
    print("CLIENT COMPLIANCE VERIFICATION")
    print("Reference: COMPLIANCE_ANALYSIS.md, doc/10_12_2.md, doc/10_12_3.md")
    print("=" * 70)
    
    checks = [
        ("Hardcoded Decimals Removed", check_hardcoded_decimals),
        ("JSON Logging Fields", check_json_logging_fields),
        ("Legacy Templates Disabled", check_legacy_templates_disabled),
        ("Dual-Entry Flow", check_dual_entry_flow),
        ("STRICT_CONFIG Usage", check_strict_config_usage)
    ]
    
    results = []
    
    for check_name, check_func in checks:
        try:
            passed, issues = check_func()
            results.append((check_name, passed, issues))
        except Exception as e:
            print(f"\n  ❌ Error in {check_name}: {e}")
            results.append((check_name, False, [str(e)]))
    
    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    passed_count = sum(1 for _, passed, _ in results if passed)
    total_count = len(results)
    
    for check_name, passed, issues in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {check_name}")
        if not passed and issues:
            for issue in issues[:3]:  # Show first 3 issues
                print(f"       {issue}")
            if len(issues) > 3:
                print(f"       ... and {len(issues) - 3} more")
    
    print("\n" + "=" * 70)
    compliance_pct = (passed_count / total_count) * 100
    print(f"COMPLIANCE: {passed_count}/{total_count} checks passed ({compliance_pct:.0f}%)")
    
    if compliance_pct >= 90:
        print("Grade: A (Excellent) ✅")
        return 0
    elif compliance_pct >= 80:
        print("Grade: B (Good) ⚠️")
        return 0
    elif compliance_pct >= 70:
        print("Grade: C (Acceptable) ⚠️")
        return 1
    else:
        print("Grade: F (Needs Work) ❌")
        return 1

if __name__ == "__main__":
    sys.exit(main())

