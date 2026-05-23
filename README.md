# GraphRAG Studio — Local Graph RAG & Knowledge Graph Mapper

A production-grade local-first application for Graph RAG (Retrieval Augmented Generation) with knowledge graph construction, visualization, and natural-language querying.

## Architecture

```
Data Sources → ETL Pipeline → Neo4j Knowledge Graph → Embeddings + FAISS → RAG Engine → Ollama LLM → Dashboard UI
```

## Features

- **Database Connectors** — PostgreSQL, MySQL, SQLite, CSV ingestion
- **ETL + Knowledge Graph Pipeline** — Extract, normalize, NER, graph build, embeddings, FAISS indexing, community detection
- **Graph RAG Engine** — Hybrid graph + vector retrieval, Cypher generation, multi-hop traversal
- **Ollama Integration** — Auto-detect local models, benchmark cards, model selection
- **Live Knowledge Graph UI** — Interactive Cytoscape.js visualization with physics simulation
- **Query Console** — Natural language querying with pipeline visualization
- **System Dashboard** — Real-time CPU, RAM, GPU metrics, service health

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, SQLAlchemy, Neo4j Driver, sentence-transformers, FAISS |
| Frontend | React, TypeScript, TailwindCSS, Framer Motion, Cytoscape.js, Recharts |
| Database | Neo4j (graph), SQLite (relational), FAISS (vectors) |
| LLM | Ollama (llama3.1, mistral, phi3, etc.) |
| Infra | Docker, Docker Compose |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.10+
- Neo4j (or Docker)
- Ollama (optional, for LLM features)

### Option 1: Run with Scripts

**Windows:**
```bash
run.bat
```

**Mac/Linux:**
```bash
chmod +x run.sh
./run.sh
```

### Option 2: Docker

```bash
docker compose -f docker/docker-compose.yml up --build
```

### Option 3: Manual

**Backend:**
```bash
cd apps/backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend:**
```bash
cd apps/frontend
npm install
npm run dev
```

## URLs

| Service | URL |
|---------|-----|
| Frontend Dashboard | http://localhost:3000 |
| FastAPI Backend | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |
| Neo4j Browser | http://localhost:7474 |

## Project Structure

```
├── apps/
│   ├── frontend/          # React + TypeScript UI
│   │   └── src/
│   │       ├── pages/      # Tab pages (Dashboard, Architecture, Pipeline, etc.)
│   │       ├── components/ # Reusable UI components
│   │       ├── store/      # Zustand state management
│   │       ├── lib/        # API client and utilities
│   │       └── types/      # TypeScript type definitions
│   └── backend/           # FastAPI Python backend
│       └── app/
│           ├── api/        # REST API routes
│           ├── core/       # Config, database, WebSocket manager
│           ├── models/     # SQLAlchemy ORM models
│           ├── schemas/    # Pydantic API schemas
│           └── services/   # Business logic (graph, RAG, Ollama, ETL, etc.)
├── docker/                 # Docker configuration
├── run.bat                 # Windows startup script
├── run.sh                  # Unix/Mac startup script
├── .env                    # Environment configuration
└── README.md
```

## API Endpoints

### Data Sources
- `GET /api/datasources` — List all data sources
- `POST /api/datasources` — Create data source
- `DELETE /api/datasources/{id}` — Delete data source

### Pipelines
- `GET /api/pipelines` — List pipelines
- `POST /api/pipelines` — Create pipeline
- `POST /api/pipelines/{id}/run` — Execute pipeline

### Graph
- `GET /api/graph` — Get graph data
- `GET /api/graph/stats` — Get graph statistics
- `POST /api/graph/cypher` — Execute Cypher query

### Query
- `POST /api/query` — Natural language query
- `GET /api/query/history` — Query history

### Ollama
- `GET /api/ollama/status` — Check Ollama availability
- `GET /api/ollama/models` — List available models
- `POST /api/ollama/models/select` — Select active model
- `POST /api/ollama/pull` — Pull a model

### Dashboard
- `GET /api/dashboard/metrics` — System metrics
- `GET /api/dashboard/health` — Service health

### WebSocket
- `ws://localhost:8000/ws` — Real-time metrics and updates

### Utilities
- `POST /api/seed` — Seed demo data

## License

MIT
