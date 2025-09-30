-- 004_unify_trades_state.sql
-- Unify trades table schema around state='OPEN'/'DONE' instead of status

PRAGMA foreign_keys=off;

CREATE TABLE IF NOT EXISTS trades_new (
    trade_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    size REAL NOT NULL,
    avg_entry REAL,
    position_size REAL,
    leverage REAL,
    channel_name TEXT,
    state TEXT NOT NULL,          -- "OPEN" or "DONE"
    realized_pnl REAL DEFAULT 0,
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Copy old data, mapping legacy 'status' to 'state'
INSERT INTO trades_new (trade_id, symbol, direction, entry_price, size,
                        avg_entry, position_size, leverage, channel_name,
                        state, realized_pnl, closed_at, created_at)
SELECT
    trade_id,
    symbol,
    direction,
    entry_price,
    size,
    avg_entry,
    position_size,
    leverage,
    channel_name,
    -- Map legacy 'status' to 'state'
    CASE
        WHEN status = 'CLOSED' THEN 'DONE'
        WHEN status = 'OPEN'   THEN 'OPEN'
        ELSE COALESCE(state, 'OPEN')
    END as state,
    COALESCE(realized_pnl, 0),
    closed_at,
    created_at
FROM trades;

DROP TABLE trades;
ALTER TABLE trades_new RENAME TO trades;

PRAGMA foreign_keys=on;