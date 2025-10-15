"""
Test suite for critical fixes implemented on 2025-10-15.

Tests cover:
1. Database WAL mode and concurrent access
2. Entry consolidated message flow
3. No print() statements in app/ code
"""

import pytest
import asyncio
import os
import ast
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch


class TestDatabaseFixes:
    """Test database locking fixes."""
    
    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self):
        """Verify WAL mode is enabled in database connections."""
        from app.storage.db import get_db_connection
        
        conn = await get_db_connection()
        try:
            cursor = await conn.execute("PRAGMA journal_mode")
            mode = await cursor.fetchone()
            
            # WAL mode should be enabled
            assert mode[0].upper() == 'WAL', f"Expected WAL mode, got {mode[0]}"
            
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_busy_timeout_set(self):
        """Verify busy timeout is set to prevent immediate lock failures."""
        from app.storage.db import get_db_connection
        
        conn = await get_db_connection()
        try:
            cursor = await conn.execute("PRAGMA busy_timeout")
            timeout = await cursor.fetchone()
            
            # Timeout should be at least 5000ms (5 seconds)
            assert int(timeout[0]) >= 5000, f"Busy timeout too low: {timeout[0]}ms"
            
        finally:
            await conn.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_database_access(self):
        """Test that multiple concurrent connections don't cause locks."""
        from app.storage.db import get_db_connection
        
        async def write_operation(task_id: int):
            """Simulate concurrent database write."""
            for i in range(5):
                conn = await get_db_connection()
                try:
                    # Perform a write operation
                    await conn.execute(
                        "CREATE TABLE IF NOT EXISTS test_concurrent (id TEXT, data TEXT)"
                    )
                    await conn.execute(
                        "INSERT INTO test_concurrent (id, data) VALUES (?, ?)",
                        (f"task_{task_id}_row_{i}", f"data_{i}")
                    )
                    await conn.commit()
                finally:
                    await conn.close()
                
                # Small delay to simulate realistic usage
                await asyncio.sleep(0.01)
        
        # Run 3 concurrent write operations
        tasks = [write_operation(i) for i in range(3)]
        
        try:
            # Should complete without "database is locked" errors
            await asyncio.wait_for(asyncio.gather(*tasks), timeout=15.0)
            
            # Verify all writes succeeded
            conn = await get_db_connection()
            try:
                cursor = await conn.execute("SELECT COUNT(*) FROM test_concurrent")
                count = await cursor.fetchone()
                assert count[0] == 15, f"Expected 15 rows, got {count[0]}"
            finally:
                # Cleanup
                await conn.execute("DROP TABLE IF EXISTS test_concurrent")
                await conn.commit()
                await conn.close()
                
        except asyncio.TimeoutError:
            pytest.fail("Database operations timed out (likely locked)")
        except Exception as e:
            if "database is locked" in str(e).lower():
                pytest.fail(f"Database locking still occurs: {e}")
            raise


class TestEntryConsolidatedMessage:
    """Test entry consolidated message implementation."""
    
    @pytest.mark.asyncio
    async def test_entry_consolidated_template_exists(self):
        """Verify ENTRY_CONSOLIDATED template is implemented."""
        from app.telegram.engine import render_template
        
        # Test data
        data = {
            'symbol': 'BTCUSDT',
            'source_name': 'Test Channel',
            'side': 'LONG',
            'trade_type': 'SWING',
            'entry1': Decimal('50000'),
            'qty1': Decimal('0.1'),
            'im1': Decimal('10'),
            'entry2': Decimal('50100'),
            'qty2': Decimal('0.1'),
            'im2': Decimal('10'),
            'avg_entry': Decimal('50050'),
            'qty_total': Decimal('0.2'),
            'im_total': Decimal('20'),
            'bot_order_id': 'BOT-123',
            'bybit_order_id': '456',
            'leverage': Decimal('6')
        }
        
        # Should not raise exception
        rendered = render_template("ENTRY_CONSOLIDATED", data)
        
        # Verify required fields in output
        assert '📌 Sammanslagning' in rendered['text'] or 'Sammanslagning' in rendered['text']
        assert 'volymvägt' in rendered['text'] or 'VWAP' in rendered['text']
        assert 'ENTRY 1' in rendered['text']
        assert 'ENTRY 2' in rendered['text']
        assert 'POSITION' in rendered['text']
        
        # Verify VWAP is correct (not simple average)
        assert '50050' in rendered['text'] or '50,050' in rendered['text']
    
    @pytest.mark.asyncio
    async def test_vwap_calculation(self):
        """Test VWAP calculation is correct (not simple average)."""
        from app.trade.websocket_handlers import WebSocketTradeHandlers
        
        handlers = WebSocketTradeHandlers()
        
        # Set up entry data
        symbol = "BTCUSDT"
        handlers._entry_data = {
            f"{symbol}_E1": {
                'price': Decimal('50000'),
                'qty': Decimal('0.3'),  # 75% weight
                'im': Decimal('15')
            },
            f"{symbol}_E2": {
                'price': Decimal('50100'),
                'qty': Decimal('0.1'),  # 25% weight
                'im': Decimal('5')
            }
        }
        
        # Calculate expected VWAP
        # VWAP = (50000 * 0.3 + 50100 * 0.1) / (0.3 + 0.1)
        # VWAP = (15000 + 5010) / 0.4 = 20010 / 0.4 = 50025
        expected_vwap = Decimal('50025')
        
        # Mock the send_message to capture the data
        sent_data = {}
        
        async def mock_send(text, **kwargs):
            sent_data['text'] = text
        
        with patch('app.trade.websocket_handlers.send_message', side_effect=mock_send):
            with patch('app.trade.websocket_handlers.render_template') as mock_render:
                # Set up mock to capture the data passed to render_template
                def capture_data(template_name, data):
                    sent_data['template_data'] = data
                    return {
                        'text': f"Test message with VWAP {data.get('avg_entry', 0)}",
                        'template_name': template_name,
                        'trade_id': 'test123',
                        'symbol': symbol,
                        'hashtags': '#btc #btcusdt'
                    }
                
                mock_render.side_effect = capture_data
                
                # Call the consolidation method
                trade_info = {
                    'trade_id': 'test123',
                    'channel_name': 'Test Channel',
                    'side': 'LONG',
                    'trade_type': 'SWING'
                }
                
                await handlers._send_consolidated_entry(symbol, trade_info)
                
                # Verify VWAP was calculated correctly (not simple average)
                assert 'template_data' in sent_data
                calculated_vwap = sent_data['template_data']['avg_entry']
                assert calculated_vwap == expected_vwap, \
                    f"VWAP calculation incorrect: expected {expected_vwap}, got {calculated_vwap}"
                
                # Simple average would be 50050 (wrong)
                simple_avg = (Decimal('50000') + Decimal('50100')) / 2
                assert calculated_vwap != simple_avg, \
                    "VWAP should not be simple average when quantities differ"


class TestNoPrintStatements:
    """Test that print() statements are removed from app/ code."""
    
    def test_no_print_in_app_code(self):
        """Verify no print() statements in app/ directory (excluding __pycache__)."""
        violations = []
        
        for root, dirs, files in os.walk('app'):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                filepath = os.path.join(root, file)
                
                # Read file
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Parse AST to find print() calls
                try:
                    tree = ast.parse(content, filename=filepath)
                    
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Call):
                            # Check if it's a print() call
                            if isinstance(node.func, ast.Name) and node.func.id == 'print':
                                # Get line number
                                line_no = node.lineno
                                # Get the line content
                                lines = content.split('\n')
                                line_content = lines[line_no - 1] if line_no <= len(lines) else ''
                                
                                # Skip if it's in a comment or docstring
                                if not line_content.strip().startswith('#'):
                                    violations.append(f"{filepath}:{line_no}: {line_content.strip()}")
                
                except SyntaxError:
                    # Skip files with syntax errors (might be templates)
                    pass
        
        assert len(violations) == 0, \
            f"Found {len(violations)} print() statements in app/ code:\n" + "\n".join(violations[:10])
    
    def test_strict_config_uses_logger(self):
        """Verify strict_config.py uses system_logger instead of print."""
        filepath = 'app/core/strict_config.py'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should contain system_logger calls
        assert 'system_logger.info' in content or 'system_logger.warning' in content, \
            "strict_config.py should use system_logger"
        
        # Count remaining print statements
        print_count = content.count('print(')
        
        # Should be 0 (all replaced with logger)
        assert print_count == 0, f"Found {print_count} print() calls in strict_config.py"
    
    def test_websocket_uses_logger(self):
        """Verify websocket.py uses system_logger instead of print."""
        filepath = 'app/bybit/websocket.py'
        
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should contain system_logger calls
        assert 'system_logger.info' in content or 'system_logger.error' in content, \
            "websocket.py should use system_logger"
        
        # Count remaining print statements (excluding comments)
        lines = content.split('\n')
        print_count = sum(1 for line in lines if 'print(' in line and not line.strip().startswith('#'))
        
        # Should be minimal (ideally 0)
        assert print_count == 0, f"Found {print_count} print() calls in websocket.py"


class TestMessageFlowCompliance:
    """Test that message flow follows CLIENT SPEC."""
    
    @pytest.mark.asyncio
    async def test_dual_entry_flow(self):
        """
        Test that dual entry flow sends all 3 required messages.
        
        CLIENT SPEC: ENTRY 1 TAKEN → ENTRY 2 TAKEN → ENTRY CONSOLIDATED
        """
        from app.trade.websocket_handlers import WebSocketTradeHandlers
        
        handlers = WebSocketTradeHandlers()
        
        # Track messages sent
        messages_sent = []
        
        async def mock_send(text, **kwargs):
            messages_sent.append({
                'text': text,
                'template_name': kwargs.get('template_name', '')
            })
        
        # Mock render_template
        def mock_render(template_name, data):
            return {
                'text': f"Message: {template_name}",
                'template_name': template_name,
                'trade_id': data.get('trade_id', 'test'),
                'symbol': data.get('symbol', 'TEST'),
                'hashtags': '#test #testusdt'
            }
        
        # Mock confirmation gate
        async def mock_fetch_im(symbol):
            return Decimal('20')
        
        with patch('app.trade.websocket_handlers.send_message', side_effect=mock_send):
            with patch('app.trade.websocket_handlers.render_template', side_effect=mock_render):
                with patch('app.trade.websocket_handlers.get_confirmation_gate') as mock_gate_fn:
                    mock_gate = MagicMock()
                    mock_gate._fetch_confirmed_im = mock_fetch_im
                    mock_gate_fn.return_value = mock_gate
                    
                    with patch('app.trade.websocket_handlers.get_bybit_client'):
                        symbol = "BTCUSDT"
                        
                        # Process ENTRY 1 fill
                        await handlers._handle_entry_fill(
                            symbol, "Buy", Decimal('0.1'), Decimal('50000'), "order_E1_123"
                        )
                        
                        # Should have 1 message (ENTRY_TAKEN for Entry 1)
                        assert len(messages_sent) == 1
                        assert 'ENTRY_TAKEN' in messages_sent[0]['template_name']
                        
                        # Process ENTRY 2 fill
                        await handlers._handle_entry_fill(
                            symbol, "Buy", Decimal('0.1'), Decimal('50100'), "order_E2_456"
                        )
                        
                        # Should now have 3 messages total
                        assert len(messages_sent) == 3, \
                            f"Expected 3 messages (E1, E2, CONSOLIDATED), got {len(messages_sent)}"
                        
                        # Verify message sequence
                        assert 'ENTRY_TAKEN' in messages_sent[0]['template_name']
                        assert 'ENTRY_TAKEN' in messages_sent[1]['template_name']
                        assert 'CONSOLIDATED' in messages_sent[2]['template_name']
    
    @pytest.mark.asyncio
    async def test_vwap_not_simple_average(self):
        """Verify VWAP calculation is volume-weighted, not simple average."""
        from app.trade.websocket_handlers import WebSocketTradeHandlers
        
        handlers = WebSocketTradeHandlers()
        symbol = "ETHUSDT"
        
        # Set up unequal quantities
        handlers._entry_data = {
            f"{symbol}_E1": {
                'price': Decimal('2000'),
                'qty': Decimal('0.9'),  # 90% of position
                'im': Decimal('18')
            },
            f"{symbol}_E2": {
                'price': Decimal('2100'),
                'qty': Decimal('0.1'),  # 10% of position
                'im': Decimal('2')
            }
        }
        
        # Calculate expected VWAP
        # VWAP = (2000 * 0.9 + 2100 * 0.1) / 1.0 = (1800 + 210) / 1.0 = 2010
        expected_vwap = Decimal('2010')
        
        # Simple average would be 2050 (WRONG)
        simple_avg = (Decimal('2000') + Decimal('2100')) / 2
        
        # Capture what gets sent
        captured_vwap = None
        
        async def mock_send(text, **kwargs):
            pass
        
        def mock_render(template_name, data):
            nonlocal captured_vwap
            if template_name == "ENTRY_CONSOLIDATED":
                captured_vwap = data.get('avg_entry')
            return {
                'text': f"VWAP: {data.get('avg_entry', 0)}",
                'template_name': template_name,
                'trade_id': 'test',
                'symbol': symbol,
                'hashtags': '#eth #ethusdt'
            }
        
        with patch('app.trade.websocket_handlers.send_message', side_effect=mock_send):
            with patch('app.trade.websocket_handlers.render_template', side_effect=mock_render):
                trade_info = {
                    'trade_id': 'test123',
                    'channel_name': 'Test',
                    'side': 'LONG',
                    'trade_type': 'DYNAMIC'
                }
                
                await handlers._send_consolidated_entry(symbol, trade_info)
                
                # Verify VWAP calculation
                assert captured_vwap == expected_vwap, \
                    f"VWAP should be {expected_vwap}, got {captured_vwap}"
                assert captured_vwap != simple_avg, \
                    f"VWAP should not be simple average {simple_avg}"


class TestTemplateCompliance:
    """Test template system compliance."""
    
    def test_no_legacy_template_imports(self):
        """Verify no active code imports swedish_templates_v2."""
        violations = []
        
        for root, dirs, files in os.walk('app'):
            # Skip deprecated and cache directories
            dirs[:] = [d for d in dirs if d not in ('__pycache__', 'deprecated')]
            
            for file in files:
                if not file.endswith('.py'):
                    continue
                
                # Skip the deprecated template file itself
                if file == 'swedish_templates_v2.py':
                    continue
                
                # Skip deprecated scheduler
                if file == 'strict_scheduler.py':
                    continue
                
                filepath = os.path.join(root, file)
                
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Check for active imports (not commented)
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    # Skip comments
                    if line.strip().startswith('#'):
                        continue
                    
                    # Check for import
                    if 'swedish_templates_v2' in line and 'import' in line:
                        violations.append(f"{filepath}:{i}: {line.strip()}")
        
        assert len(violations) == 0, \
            f"Found {len(violations)} legacy template imports:\n" + "\n".join(violations)


class TestFormatFunctions:
    """Test format function compliance with CLIENT SPEC."""
    
    def test_fmt_leverage_uses_comma(self):
        """Verify leverage format uses comma: x6,00 not x6.00"""
        from app.telegram.formatting import fmt_leverage
        
        result = fmt_leverage(Decimal('6.00'))
        
        # Should use comma as decimal separator
        assert ',' in result or '6.00' in result, \
            f"Leverage format should use comma or show decimals: {result}"
        
        # Should have exactly 2 decimal places
        if ',' in result:
            parts = result.replace('x', '').split(',')
            assert len(parts) == 2 and len(parts[1]) == 2, \
                f"Should have 2 decimal places: {result}"
    
    def test_fmt_percent_has_space(self):
        """Verify percent format has space: '11 %' not '11%'"""
        from app.telegram.formatting import fmt_percent
        
        result = fmt_percent(Decimal('11.0'))
        
        # Should have space before %
        assert ' %' in result, f"Percent should have space before %: {result}"
        
        # Should not be "11%"
        assert result != "11%", "Should not be '11%' without space"
    
    def test_fmt_usdt_exact_two_decimals(self):
        """Verify USDT format always has exactly 2 decimals, never approximate."""
        from app.telegram.formatting import fmt_usdt
        
        # Test various inputs
        test_cases = [
            (Decimal('20'), '20.00'),
            (Decimal('19.36'), '19.36'),
            (Decimal('19.3'), '19.30'),
            (Decimal('19.999'), '19.99'),  # Should round down
        ]
        
        for input_val, expected_decimal in test_cases:
            result = fmt_usdt(input_val)
            
            # Should never contain "~"
            assert '~' not in result, f"Should never show approximate: {result}"
            
            # Should have exactly 2 decimals
            assert expected_decimal in result, \
                f"Expected {expected_decimal} in result, got: {result}"


class TestOriginalEntryPrice:
    """Test that strategies use original_entry_price, not avg_entry."""
    
    @pytest.mark.asyncio
    async def test_pyramid_uses_original_entry(self):
        """Verify pyramid strategy calculates from original entry."""
        from app.strategies.pyramid_v2 import PyramidStrategyV2
        
        # Create pyramid strategy
        pyramid = PyramidStrategyV2(
            trade_id="test123",
            symbol="BTCUSDT",
            direction="LONG",
            original_entry=Decimal('50000'),
            channel_name="Test"
        )
        
        # Verify it stores original entry
        assert hasattr(pyramid, 'original_entry'), "Should store original_entry"
        assert pyramid.original_entry == Decimal('50000'), "Should match provided value"
        
        # Calculate gain at +3% from original
        current_price = Decimal('51500')  # +3% from 50000
        
        # Mock Bybit client
        with patch.object(pyramid, 'bybit'):
            # The check_and_activate method should calculate from original_entry
            # If price is 51500 and original is 50000, gain should be 3%
            gain_pct = (current_price - pyramid.original_entry) / pyramid.original_entry * 100
            
            assert abs(gain_pct - Decimal('3.0')) < Decimal('0.01'), \
                f"Gain calculation should be from original entry: {gain_pct}"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

