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

# --- Start Backend ---
echo -e "${YELLOW}[1/2]${NC} Starting FastAPI Backend..."
cd apps/backend

if [ ! -d "venv" ]; then
    echo -e "${YELLOW}[INFO]${NC} Creating Python virtual environment..."
    $PYTHON -m venv venv
fi

source venv/bin/activate
echo -e "${YELLOW}[INFO]${NC} Installing Python dependencies..."
pip install -q -r requirements.txt

echo -e "${GREEN}[INFO]${NC} Starting backend on http://localhost:8000"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd ../..

# Wait for backend
echo -e "${YELLOW}[INFO]${NC} Waiting for backend to start..."
sleep 5

# --- Start Frontend ---
echo -e "${YELLOW}[2/2]${NC} Starting React Frontend..."
cd apps/frontend

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}[INFO]${NC} Installing Node.js dependencies..."
    npm install
fi

echo -e "${GREEN}[INFO]${NC} Starting frontend on http://localhost:3000"
npm run dev &
FRONTEND_PID=$!

cd ../..

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  GraphRAG Studio is running!${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""
echo -e "  ${GREEN}Frontend:${NC}  http://localhost:3000"
echo -e "  ${GREEN}Backend:${NC}   http://localhost:8000"
echo -e "  ${GREEN}API Docs:${NC}  http://localhost:8000/docs"
echo -e "  ${GREEN}Neo4j:${NC}     http://localhost:7474"
echo ""
echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""

# Wait for either process to exit
wait $BACKEND_PID $FRONTEND_PID
