@echo off
echo ============================================
echo   RegisterBot - Auto Build .exe (Phone Mode)
echo ============================================
echo.

REM Step 1: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python chua duoc cai dat!
    echo Tai Python tai: https://www.python.org/downloads/
    exit /b 1
)
echo [OK] Python da san sang

REM Step 2: Install dependencies (no Playwright, no PyQt5)
echo.
echo [1/3] Cai dat thu vien...
pip install openpyxl pandas pyinstaller httpx flask -q
if errorlevel 1 goto error

REM Step 3: Build .exe
echo.
echo [2/3] Build file .exe...
pyinstaller --onedir --console --noconfirm ^
    --name "RegisterBot" ^
    --hidden-import "openpyxl" ^
    --hidden-import "pandas" ^
    --hidden-import "httpx" ^
    --hidden-import "imaplib" ^
    --hidden-import "email" ^
    --hidden-import "flask" ^
    --hidden-import "sqlite3" ^
    --hidden-import "src" ^
    --hidden-import "src.xiaowei_client" ^
    --hidden-import "src.phone_bot" ^
    --hidden-import "src.db_handler" ^
    --hidden-import "src.excel_handler" ^
    --hidden-import "src.gmail_otp" ^
    --hidden-import "src.config" ^
    --hidden-import "src.captcha_helper" ^
    --hidden-import "src.web_server" ^
    --hidden-import "src.mock_captcha" ^
    --add-data "src/__init__.py;src" ^
    --add-data "src/config.py;src" ^
    --add-data "src/xiaowei_client.py;src" ^
    --add-data "src/phone_bot.py;src" ^
    --add-data "src/db_handler.py;src" ^
    --add-data "src/excel_handler.py;src" ^
    --add-data "src/gmail_otp.py;src" ^
    --add-data "src/mock_captcha.py;src" ^
    --add-data "src/captcha_helper.py;src" ^
    --add-data "src/web_server.py;src" ^
    --add-data "src/web;src/web" ^
    --add-data "data/accounts.xlsx;data" ^
    main.py
if errorlevel 1 goto error

REM Step 4: Copy files to dist/
echo.
echo [3/3] Chuan bi thu muc release...
mkdir dist\RegisterBot\src 2>nul
mkdir dist\RegisterBot\data 2>nul
mkdir dist\RegisterBot\data\screenshots 2>nul
mkdir dist\RegisterBot\logs 2>nul

copy src\config.py dist\RegisterBot\src\config.py >nul
copy src\xiaowei_client.py dist\RegisterBot\src\xiaowei_client.py >nul
copy src\phone_bot.py dist\RegisterBot\src\phone_bot.py >nul
copy src\db_handler.py dist\RegisterBot\src\db_handler.py >nul
copy src\excel_handler.py dist\RegisterBot\src\excel_handler.py >nul
copy src\__init__.py dist\RegisterBot\src\__init__.py >nul
copy data\accounts.xlsx dist\RegisterBot\data\accounts.xlsx >nul
copy .env.example dist\RegisterBot\.env.example >nul
if exist data\config.json copy data\config.json dist\RegisterBot\data\config.json >nul
if exist data\registered_accounts.db copy data\registered_accounts.db dist\RegisterBot\data\registered_accounts.db >nul
if exist src\gmail_otp.py copy src\gmail_otp.py dist\RegisterBot\src\ >nul
if exist src\mock_captcha.py copy src\mock_captcha.py dist\RegisterBot\src\ >nul
if exist src\captcha_helper.py copy src\captcha_helper.py dist\RegisterBot\src\ >nul
if exist src\web_server.py copy src\web_server.py dist\RegisterBot\src\ >nul
xcopy /E /I /Y src\web dist\RegisterBot\src\web >nul

echo.
echo ============================================
echo   BUILD THANH CONG!
echo   File .exe nam tai: dist\RegisterBot\RegisterBot.exe
echo   Che do: Phone (XiaoWei) + Web UI
echo ============================================
echo.
echo Noi dung thu muc dist\RegisterBot\:
dir dist\RegisterBot\
exit /b 0

:error
echo.
echo [ERROR] Build that bai! Xem log o tren.
exit /b 1


