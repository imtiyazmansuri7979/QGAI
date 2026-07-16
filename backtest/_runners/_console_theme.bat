@echo off
REM QGAI console theme: dark background + ANSI text colors.
REM Use from any runner:
REM   call "%~dp0_console_theme.bat"
REM or from a subfolder:
REM   call "%~dp0..\_console_theme.bat"

color 0F
for /f %%A in ('powershell -NoProfile -Command "[char]27"') do set "QGAI_ESC=%%A"

set "QGAI_RESET=%QGAI_ESC%[0m"
set "QGAI_DIM=%QGAI_ESC%[90m"
set "QGAI_RED=%QGAI_ESC%[91m"
set "QGAI_GREEN=%QGAI_ESC%[92m"
set "QGAI_YELLOW=%QGAI_ESC%[93m"
set "QGAI_BLUE=%QGAI_ESC%[94m"
set "QGAI_MAGENTA=%QGAI_ESC%[95m"
set "QGAI_CYAN=%QGAI_ESC%[96m"
set "QGAI_WHITE=%QGAI_ESC%[97m"
set "QGAI_BOLD=%QGAI_ESC%[1m"

exit /b 0
