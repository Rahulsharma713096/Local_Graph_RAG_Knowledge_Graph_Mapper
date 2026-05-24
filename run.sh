#!/usr/bin/env bash
set -e

NC='\033[0m'
CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'

echo -e "${CYAN}"
echo "============================================"
echo "  GraphRAG Studio — Knowledge Graph Mapper"
echo "  Local Graph RAG & Knowledge Graph Mapper"
echo "============================================"
echo -e "${NC}"

# Check prerequisites
command -v node >/dev/null 2>&1 || { echo -e "${RED}[ERROR] Node.js is required. Install from https://nodejs.org${NC}"; exit 1; }
echo -e "${GREEN}[OK]${NC} Node.js found: $(node --version)"

command -v python3 >/dev/null 2>&1 || command -v python >/dev/null 2>&1 || { echo -e "${RED}[ERROR] Python 3.10+ is required${NC}"; exit 1; }
PYTHON=$(command -v python3 || command -v python)
echo -e "${GREEN}[OK]${NC} Python found: $($PYTHON --version)"

# Check Docker (optional)
USE_DOCKER=false
if command -v docker >/dev/null 2>&1; then
    echo -e "${GREEN}[OK]${NC} Docker found"
else
    echo -e "${YELLOW}[INFO]${NC} Docker not found — will run services natively"
fi

# Parse arguments
for arg in "$@"; do
    [ "$arg" = "--docker" ] || [ "$arg" = "-d" ] && USE_DOCKER=true
    [ "$arg" = "--help" ] || [ "$arg" = "-h" ] && {
        echo "Usage: $0 [--docker|-d] [--help|-h]"
        echo ""
        echo "  --docker, -d    Run with Docker Compose instead of natively"
        echo "  --help, -h      Show this help message"
        exit 0
    }
done

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}[INFO]${NC} Stopping services..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}[INFO]${NC} All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  Starting GraphRAG Studio...${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Docker mode
if [ "$USE_DOCKER" = true ]; then
    echo -e "${YELLOW}[INFO]${NC} Starting with Docker..."
    if [ -f "docker/docker-compose.yml" ]; then
        docker compose -f docker/docker-compose.yml up --build
    else
        docker compose up --build
    fi
    exit 0
fi

# --- Check if backend port is available ---
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}[WARN]${NC} Port 8000 is already in use. Backend may fail to start."
fi

if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}[WARN]${NC} Port 3000 is already in use. Frontend may fail to start."
fi

# --- Check Neo4j availability (optional) ---
echo -e "${YELLOW}[INFO]${NC} Checking Neo4j availability..."
if command -v nc >/dev/null 2>&1; then
    if nc -z localhost 7687 2>/dev/null; then
        echo -e "${GREEN}[OK]${NC} Neo4j is available on port 7687"
    else
        echo -e "${YELLOW}[INFO]${NC} Neo4j is not running on port 7687 — using local fallback storage"
    fi
else
    echo -e "${YELLOW}[INFO]${NC} 'nc' not found — skipping Neo4j check"
fi

# --- Start Backend ---
echo ""
echo -e "${YELLOW}[1/2]${NC} Starting FastAPI Backend..."
cd "$(dirname "$0")/apps/backend"

# Create Python venv if needed
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[INFO]${NC} Creating Python virtual environment..."
    $PYTHON -m venv venv
fi

# Activate and install dependencies
source venv/bin/activate
echo -e "${YELLOW}[INFO]${NC} Installing Python dependencies..."
pip install -q -r requirements.txt

# Create data and logs directories
mkdir -p data logs

echo -e "${GREEN}[INFO]${NC} Starting backend on http://localhost:8000"
echo -e "${YELLOW}[INFO]${NC} API docs available at http://localhost:8000/docs"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --log-level info &
BACKEND_PID=$!

cd - > /dev/null

# Wait for backend to be ready
echo -e "${YELLOW}[INFO]${NC} Waiting for backend to start..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}[OK]${NC} Backend is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${YELLOW}[WARN]${NC} Backend did not respond in time — check logs"
    fi
    sleep 1
done

# --- Start Frontend ---
echo ""
echo -e "${YELLOW}[2/2]${NC} Starting React Frontend..."
cd "$(dirname "$0")/apps/frontend"

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}[INFO]${NC} Installing Node.js dependencies..."
    npm install
fi

echo -e "${GREEN}[INFO]${NC} Starting frontend on http://localhost:3000"
npm run dev &
FRONTEND_PID=$!

cd - > /dev/null

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  GraphRAG Studio is running!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  ${GREEN}Frontend:${NC}  http://localhost:3000"
echo -e "  ${GREEN}Backend:${NC}   http://localhost:8000"
echo -e "  ${GREEN}API Docs:${NC}  http://localhost:8000/docs"
echo -e "  ${GREEN}Neo4j:${NC}     http://localhost:7474 (if running)"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID 2>/dev/null
