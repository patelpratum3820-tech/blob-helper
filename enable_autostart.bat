@echo off
setlocal
echo ============================================================
echo   Enabling Auto-Start on Laptop Boot for Blob AI
echo ============================================================

set "VBS_PATH=%~dp0run_blob_silent.vbs"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_PATH=%STARTUP_DIR%\BlobAI.lnk"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%VBS_PATH%\"'; $s.WorkingDirectory = '%~dp0'; $s.Description = 'Blob AI Desktop Companion'; $s.Save()"

if exist "%SHORTCUT_PATH%" (
    echo [SUCCESS] Blob AI has been added to your Windows Startup folder!
    echo It will now open automatically every time your laptop starts up.
    echo (No CMD window, completely silent!)
) else (
    echo [ERROR] Could not create startup shortcut.
)

echo.
pause
