from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi import HTTPException

from .database import run_migrations
from .routers import tables, fields, relationships, items, users, groups, perms, files, comments, view_prefs, images

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="Dynamic CRUD", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tables.router)
app.include_router(fields.router)
app.include_router(relationships.router)
app.include_router(items.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(perms.router)
app.include_router(files.router)
app.include_router(comments.router)
app.include_router(view_prefs.router)
app.include_router(images.router)


STATIC_DIR.mkdir(exist_ok=True)
assets_dir = STATIC_DIR / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static_assets")


@app.get("/{path:path}")
async def serve_frontend(path: str):
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    raise HTTPException(404, "Not found")
