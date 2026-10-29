from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import ValidationError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import Job, Profile
from .workspace import Preferences, Workspace
from .role_types import ROLE_TYPES


def create_workspace_app(workspace: Workspace):
    @asynccontextmanager
    async def lifespan(app):
        yield
        workspace.close()

    app = FastAPI(title="Job Agent", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])
    token = secrets.token_urlsafe(32)

    @app.middleware("http")
    async def security(request, call_next):
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("x-workspace-token") != token or request.headers.get("origin") != f"{request.url.scheme}://{request.url.netloc}":
                return JSONResponse({"detail": "Open the local app to make changes"}, status_code=403)
            if len(await request.body()) > 1_000_000:
                return JSONResponse({"detail": "Request is too large"}, status_code=413)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"detail": str(error)[:1500]}, status_code=400)

    @app.get("/", response_class=HTMLResponse)
    def index():
        return Path(__file__).with_name("workspace.html").read_text().replace("__WORKSPACE_TOKEN__", token)

    @app.get("/api/state")
    def state():
        return {"document_style": workspace.document_style_state(), "role_type_options": ROLE_TYPES, "kind": "job-workspace", "path": str(workspace.root), "jobs": workspace.jobs(),
            "preferences": workspace.preferences.model_dump(), "profile": workspace.profile.model_dump() if workspace.profile else None,
            "sources": workspace.sources_info(), "connections": workspace.get_meta("connections", {}),
            "activity": workspace.activity(), "approvals": workspace.bridge.pending_approvals(),
            "assessment_progress": workspace.get_meta("assessment_progress"), "last_search": workspace.get_meta("last_search"), "last_morning": workspace.get_meta("last_morning"),
            "applications": workspace.get_meta('applications', []), "application_sync": workspace.get_meta('application_sync'),
            "morning_schedule": workspace.get_meta("morning_schedule"), "alert_search": workspace.get_meta("job_alert_search")}

    @app.post('/api/document-style')
    async def document_style(request: Request):
        return workspace.save_document_style(await request.json())

    @app.post('/api/document-style/sample')
    async def style_sample(request: Request):
        data = await request.json()
        if not isinstance(data.get('job_id'), str):
            raise ValueError('Choose a saved, fully read role for your sample')
        return workspace.task('Prepare style sample', lambda: workspace.generate_style_sample(data['job_id']))

    @app.post('/api/document-style/approve')
    async def approve_style(request: Request):
        data = await request.json()
        return workspace.approve_document_style(data.get('sample_id'), data.get('fingerprint'),
                    data.get('reviewed_resume'), data.get('reviewed_cover'))

    @app.get('/api/document-style/samples/{sample_id}/{kind}')
    def sample_pdf(sample_id: str, kind: str):
        return FileResponse(workspace.sample_file(sample_id, kind), media_type='application/pdf')

    @app.get('/api/document-style/samples/{sample_id}/{kind}/pages/{number}')
    def sample_page(sample_id: str, kind: str, number: int):
        return FileResponse(workspace.sample_preview_file(sample_id, kind, number), media_type='image/png')

    @app.post("/api/connect")
    def connect():
        return workspace.task("Check Gmail and Drive", workspace.connect)

    @app.post("/api/discover")
    def discover():
        return workspace.task("Find Australian jobs", workspace.discover)

    @app.post("/api/discover/extended")
    def extended():
        return workspace.task("Extended Australian job search", lambda: workspace.discover(extended=True))

    @app.post("/api/morning")
    async def morning(request: Request):
        from .morning import run_morning
        data = await request.json()
        return workspace.task("Scheduled job packets", lambda: run_morning(workspace, extended=bool(data.get("extended", False)), session=data.get("session", "morning")))

    @app.post("/api/alerts")
    def alerts():
        return workspace.task("Find Gmail job alerts", workspace.alerts)

    @app.post('/api/applications/sync')
    def application_sync():
        return workspace.task('Check Gmail applications', workspace.sync_applications)

    @app.post("/api/settings")
    async def settings(request: Request):
        preferences = Preferences.model_validate(await request.json())
        if ((preferences.morning_enabled and not workspace.preferences.morning_enabled)
                or (preferences.standout_enabled and not workspace.preferences.standout_enabled)):
            workspace.require_style_approval()
        if preferences.morning_enabled:
            account = workspace.require_account("gmail")
            preferences = preferences.model_copy(update={"morning_recipient": account["email"]})
        workspace.save_preferences(preferences)
        return {"saved": True}

    @app.post("/api/profile")
    async def profile(request: Request):
        workspace.save_profile(Profile.model_validate(await request.json()))
        return {"saved": True}

    @app.post("/api/drive/search")
    async def drive_search(request: Request):
        payload = await request.json()
        query = str(payload.get("query", "resume"))[:200]
        def search():
            result = workspace.bridge.call("google_drive.search", {"query": query, "topn": 20})
            workspace.set_meta("drive_results", result)
            return result
        return workspace.task("Search Drive files", search)

    @app.get("/api/drive/results")
    def drive_results():
        return workspace.get_meta("drive_results", {"results": []})

    @app.get("/api/sources/{file_id}")
    def source(file_id: str):
        row = next((s for s in workspace.sources if s["id"] == file_id), None)
        if not row:
            raise HTTPException(404)
        return row

    @app.get("/api/alerts/{message_id}")
    def read_alert(message_id: str):
        return workspace.read_alert(message_id)

    @app.post("/api/sources/import")
    async def import_source(request: Request):
        payload = await request.json()
        return workspace.task("Import Drive source", lambda: workspace.import_source(str(payload["file_id"]), payload.get("kind", "resume")))

    @app.post("/api/sources/activate")
    async def activate_source(request: Request):
        payload = await request.json()
        return workspace.task("Use selected résumé", lambda: workspace.activate_resume(str(payload["file_id"])))

    @app.post("/api/jobs")
    async def add_job(request: Request):
        data = await request.json()
        from_alert = data.pop("from_alert", False)
        job = Job.model_validate({**data, "source_id": "opportunity"})
        workspace.add_job(job, full=not from_alert)
        if not from_alert:
            workspace.set_meta('location_override:'+job.identity, job.location)
        return {"id": job.identity}

    @app.post('/api/jobs/{job_id}/top')
    async def top_listing(job_id: str, request: Request):
        data = await request.json()
        return workspace.set_top_listing(job_id, data.get('top'))

    @app.post('/api/assess-filtered')
    async def assess_filtered(request: Request):
        data = await request.json()
        ids = data.get('job_ids', [])
        if not isinstance(ids, list) or len(ids)>10000 or not all(isinstance(i,str) for i in ids):
            raise ValueError('Invalid role selection')
        return workspace.task('Read and assess saved roles', lambda: workspace.assess_batch(ids))

    @app.post("/api/jobs/{job_id}/edit")
    async def edit_job(job_id: str, request: Request):
        data = await request.json()
        with workspace.write_lock:
            row, original = workspace.job(job_id)
            job = Job.model_validate({**original.model_dump(mode="json"), **data.get("job", {}), "source_id": original.source_id, "url": str(original.url)})
            workspace.add_job(job, full=True)
            workspace.set_meta('assessment_source:'+job.identity, None)
            workspace.set_meta('location_override:'+job.identity, job.location)
            with workspace.store.connect() as db:
                db.execute("UPDATE job_details SET stage=?,notes=? WHERE job_id=?", (str(data.get("stage", "saved"))[:40], str(data.get("notes", ""))[:12000], job_id))
        return {"saved": True}

    @app.post("/api/jobs/{job_id}/{action}")
    async def job_action(job_id: str, action: str, request: Request):
        operations = {
            "check-prepare": ("Check role and prepare packet", lambda: workspace.check_prepare(job_id)),
            "read": ("Read full job listing", lambda: workspace.hydrate(job_id)),
            "prepare": ("Prepare application PDFs", lambda: workspace.prepare(job_id)),
            "drive-resume": ("Save résumé to Drive", lambda: workspace.upload(job_id, "resume")),
            "drive-cover": ("Save cover letter to Drive", lambda: workspace.upload(job_id, "cover")),
            "draft": ("Create Gmail draft to your inbox", lambda: workspace.gmail_packet(job_id)),
            "email-self": ("Email packet to your inbox", lambda: workspace.gmail_packet(job_id, send=True)),
        }
        if action not in operations:
            raise HTTPException(404)
        payload = await request.json()
        if action in {"drive-resume", "drive-cover", "draft", "email-self"} and payload.get("reviewed") is not True:
            raise ValueError("Review the PDFs and tick the review box before using Drive or Gmail")
        label, operation = operations[action]
        return workspace.task(label, operation)

    @app.post("/api/approvals/{approval_id}")
    async def approval(approval_id: str, request: Request):
        data = await request.json()
        workspace.bridge.answer_approval(approval_id, data["action"], data.get("content"))
        return {"answered": True}

    @app.post("/api/actions/{action_id}/resolve")
    async def resolve_action(action_id: str, request: Request):
        data = await request.json()
        result = data.get("result")
        if result not in {"done", "retryable"} or data.get("checked_provider") is not True:
            raise ValueError("Check Gmail or Drive before resolving an uncertain write")
        with workspace.store.connect() as db:
            current = db.execute("SELECT status FROM actions WHERE id=?", (action_id,)).fetchone()
            if not current or current[0] != "needs_review":
                raise ValueError("This action does not need resolution")
            db.execute("UPDATE actions SET status=?,error='User checked provider and resolved this action' WHERE id=?", (result, action_id))
        return {"resolved": True}

    @app.get("/files/{job_id}/{kind}")
    def file(job_id: str, kind: str):
        names = {"resume": "Resume.pdf", "cover": "Cover Letter.pdf", "email": "notification.html"}
        row = workspace.store.get(job_id)
        if not row or not row["packet_dir"] or kind not in names:
            raise HTTPException(404)
        path = (Path(row["packet_dir"]) / names[kind]).resolve()
        if not path.is_relative_to(workspace.artifacts) or not path.is_file():
            raise HTTPException(404)
        return FileResponse(path, media_type="text/html" if kind == "email" else "application/pdf")

    return app


def serve_workspace(root: Path, port: int = 8877):
    import uvicorn
    workspace = Workspace(root)
    uvicorn.run(create_workspace_app(workspace), host="127.0.0.1", port=port, log_level="warning")
