-- Migration 005: Add columns needed for weekly reports
-- Fix for database schema mismatch reported in error analysis

-- Add pyramid_level column
ALTER TABLE trades ADD COLUMN pyramid_level INTEGER DEFAULT 0;

-- Add hedge_count column
ALTER TABLE trades ADD COLUMN hedge_count INTEGER DEFAULT 0;

-- Add reentry_count column  
ALTER TABLE trades ADD COLUMN reentry_count INTEGER DEFAULT 0;

-- Add error_type column
ALTER TABLE trades ADD COLUMN error_type TEXT DEFAULT NULL;

-- Add pnl_pct column for percentage-based PnL tracking
ALTER TABLE trades ADD COLUMN pnl_pct REAL DEFAULT 0.0;

-- Add status column for better trade state tracking
ALTER TABLE trades ADD COLUMN status TEXT DEFAULT 'active';

-- Create index for faster report queries
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON trades(created_at);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_state_created ON trades(state, created_at);

