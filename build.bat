@echo off
echo Building Tailwind CSS...
echo.

REM Check if Node.js is installed
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Node.js is not installed or not in PATH
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

REM Check if npm is installed
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: npm is not installed or not in PATH
    pause
    exit /b 1
)

REM Install dependencies if node_modules doesn't exist
if not exist "node_modules" (
    echo Installing dependencies...
    npm install
    if %errorlevel% neq 0 (
        echo Error: Failed to install dependencies
        pause
        exit /b 1
    )
)

REM Build Tailwind CSS
echo Building Tailwind CSS...
npm run build-prod

if %errorlevel% equ 0 (
    echo.
    echo Success! Tailwind CSS has been built.
    echo The file is located at: static/css/tailwind.css
    echo.
    echo You can now run your Flask application.
) else (
    echo.
    echo Error: Failed to build Tailwind CSS
)

pause 