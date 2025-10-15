"""
Trading Logic Compliance Validator

This script validates that the codebase complies with CLIENT SPEC requirements
for entry/exit orders and original_entry_price usage.

CLIENT SPEC (doc/10_15.md):
1. Entry orders: MUST have post_only=True, reduceOnly=False
2. Exit orders: MUST have reduceOnly=True
3. All % calculations: MUST use original_entry_price (not avg_entry)

Usage:
    python scripts/validate_trading_logic.py
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Any
from decimal import Decimal


class ValidationError:
    """Represents a validation error."""
    
    def __init__(self, file: str, line: int, message: str, code_snippet: str = ""):
        self.file = file
        self.line = line
        self.message = message
        self.code_snippet = code_snippet
    
    def __str__(self):
        return f"{self.file}:{self.line}: {self.message}\n  {self.code_snippet}"


class TradingLogicValidator:
    """Validates trading logic compliance."""
    
    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.errors: List[ValidationError] = []
        self.warnings: List[ValidationError] = []
    
    def validate_all(self) -> bool:
        """
        Run all validations.
        
        Returns:
            True if all validations pass, False otherwise
        """
        print("=" * 80)
        print("TRADING LOGIC COMPLIANCE VALIDATOR")
        print("=" * 80)
        print()
        
        # Run validators
        self.check_entry_order_flags()
        self.check_exit_order_flags()
        self.check_original_entry_usage()
        self.check_avg_entry_in_calculations()
        self.check_post_only_enforcement()
        
        # Report results
        self.print_report()
        
        return len(self.errors) == 0
    
    def check_entry_order_flags(self):
        """Check that entry orders never have reduceOnly=True."""
        print("Checking entry order flags...")
        
        patterns = [
            (r'reduceOnly["\s]*:\s*True', "Entry order has reduceOnly=True (FORBIDDEN)"),
            (r'"reduceOnly"\s*:\s*True', "Entry order has reduceOnly=True (FORBIDDEN)"),
        ]
        
        # Files to check
        files_to_check = [
            "app/core/strict_fsm.py",
            "app/strategies/reentry_v2.py",
            "app/strategies/hedge_v2.py",
            "app/bybit/client.py"
        ]
        
        for file_path in files_to_check:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                continue
            
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Skip if it's clearly an exit order (has "tp", "sl", "exit" in context)
                context = "".join(lines[max(0, line_num-5):min(len(lines), line_num+5)])
                if any(keyword in context.lower() for keyword in ["tp", "sl", "exit", "breakeven", "trailing"]):
                    continue
                
                # Check for reduceOnly=True in what looks like an entry context
                if "reduceOnly" in line and "True" in line:
                    if any(keyword in context.lower() for keyword in ["entry", "open", "position"]):
                        self.errors.append(ValidationError(
                            file=file_path,
                            line=line_num,
                            message="Entry order may have reduceOnly=True (check manually)",
                            code_snippet=line.strip()
                        ))
    
    def check_exit_order_flags(self):
        """Check that exit orders always have reduceOnly=True."""
        print("Checking exit order flags...")
        
        files_to_check = [
            "app/core/intelligent_tpsl_fixed_v3.py",
            "app/core/simulated_tpsl.py",
            "app/strategies/breakeven_v2.py",
            "app/strategies/trailing_v2.py"
        ]
        
        for file_path in files_to_check:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                continue
            
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Check for order creation without reduceOnly
                if "orderType" in line and ("Limit" in line or "Market" in line):
                    # Get surrounding context
                    start = max(0, line_num - 10)
                    end = min(len(lines), line_num + 10)
                    context = "".join(lines[start:end])
                    
                    # If this looks like TP/SL order but no reduceOnly=True
                    if any(keyword in context.lower() for keyword in ["tp", "sl", "take_profit", "stop_loss"]):
                        if "reduceOnly" not in context or "reduceOnly: False" in context:
                            self.warnings.append(ValidationError(
                                file=file_path,
                                line=line_num,
                                message="Exit order may be missing reduceOnly=True (check manually)",
                                code_snippet=line.strip()
                            ))
    
    def check_original_entry_usage(self):
        """Check that strategies use original_entry_price."""
        print("Checking original_entry_price usage...")
        
        # Files that should use original_entry
        files_to_check = [
            "app/strategies/breakeven_v2.py",
            "app/strategies/trailing_v2.py",
            "app/strategies/pyramid_v2.py"
        ]
        
        for file_path in files_to_check:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                continue
            
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if file uses original_entry
            if "original_entry" not in content:
                self.warnings.append(ValidationError(
                    file=file_path,
                    line=0,
                    message="Strategy may not be using original_entry_price for % calculations",
                    code_snippet=""
                ))
    
    def check_avg_entry_in_calculations(self):
        """Check for avg_entry usage in percentage calculations."""
        print("Checking for avg_entry in % calculations...")
        
        files_to_check = [
            "app/strategies/breakeven_v2.py",
            "app/strategies/trailing_v2.py",
            "app/core/pnl_calculator.py"
        ]
        
        for file_path in files_to_check:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                continue
            
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Check for avg_entry in percentage calculations
                if "avg_entry" in line.lower() and ("*" in line or "/" in line or "%" in line):
                    self.warnings.append(ValidationError(
                        file=file_path,
                        line=line_num,
                        message="Using avg_entry in calculation (should use original_entry_price?)",
                        code_snippet=line.strip()
                    ))
    
    def check_post_only_enforcement(self):
        """Check that entry orders enforce Post-Only."""
        print("Checking Post-Only enforcement...")
        
        files_to_check = [
            "app/bybit/client.py",
            "app/core/strict_fsm.py"
        ]
        
        for file_path in files_to_check:
            full_path = self.root_dir / file_path
            if not full_path.exists():
                continue
            
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                # Check for entry order creation
                if "orderType" in line and "Limit" in line:
                    # Get context
                    start = max(0, line_num - 5)
                    end = min(len(lines), line_num + 10)
                    context = "".join(lines[start:end])
                    
                    # If looks like entry but no PostOnly
                    if "entry" in context.lower():
                        if "PostOnly" not in context and "post_only" not in context.lower():
                            self.warnings.append(ValidationError(
                                file=file_path,
                                line=line_num,
                                message="Entry order may be missing Post-Only enforcement",
                                code_snippet=line.strip()
                            ))
    
    def print_report(self):
        """Print validation report."""
        print()
        print("=" * 80)
        print("VALIDATION REPORT")
        print("=" * 80)
        print()
        
        if self.errors:
            print(f"❌ ERRORS FOUND: {len(self.errors)}")
            print()
            for error in self.errors:
                print(f"  {error}")
                print()
        else:
            print("✅ No critical errors found")
            print()
        
        if self.warnings:
            print(f"⚠️  WARNINGS: {len(self.warnings)}")
            print()
            for warning in self.warnings:
                print(f"  {warning}")
                print()
        else:
            print("✅ No warnings")
            print()
        
        # Summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Errors:   {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        print()
        
        if len(self.errors) == 0:
            print("✅ VALIDATION PASSED")
        else:
            print("❌ VALIDATION FAILED - Fix errors before deploying")
        print()


def main():
    """Main entry point."""
    # Determine root directory
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent
    
    print(f"Validating codebase at: {root_dir}")
    print()
    
    validator = TradingLogicValidator(str(root_dir))
    success = validator.validate_all()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

