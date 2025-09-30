# Bybit Copybot Pro - Production Deployment Guide

## 🚀 **Production-Ready Features**

This bot now includes all client requirements:

### ✅ **Core Features**
- **Signal Detection**: Supports JUP, FIDDE, Lux Leak, Simple formats
- **ACK-Gated Trading**: No success until Bybit confirms each step
- **Leverage Policy**: SWING=6x, DYNAMIC≥7.5x, forbid (6,7.5), auto SL -2% + FAST x10
- **Dual-Entry Planning**: 50/50 split or ±0.1% auto-generation
- **Symbol Registry**: Bybit instruments metadata with quantization

### ✅ **Advanced Trading Features**
- **TP2 → Break-even + 0.0015%**: OCO Manager
- **Trailing Stop**: +6.1% trigger, 2.5% band
- **Hedge/Re-entry**: -2% trigger, up to 3 re-entries
- **Pyramid Manager**: IM steps, thresholds

### ✅ **Production Features**
- **Capacity Gate**: 100 trades maximum
- **Idempotency**: 90-180s deduplication
- **Swedish Templates**: Channel names in all messages
- **Structured Logging**: TraceId, error mapping
- **Daily/Weekly Reports**: 22:00 Stockholm timezone

## 📋 **Deployment Checklist**

### 1. **Environment Setup**
```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. **Configuration (.env)**
```env
# Bybit Configuration
BYBIT_ENDPOINT=https://api-testnet.bybit.com  # Testnet first!
BYBIT_API_KEY=your_api_key
BYBIT_API_SECRET=your_api_secret
BYBIT_RECV_WINDOW=5000

# Telegram Configuration
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_SESSION=bybit_copybot_session

# Channel Configuration (by name, not ID)
SRC_CHANNEL_NAMES=YourChannelOne,YourChannelTwo,YourChannelThree

# Risk Management
RISK_PER_TRADE=0.02  # 2%
MAX_CONCURRENT_TRADES=100
DEDUP_SECONDS=120

# Timezone
TIMEZONE=Europe/Stockholm
```

### 3. **Database Setup**
The bot will automatically create SQLite databases:
- `trades.sqlite`: Trade tracking, idempotency
- `bybit_copybot_session.session`: Telegram session

### 4. **Telegram Authentication**
```bash
# First run - authenticate with Telegram
python telegram_auth.py
```

### 5. **Testing**
```bash
# Run acceptance tests
pytest tests/test_acceptance.py -v

# Run specific test categories
pytest tests/test_acceptance.py::TestSignalParsing -v
pytest tests/test_acceptance.py::TestTradeFSM -v
```

### 6. **Production Deployment**

#### **Option A: Direct Run**
```bash
python main.py
```

#### **Option B: Systemd Service (Linux)**
```ini
# /etc/systemd/system/bybit-copybot.service
[Unit]
Description=Bybit Copybot Pro
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/bybit-copybot-pro
Environment=PATH=/path/to/bybit-copybot-pro/.venv/bin
ExecStart=/path/to/bybit-copybot-pro/.venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable bybit-copybot
sudo systemctl start bybit-copybot
sudo systemctl status bybit-copybot
```

#### **Option C: Docker**
```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["python", "main.py"]
```

```bash
docker build -t bybit-copybot .
docker run -d --name bybit-copybot --env-file .env bybit-copybot
```

## 📊 **Monitoring & Logs**

### **Structured Logging**
All logs are in JSON format with traceId:
```json
{
  "timestamp": "2025-09-30T12:00:00.000000",
  "level": "INFO",
  "logger": "trade",
  "traceId": "a1b2c3d4",
  "message": "Signal parsed successfully",
  "data": {
    "symbol": "JUPUSDT",
    "direction": "BUY",
    "channel_name": "Test Channel"
  }
}
```

### **Log Files**
- `bot.log`: Main application logs
- `trades.sqlite`: Trade database
- Console output: Real-time monitoring

### **Health Checks**
```bash
# Check if bot is running
ps aux | grep python

# Check logs
tail -f bot.log

# Check database
sqlite3 trades.sqlite "SELECT COUNT(*) FROM active_trades WHERE status='ACTIVE';"
```

## 🔧 **Configuration Options**

### **Signal Formats Supported**
1. **JUP Format**: `💎 BUY #JUP/USD at #KRAKEN ...`
2. **Simple Format**: `BTCUSDT LONG lev=10 entries=60000,59800...`
3. **FIDDE Format**: `📍Mynt: #CATI/USDT 🟢 LÅNG ...`
4. **Lux Leak Format**: `🔴 Long CHESSUSDT Entry : 1) 0.08255...`

### **Leverage Modes**
- **SWING**: 6x leverage only
- **DYNAMIC**: 7.5x+ leverage
- **FAST**: 10x+ leverage
- **Auto SL**: -2% + FAST x10 when no SL provided

### **Risk Management**
- **Per Trade**: 2% of equity (configurable)
- **Capacity**: 100 concurrent trades maximum
- **Deduplication**: 120 seconds window
- **Quantization**: Bybit tick/step enforcement

## 🚨 **Important Notes**

### **Testnet First**
- Always test with Bybit testnet before mainnet
- Use testnet API keys in `.env`
- Verify all functionality before switching to mainnet

### **Security**
- Never commit `.env` file
- Use environment variables in production
- Rotate API keys regularly
- Monitor for unauthorized access

### **Backup**
- Regular database backups
- Configuration backup
- Log rotation and archival

## 📞 **Support**

### **Troubleshooting**
1. **Signal not detected**: Check channel names in `SRC_CHANNEL_NAMES`
2. **Telegram connection issues**: Re-run `python telegram_auth.py`
3. **Bybit API errors**: Check API keys and permissions
4. **Database locked**: Stop all bot instances, delete session files

### **Performance Tuning**
- Adjust `MAX_CONCURRENT_TRADES` based on capital
- Tune `DEDUP_SECONDS` based on signal frequency
- Monitor memory usage with large trade volumes

## 🎯 **Success Metrics**

The bot is production-ready when:
- ✅ All signal formats parse correctly
- ✅ ACK-gated trading works
- ✅ Leverage policy enforced
- ✅ Advanced features active
- ✅ Reports generated on schedule
- ✅ Structured logging working
- ✅ Capacity limits respected
- ✅ Idempotency prevents duplicates

**The bot is now fully compliant with all client requirements!** 🚀