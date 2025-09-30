# Bybit Copybot Pro - Configuration Guide

## 🔧 **Required Configuration**

The bot needs a `.env` file in the root directory with the following configuration:

### 1. Create `.env` file
Create a file named `.env` in the project root with this content:

```env
# Bybit Configuration (Testnet)
BYBIT_ENDPOINT=https://api-testnet.bybit.com
BYBIT_API_KEY=your_testnet_api_key_here
BYBIT_API_SECRET=your_testnet_api_secret_here
BYBIT_RECV_WINDOW=5000

# Telegram Configuration
TELEGRAM_API_ID=your_telegram_api_id_here
TELEGRAM_API_HASH=your_telegram_api_hash_here
TELEGRAM_SESSION=bybit_copybot_session

# Channel Configuration (by name, not ID)
SRC_CHANNEL_NAMES=CRYPTORAKETEN,Wolf Trading,SMART CRYPTO

# Risk Management
RISK_PER_TRADE=0.02
MAX_CONCURRENT_TRADES=100
DEDUP_SECONDS=120

# Timezone
TIMEZONE=Europe/Stockholm
```

### 2. Get Telegram API Credentials
1. Go to https://my.telegram.org/apps
2. Create a new application
3. Get your `API_ID` and `API_HASH`
4. Replace `your_telegram_api_id_here` and `your_telegram_api_hash_here` in the .env file

### 3. Get Bybit Testnet Credentials
1. Go to https://testnet.bybit.com/
2. Create an account and get API credentials
3. Replace `your_testnet_api_key_here` and `your_testnet_api_secret_here` in the .env file

### 4. Configure Channel Names
Replace the channel names in `SRC_CHANNEL_NAMES` with the actual names of your Telegram channels.

## 🚀 **Running the Bot**

1. **First time setup** (Telegram authentication):
   ```bash
   python telegram_auth.py
   ```

2. **Run the bot**:
   ```bash
   python -m app.main
   ```

## 🔍 **Troubleshooting**

If the bot doesn't detect signals:

1. **Check .env file exists** and has correct values
2. **Verify Telegram authentication** completed successfully
3. **Check channel names** match exactly (case-sensitive)
4. **Ensure you've joined** the channels with the bot account
5. **Check bot logs** for error messages

## 📱 **Testing Signal Detection**

Send a test signal in one of your whitelisted channels:
```
BTCUSDT LONG lev=10 entries=60000,59800 sl=59000 tps=61000,62000,63000
```

The bot should respond with:
- 📡 Signal received message
- 🔧 Leverage set message
- 📥 Entry orders placed message
- ✅ Position confirmed message
- 🎯 TP/SL placed message