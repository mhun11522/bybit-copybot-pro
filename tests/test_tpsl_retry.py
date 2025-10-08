#!/usr/bin/env python3
"""Test TP/SL retry functionality."""

import asyncio
from unittest.mock import AsyncMock, patch
from app.core.confirmation_gate import retry_until_ok

async def test_retry_until_ok_success():
    """Test retry function with successful operation."""
    call_count = 0
    
    async def mock_op():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"success": False, "error": "Temporary failure"}
        return {"success": True, "result": "Success"}
    
    result = await retry_until_ok(mock_op, attempts=3, delay=0.1, op_name="test_op")
    
    assert result["success"] is True
    assert result["result"] == "Success"
    assert call_count == 2

async def test_retry_until_ok_failure():
    """Test retry function with persistent failure."""
    call_count = 0
    
    async def mock_op():
        nonlocal call_count
        call_count += 1
        return {"success": False, "error": "Persistent failure"}
    
    try:
        await retry_until_ok(mock_op, attempts=3, delay=0.1, op_name="test_op")
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "test_op failed after 3 attempts" in str(e)
        assert call_count == 3

async def test_retry_until_ok_exception():
    """Test retry function with exceptions."""
    call_count = 0
    
    async def mock_op():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Network error")
        return {"success": True, "result": "Success after retry"}
    
    result = await retry_until_ok(mock_op, attempts=3, delay=0.1, op_name="test_op")
    
    assert result["success"] is True
    assert result["result"] == "Success after retry"
    assert call_count == 2

async def test_retry_until_ok_immediate_success():
    """Test retry function with immediate success."""
    call_count = 0
    
    async def mock_op():
        nonlocal call_count
        call_count += 1
        return {"success": True, "result": "Immediate success"}
    
    result = await retry_until_ok(mock_op, attempts=3, delay=0.1, op_name="test_op")
    
    assert result["success"] is True
    assert result["result"] == "Immediate success"
    assert call_count == 1

if __name__ == "__main__":
    import pytest
    pytest.main([__file__])
