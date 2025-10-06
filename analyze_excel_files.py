#!/usr/bin/env python3
"""Analyze all Excel files and compare with bot history."""

import pandas as pd
import sqlite3
from datetime import datetime
import os

def analyze_excel_files():
    """Analyze all Excel files and compare with bot database."""
    print("🔍 COMPREHENSIVE EXCEL FILE ANALYSIS")
    print("=" * 60)
    
    # List of Excel files to analyze
    excel_files = [
        'comprehensive_trading_data_20251006_081539.xlsx',
        'bot_database_export.xlsx', 
        'bot_status_summary.xlsx',
        'bybit_demo_trades.xlsx',
        'bybit_demo_export_20251006_081323.xlsx',
        'export_summary_20251006_081324.xlsx'
    ]
    
    analysis_results = {}
    
    # Analyze each Excel file
    for file in excel_files:
        if os.path.exists(file):
            print(f"\n📊 ANALYZING: {file}")
            print("-" * 40)
            
            try:
                # Get all sheet names
                xl_file = pd.ExcelFile(file)
                sheets = xl_file.sheet_names
                print(f"   Sheets: {sheets}")
                
                file_analysis = {
                    'file': file,
                    'sheets': sheets,
                    'total_rows': 0,
                    'data_quality': {},
                    'issues': []
                }
                
                # Analyze each sheet
                for sheet in sheets:
                    try:
                        df = pd.read_excel(file, sheet_name=sheet)
                        rows = len(df)
                        cols = len(df.columns)
                        file_analysis['total_rows'] += rows
                        
                        print(f"   📋 {sheet}: {rows} rows, {cols} columns")
                        
                        # Check for data quality issues
                        quality_issues = []
                        
                        # Check for empty data
                        if rows == 0:
                            quality_issues.append("Empty sheet")
                        elif rows == 1 and 'note' in str(df.iloc[0].values).lower():
                            quality_issues.append("Contains only notes/placeholders")
                        elif rows == 1 and 'error' in str(df.iloc[0].values).lower():
                            quality_issues.append("Contains error messages")
                        
                        # Check for missing data
                        if rows > 0:
                            missing_data = df.isnull().sum().sum()
                            if missing_data > 0:
                                quality_issues.append(f"Missing data: {missing_data} cells")
                            
                            # Check for duplicate rows
                            duplicates = df.duplicated().sum()
                            if duplicates > 0:
                                quality_issues.append(f"Duplicate rows: {duplicates}")
                        
                        file_analysis['data_quality'][sheet] = {
                            'rows': rows,
                            'columns': cols,
                            'issues': quality_issues
                        }
                        
                        if quality_issues:
                            file_analysis['issues'].extend([f"{sheet}: {issue}" for issue in quality_issues])
                        
                    except Exception as e:
                        print(f"   ❌ Error reading sheet {sheet}: {e}")
                        file_analysis['issues'].append(f"Sheet {sheet}: Read error - {e}")
                
                analysis_results[file] = file_analysis
                
            except Exception as e:
                print(f"   ❌ Error analyzing file: {e}")
                analysis_results[file] = {
                    'file': file,
                    'error': str(e),
                    'issues': [f"File read error: {e}"]
                }
        else:
            print(f"   ⚠️  File not found: {file}")
    
    return analysis_results

def compare_with_bot_database():
    """Compare Excel data with bot database."""
    print(f"\n🔍 COMPARING WITH BOT DATABASE")
    print("-" * 40)
    
    try:
        conn = sqlite3.connect('trades.sqlite')
        
        # Get bot database stats
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('SELECT COUNT(*) FROM trades')
        total_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = "DONE"')
        done_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE state = "OPENING"')
        opening_trades = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM trades WHERE DATE(created_at) = DATE("now")')
        today_trades = cursor.fetchone()[0]
        
        # Get recent trades
        cursor.execute('''
            SELECT trade_id, symbol, direction, state, created_at, realized_pnl
            FROM trades 
            ORDER BY created_at DESC 
            LIMIT 5
        ''')
        recent_trades = cursor.fetchall()
        
        # Signal guard
        try:
            cursor.execute('SELECT COUNT(*) FROM signal_guard')
            signal_guard_count = cursor.fetchone()[0]
        except:
            signal_guard_count = 0
        
        # Symbol blocks
        try:
            cursor.execute('SELECT COUNT(*) FROM symbol_dir_block')
            symbol_blocks_count = cursor.fetchone()[0]
        except:
            symbol_blocks_count = 0
        
        conn.close()
        
        print(f"📊 Bot Database Statistics:")
        print(f"   Total trades: {total_trades}")
        print(f"   Done trades: {done_trades}")
        print(f"   Opening trades: {opening_trades}")
        print(f"   Today's trades: {today_trades}")
        print(f"   Signal guard records: {signal_guard_count}")
        print(f"   Symbol blocks: {symbol_blocks_count}")
        
        print(f"\n📋 Recent trades:")
        for trade in recent_trades:
            trade_id, symbol, direction, state, created_at, pnl = trade
            pnl_str = f"{pnl:.2f}" if pnl else "N/A"
            print(f"   {trade_id}: {symbol} {direction} - {state} - PnL: {pnl_str} - {created_at}")
        
        return {
            'total_trades': total_trades,
            'done_trades': done_trades,
            'opening_trades': opening_trades,
            'today_trades': today_trades,
            'signal_guard_count': signal_guard_count,
            'symbol_blocks_count': symbol_blocks_count,
            'recent_trades': recent_trades
        }
        
    except Exception as e:
        print(f"❌ Error accessing bot database: {e}")
        return None

def identify_weaknesses(analysis_results, bot_db_stats):
    """Identify weaknesses and inconsistencies."""
    print(f"\n⚠️  WEAKNESS ANALYSIS")
    print("-" * 40)
    
    weaknesses = []
    
    # 1. Data consistency issues
    if bot_db_stats:
        # Check if Excel exports match database
        comprehensive_file = analysis_results.get('comprehensive_trading_data_20251006_081539.xlsx', {})
        if comprehensive_file and 'data_quality' in comprehensive_file:
            bot_trades_sheet = comprehensive_file['data_quality'].get('Bot_Trades', {})
            if bot_trades_sheet.get('rows', 0) != bot_db_stats['total_trades']:
                weaknesses.append(f"Row count mismatch: Excel has {bot_trades_sheet.get('rows', 0)} rows, DB has {bot_db_stats['total_trades']} trades")
    
    # 2. Empty or placeholder data
    for file, analysis in analysis_results.items():
        if 'issues' in analysis:
            for issue in analysis['issues']:
                if 'Empty sheet' in issue or 'Contains only notes' in issue or 'Contains error messages' in issue:
                    weaknesses.append(f"{file}: {issue}")
    
    # 3. Missing recent data
    if bot_db_stats and bot_db_stats['today_trades'] == 0:
        weaknesses.append("No trades today despite bot being active")
    
    # 4. Stuck trades
    if bot_db_stats and bot_db_stats['opening_trades'] > 0:
        weaknesses.append(f"{bot_db_stats['opening_trades']} trades stuck in OPENING state")
    
    # 5. No PnL data
    if bot_db_stats and bot_db_stats['recent_trades']:
        pnl_issues = [trade for trade in bot_db_stats['recent_trades'] if not trade[5] or trade[5] == 0]
        if pnl_issues:
            weaknesses.append(f"Missing PnL data for {len(pnl_issues)} recent trades")
    
    # 6. API authentication issues
    for file, analysis in analysis_results.items():
        if 'issues' in analysis:
            for issue in analysis['issues']:
                if 'error' in issue.lower() and 'auth' in issue.lower():
                    weaknesses.append(f"{file}: Authentication issues - {issue}")
    
    return weaknesses

def generate_report(analysis_results, bot_db_stats, weaknesses):
    """Generate comprehensive analysis report."""
    print(f"\n📊 COMPREHENSIVE ANALYSIS REPORT")
    print("=" * 60)
    
    print(f"\n📁 FILE ANALYSIS SUMMARY:")
    for file, analysis in analysis_results.items():
        print(f"\n   📄 {file}")
        if 'error' in analysis:
            print(f"      ❌ Error: {analysis['error']}")
        else:
            print(f"      📊 Total rows: {analysis.get('total_rows', 0)}")
            print(f"      📋 Sheets: {len(analysis.get('sheets', []))}")
            if analysis.get('issues'):
                print(f"      ⚠️  Issues: {len(analysis['issues'])}")
                for issue in analysis['issues'][:3]:  # Show first 3 issues
                    print(f"         • {issue}")
    
    print(f"\n🔍 DATA CONSISTENCY CHECK:")
    if bot_db_stats:
        print(f"   ✅ Bot database accessible")
        print(f"   📊 Total trades in DB: {bot_db_stats['total_trades']}")
        print(f"   📊 Trades in Excel: {analysis_results.get('comprehensive_trading_data_20251006_081539.xlsx', {}).get('data_quality', {}).get('Bot_Trades', {}).get('rows', 'Unknown')}")
    else:
        print(f"   ❌ Bot database not accessible")
    
    print(f"\n⚠️  IDENTIFIED WEAKNESSES ({len(weaknesses)}):")
    for i, weakness in enumerate(weaknesses, 1):
        print(f"   {i}. {weakness}")
    
    print(f"\n🎯 RECOMMENDATIONS:")
    print(f"   1. Fix authentication issues for Bybit API")
    print(f"   2. Resolve stuck trades in OPENING state")
    print(f"   3. Implement proper PnL calculation and recording")
    print(f"   4. Add data validation to prevent empty exports")
    print(f"   5. Implement real-time data synchronization")
    
    return {
        'analysis_results': analysis_results,
        'bot_db_stats': bot_db_stats,
        'weaknesses': weaknesses,
        'total_files_analyzed': len(analysis_results),
        'total_weaknesses': len(weaknesses)
    }

if __name__ == "__main__":
    # Run analysis
    analysis_results = analyze_excel_files()
    bot_db_stats = compare_with_bot_database()
    weaknesses = identify_weaknesses(analysis_results, bot_db_stats)
    final_report = generate_report(analysis_results, bot_db_stats, weaknesses)
    
    print(f"\n✅ Analysis completed successfully!")
    print(f"   Files analyzed: {final_report['total_files_analyzed']}")
    print(f"   Weaknesses found: {final_report['total_weaknesses']}")
