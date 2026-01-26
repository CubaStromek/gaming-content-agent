@echo off
chcp 65001 >nul
title Gaming Content Agent - Starter

echo.
echo ══════════════════════════════════════════════════════════════════════
echo                    GAMING CONTENT AGENT - Starter
echo ══════════════════════════════════════════════════════════════════════
echo.

cd /d "%~dp0"

:: Kontrola Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python neni nainstalovan nebo neni v PATH!
    echo         Nainstaluj Python z https://python.org
    pause
    exit /b 1
)

:: Kontrola/vytvoreni venv
if not exist "venv\Scripts\activate.bat" (
    echo [INFO] Vytvarim virtualni prostredi...
    python -m venv venv
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Nepodarilo se vytvorit venv!
        pause
        exit /b 1
    )
    echo [OK] Virtualni prostredi vytvoreno
    echo.
)

:: Aktivace venv
echo [INFO] Aktivuji virtualni prostredi...
call venv\Scripts\activate.bat

:: Kontrola zavislosti (rychla kontrola - existuje flask?)
python -c "import flask" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [INFO] Instaluji zavislosti...
    pip install -r requirements.txt --quiet
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Nepodarilo se nainstalovat zavislosti!
        pause
        exit /b 1
    )
    echo [OK] Zavislosti nainstalovany
    echo.
)

:: Kontrola .env souboru
if not exist ".env" (
    echo [WARNING] Soubor .env neexistuje!
    echo           Zkopiruj .env.example na .env a nastav CLAUDE_API_KEY
    echo.
    if exist ".env.example" (
        echo [INFO] Kopiruji .env.example na .env...
        copy .env.example .env >nul
        echo [INFO] Uprav .env a nastav sve API klice!
        echo.
    )
)

echo.
echo ══════════════════════════════════════════════════════════════════════
echo   Spoustim Web Frontend na http://localhost:5000
echo   Pro ukonceni stiskni Ctrl+C
echo ══════════════════════════════════════════════════════════════════════
echo.

:: Otevreni prohlizece po 2 sekundach (na pozadi)
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:5000"

:: Spusteni Flask serveru
python web_app.py

:: Pokud server skonci
echo.
echo [INFO] Server ukoncen.
pause
