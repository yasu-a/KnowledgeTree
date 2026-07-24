@echo off
setlocal
set "PROJECT_ROOT=%~dp0"
start "" /b "%PROJECT_ROOT%.venv\Scripts\pythonw.exe" "%PROJECT_ROOT%main.py"
endlocal
