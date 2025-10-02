@echo off
REM Demo Test API Startup Script for Windows
REM This script sets up and starts the Demo Test API for APE testing

echo 🚀 Starting Demo Test API...

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js is not installed. Please install Node.js 18+ and try again.
    exit /b 1
)

echo ✅ Node.js version: 
node --version

REM Install dependencies if node_modules doesn't exist
if not exist "node_modules" (
    echo 📦 Installing dependencies...
    npm install
) else (
    echo ✅ Dependencies already installed
)

REM Build the project
echo 🔨 Building project...
npm run build

REM Set default environment variables if not set
if not defined PORT set PORT=3000
if not defined NODE_ENV set NODE_ENV=production
if not defined SESSION_SECRET set SESSION_SECRET=demo-secret
if not defined ERROR_RATE_503 set ERROR_RATE_503=0.05
if not defined ERROR_RATE_500 set ERROR_RATE_500=0.01
if not defined RESPONSE_DELAY_MIN set RESPONSE_DELAY_MIN=50
if not defined RESPONSE_DELAY_MAX set RESPONSE_DELAY_MAX=200

echo 🔧 Configuration:
echo    Port: %PORT%
echo    Environment: %NODE_ENV%
echo    Error Rate (503): %ERROR_RATE_503%
echo    Error Rate (500): %ERROR_RATE_500%
echo    Response Delay: %RESPONSE_DELAY_MIN%-%RESPONSE_DELAY_MAX%ms

REM Start the server
echo 🌟 Starting Demo Test API on port %PORT%...
echo 📍 Health check: http://localhost:%PORT%/api/health
echo 📍 API documentation: http://localhost:%PORT%/
echo.
echo Press Ctrl+C to stop the server

npm start