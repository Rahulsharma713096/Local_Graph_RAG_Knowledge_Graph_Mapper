@echo off
title GraphRAG Studio — Knowledge Graph Mapper
setlocal enabledelayedexpansion

echo ============================================
echo   GraphRAG Studio — Knowledge Graph Mapper
echo   Local Graph RAG amp; Knowledge Graph Mapper
echo ============================================
echo.

:: Check for Node.js
where node >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js is not installed. Please install Node.js from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found: 
node --version

:: Check for Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed. Please install Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python found: 
python --version

:: Check for Docker (optional)
where docker >nul 2>nul
if %ERRORLEVEL% equ 0 (
    echo [OK] Docker found
    set DOCKER_AVAILABLE=true
) else (
    echo [INFO] Docker not found - will run services natively
    set DOCKER_AVAILABLE=false
)

echo.
echo ============================================
echo   Starting GraphRAG Studio...
echo ============================================
echo.

:: Parse arguments
set USE_DOCKER=false
:parse_args
if "%1"=="--docker" set USE_DOCKER=true
if "%1"=="-d" set USE_DOCKER=true
if not "%1"=="" shift & goto parse_args

if "%USE_DOCKER%"=="true" (
    echo [INFO] Starting with Docker...
    if exist docker-compose.yml (
        docker compose up --build
    ) else (
        docker compose -f docker/docker-compose.yml up --build
    )
    goto :end
)

:: Start Backend
echo [1/2] Starting FastAPI Backend...
cd apps\backend
if not exist venv (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
echo [INFO] Installing Python dependencies...
pip install -r requirements.txt --quiet
echo [INFO] Starting backend on http://localhost:8000
start "GraphRAG Backend" cmd /c "uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
cd ..\..

:: Wait for backend
echo [INFO] Waiting for backend to start...
timeout /t 5 /nobreak >nul

:: Start Frontend
echo [2/2] Starting React Frontend...
cd apps\frontend
if not exist node_modules (
    echo [INFO] Installing Node.js dependencies...
    call npm install
)
echo [INFO] Starting frontend on http://localhost:3000
start "GraphRAG Frontend" cmd /c "npm run dev"
cd ..\..

echo.
echo ============================================
echo   GraphRAG Studio is starting up!
echo ============================================
echo.
echo   Frontend:  http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo   Neo4j:     http://localhost:7474
echo.
echo   Press any key to stop all services...
echo ============================================
pause >nul

:: Cleanup
echo [INFO] Stopping services...
taskkill /f /im uvicorn.exe >nul 2>nul
taskkill /f /im node.exe >nul 2>nul
echo [INFO] All services stopped.

:end
endlocal
