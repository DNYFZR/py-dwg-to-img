@echo off
rem Execute this to create a debug backtrace of an Inkscape crash.

set TRACEFILE="%USERPROFILE%\inkscape_backtrace.txt"

echo Thanks for creating a debug backtrace!
echo.
echo After Inkscape starts, try to force the crash.
echo The backtrace will be recorded automatically.
echo.
echo Gathering system info...

echo --- INKSCAPE VERSION --- > %TRACEFILE%
inkscape.com --debug-info >> %TRACEFILE%
echo. >> %TRACEFILE%
echo --- SYSTEM INFO --- >> %TRACEFILE%
systeminfo >> %TRACEFILE%

echo.
echo Launching Inkscape, please wait...

echo. >> %TRACEFILE%
echo --- BACKTRACE --- >> %TRACEFILE%
gdb.exe -batch -ex "run --app-id-tag gdbbt" -ex "bt" inkscape.exe >> %TRACEFILE%

echo.
echo Backtrace written to %TRACEFILE%
echo Please attach this file when reporting the issue at https://inkscape.org/report
echo (remove personal information you do not want to share, e.g. your user name)
echo.

pause
