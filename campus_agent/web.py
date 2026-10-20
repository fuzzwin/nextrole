from __future__ import annotations
import asyncio
import json
import secrets
from pathlib import Path
from urllib.parse import urlsplit
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .pipeline import Agent

def create_app(agent: Agent) -> FastAPI:
    app=FastAPI(title="Campus Job Agent",docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=["127.0.0.1","localhost"])
    token=secrets.token_urlsafe(32)
    state={"busy":False,"last_result":None,"task":None}

    @app.middleware("http")
    async def headers(request,call_next):
        response=await call_next(request)
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Cache-Control"]="no-store"
        response.headers["Content-Security-Policy"]="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
        return response

    @app.get("/",response_class=HTMLResponse)
    def index():
        return Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8").replace("__SCAN_TOKEN__",token)

    @app.get("/api/status")
    def status():
        return {**agent.status(),"workspace":str(agent.base),"busy":state["busy"],"last_result":state["last_result"]}

    @app.get("/api/jobs")
    def jobs():
        return agent.store.jobs()

    @app.post("/api/scan")
    async def scan(request: Request):
        origin=request.headers.get("origin","")
        if request.headers.get("x-scan-token")!=token or origin!=f"{request.url.scheme}://{request.url.netloc}":
            raise HTTPException(403,"Open the dashboard locally to start a scan")
        if state["busy"]:
            raise HTTPException(409,"Scan already running")
        state["busy"]=True
        async def work():
            try:
                state["last_result"]=await asyncio.to_thread(lambda: asyncio.run(agent.scan(send=False)))
            except Exception as exc:
                state["last_result"]={"errors":[type(exc).__name__]}
            finally:
                state["busy"]=False
        state["task"]=asyncio.create_task(work())
        return {"started":True,"sends_email":False}

    @app.get("/files/{job_id}/{kind}")
    def file(job_id: str,kind: str):
        names={"resume":"Resume.pdf","cover":"Cover Letter.pdf","email":"notification.html","eml":"notification.eml"}
        row=agent.store.get(job_id)
        if not row or kind not in names or not row["packet_dir"]:
            raise HTTPException(404)
        target=(Path(row["packet_dir"])/names[kind]).resolve()
        if not target.is_relative_to(agent.artifacts) or not target.is_file():
            raise HTTPException(404)
        media={"resume":"application/pdf","cover":"application/pdf","email":"text/html","eml":"message/rfc822"}[kind]
        return FileResponse(target,media_type=media)
    return app

def serve(agent: Agent,port: int):
    import uvicorn
    print(f"Local dashboard: http://127.0.0.1:{port}",flush=True)
    uvicorn.run(create_app(agent),host="127.0.0.1",port=port,log_level="warning")
