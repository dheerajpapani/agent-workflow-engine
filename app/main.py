from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import routers and startup helpers
from app.api import graph, websocket as websocket_api
from app.engine.registry import tool_registry
from app.workflows.code_review.nodes import register_code_review_tools

# Resolve paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks: register tools
    register_code_review_tools(tool_registry)
    print("✓ Tool registry initialized with code review tools")
    yield
    print("✓ Application shutdown complete")

app = FastAPI(
    title="Agent Workflow Engine",
    description="A minimal graph-based workflow engine with async execution and WebSocket logging",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS (open for dev; restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers FIRST so API routes take precedence over static files
app.include_router(graph.router, prefix="/graph", tags=["Graph Workflow"])
# websocket router contains the global manager and the /ws/{run_id} endpoint
app.include_router(websocket_api.router, tags=["WebSocket"])

# Health & tools endpoints (API routes)
@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/tools", tags=["Tools"])
async def list_tools():
    from app.engine.registry import tool_registry as registry
    return {"tools": list(registry.list_tools()), "count": len(registry.list_tools())}

# Now mount static frontend as a fallback (only for unmatched paths)
if FRONTEND_DIST.exists():
    # Mount after routers so API routes are reachable
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

    # Optional explicit root file response (StaticFiles already handles it, but keep for clarity)
    @app.get("/", include_in_schema=False)
    async def root_index():
        index_file = FRONTEND_DIST / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"status": "healthy", "message": "Frontend built but index.html not found."}
else:
    # Inform when frontend is not built
    @app.get("/", include_in_schema=False)
    async def root_no_frontend():
        return {
            "status": "healthy",
            "service": "Agent Workflow Engine",
            "message": "Frontend not built. Run `cd frontend && npm install && npm run build` then restart backend.",
        }
