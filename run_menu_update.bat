@echo off
echo Running menu update script...
cd /d "%~dp0"

REM Activate virtual environment if it exists
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found. Running with system Python.
)

python update_menu.py

echo.
echo Menu update completed.
echo Press any key to exit...
pause > nul