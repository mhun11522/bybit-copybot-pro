@echo off
REM ============================================================================
REM Bybit Copybot Pro - Easy Start Script
REM ============================================================================
REM Double-click this file to start the bot
REM ============================================================================

echo.
echo ============================================================================
echo   BYBIT COPYBOT PRO - STARTING
echo ============================================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo Please install Python 3.10 from https://www.python.org/downloads/
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

REM Run verification first
echo Running verification...
echo.
python verify_setup.py

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo   VERIFICATION FAILED
    echo ============================================================================
    echo.
    echo Please fix the issues above before starting the bot.
    echo See QUICK_START_GUIDE.md for help.
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo   ALL CHECKS PASSED - STARTING BOT
echo ============================================================================
echo.
echo The bot will start now.
echo.
echo You will be asked to authenticate with Telegram:
echo   1. Enter your phone number (with country code, e.g., +1234567890)
echo   2. Check Telegram app for 5-digit code
echo   3. Enter the code
echo.
echo Press any key to start the bot...
pause >nul

echo.
echo Starting bot...
echo.

REM Start the bot
python start.py

REM If we get here, the bot has stopped
echo.
echo ============================================================================
echo   BOT STOPPED
echo ============================================================================
echo.
pause

