bybit-copybot-pro
==================

Beginner-friendly starter for Tomas's Bybit copy-bot. Step 1 sets up a clean Python 3.10 workspace with Telethon and testing ready.

Quick start (Windows, PowerShell):
1. Ensure Python 3.10 is installed (e.g., `py -3.10 -V`)
2. Create venv and install deps:
   - `py -3.10 -m venv .venv`
   - `.\.venv\Scripts\python.exe -m pip install --upgrade pip`
   - `.\.venv\Scripts\pip.exe install -r requirements.txt`
3. Run tests: `.\\.venv\\Scripts\\pytest.exe -q` (should show "collected 0 items")

Project layout:

```
bybit-copybot-pro/
├── app/
│   └── __init__.py
├── tests/
├── requirements.txt
├── .env
├── README.md
```

