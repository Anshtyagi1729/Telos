import os
import subprocess

from fastapi import FastAPI, Request
from fastapi.responses import Response

from api.db.database import engine
from api.db.models import Base
from api.routes import agents, projects, task

app = FastAPI(title="Dispatch API")
app.include_router(projects.router)
app.include_router(task.router)
app.include_router(agents.router)
# main.py


@app.api_route("/repos/{project_id}.git/{path:path}", methods=["GET", "POST"])
async def git_http_backend(project_id: str, path: str, request: Request):
    repo_path = f"/data/repos/{project_id}.git"

    if not os.path.exists(repo_path):
        return Response(status_code=404, content=b"Repo not found")

    env = {
        **os.environ,
        "GIT_PROJECT_ROOT": "/data/repos",
        "GIT_HTTP_EXPORT_ALL": "1",
        "PATH_INFO": f"/{project_id}.git/{path}",
        "REQUEST_METHOD": request.method,
        "CONTENT_TYPE": request.headers.get("content-type", ""),
        "QUERY_STRING": str(request.url.query),
        "REMOTE_ADDR": request.client.host if request.client else "127.0.0.1",
    }

    body = await request.body()

    proc = subprocess.run(
        ["git", "http-backend"], input=body, capture_output=True, env=env
    )

    if proc.returncode != 0:
        return Response(status_code=500, content=proc.stderr)

    raw = proc.stdout
    header_section, _, body = raw.partition(b"\r\n\r\n")

    headers = {}
    status_code = 200

    for line in header_section.decode(errors="replace").split("\r\n"):
        if not line:
            continue
        if line.startswith("Status:"):
            status_code = int(line.split()[1])
        elif ":" in line:
            key, _, value = line.partition(":")
            headers[key.strip()] = value.strip()

    return Response(content=body, status_code=status_code, headers=headers)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@app.get("/")
async def root():
    return {"status": "dispatcher is rnning"}
