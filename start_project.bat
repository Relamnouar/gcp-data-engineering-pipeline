@echo off

echo ===================================================
echo Starting Data Environment (Python 3.12)
echo ===================================================

:: Verify Docker daemon
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker Desktop is not running.
    echo Please start Docker and try again.
    pause
    exit /b
)

:: Clean up existing containers
echo [INFO] Cleaning up existing processes...
docker-compose down >nul 2>&1

:: Build and start container
echo [INFO] Building and starting container...
docker-compose up -d --build

if %errorlevel% neq 0 (
    echo.
    echo [CRITICAL ERROR] Build or startup failed.
    echo Review error messages above.
    pause
    exit /b
)

:: Verify container status
echo [INFO] Verifying container status...
timeout /t 3 /nobreak >nul
docker ps | findstr "ey-data-runner" >nul

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Container started but stopped immediately.
    echo Displaying logs for diagnostics:
    echo ---------------------------------------------------
    docker-compose logs
    echo ---------------------------------------------------
    pause
    exit /b
)

:: Connect to container
echo.
echo [SUCCESS] Environment ready. Connecting...
echo.
docker-compose exec data-pipeline bash

:: Cleanup on exit
echo.
echo [INFO] Session ended. Stopping container...
docker-compose down
echo Goodbye!
pause