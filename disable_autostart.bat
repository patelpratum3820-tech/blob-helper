@echo off
setlocal
echo ============================================================
echo   Disabling Auto-Start for Blob AI
echo ============================================================

set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BlobAI.lnk"

if exist "%SHORTCUT_PATH%" (
    del "%SHORTCUT_PATH%"
    echo [SUCCESS] Blob AI auto-start has been removed from Windows Startup.
) else (
    echo Blob AI was not in the Startup folder.
)

echo.
pause
