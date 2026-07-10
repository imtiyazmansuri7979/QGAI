@echo off
setlocal
title QGAI - Set Console Font Arial
chcp 65001 >nul

echo ============================================================
echo   QGAI - SET CONSOLE FONT TO ARIAL
echo ------------------------------------------------------------
echo   This updates the current Windows user console defaults.
echo   Close and reopen QGAI .bat windows after this.
echo.
echo   Note: classic Windows Console may ignore Arial on some
echo   systems because it prefers fixed-width console fonts.
echo ============================================================
echo.

reg add "HKCU\Console" /v FaceName /t REG_SZ /d "Arial" /f >nul
reg add "HKCU\Console" /v FontFamily /t REG_DWORD /d 54 /f >nul
reg add "HKCU\Console" /v FontSize /t REG_DWORD /d 1048576 /f >nul
reg add "HKCU\Console" /v FontWeight /t REG_DWORD /d 400 /f >nul
reg add "HKCU\Console" /v CodePage /t REG_DWORD /d 65001 /f >nul

reg add "HKCU\Console\%%SystemRoot%%_System32_cmd.exe" /v FaceName /t REG_SZ /d "Arial" /f >nul
reg add "HKCU\Console\%%SystemRoot%%_System32_cmd.exe" /v FontFamily /t REG_DWORD /d 54 /f >nul
reg add "HKCU\Console\%%SystemRoot%%_System32_cmd.exe" /v FontSize /t REG_DWORD /d 1048576 /f >nul
reg add "HKCU\Console\%%SystemRoot%%_System32_cmd.exe" /v FontWeight /t REG_DWORD /d 400 /f >nul
reg add "HKCU\Console\%%SystemRoot%%_System32_cmd.exe" /v CodePage /t REG_DWORD /d 65001 /f >nul

echo Done. Close this window and open QGAI again.
echo If Windows ignores Arial, use Consolas/Cascadia Mono in console Properties.
echo.
pause
