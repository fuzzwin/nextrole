from __future__ import annotations
import asyncio
import json
import os
from contextlib import contextmanager
from pathlib import Path
from .models import Settings, Profile, Job, utcnow
from .store import Store
from .sources import scrape
from .tailor import prepare_text
from .documents import generate_documents
from .mail import build_email, save_preview, send_email, check_mail_settings

@contextmanager
def process_lock(directory: Path):
    directory.mkdir(parents=True,exist_ok=True)
    lock=directory/".scan.lock"
    try:
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:
        raise RuntimeError(f"Another scan owns {lock}. If it crashed, verify its PID has exited before removing this lock.")
    try:
        with os.fdopen(fd,"w") as handle:
            handle.write(str(os.getpid()))
        yield
    finally:
        lock.unlink(missing_ok=True)

class Agent:
    def __init__(self, settings: Settings, profile: Profile, base: Path):
        self.settings=settings
        self.profile=profile
        self.base=base.resolve()
        self.artifacts=(base/settings.artifacts).resolve()
        self.store=Store((base/settings.database).resolve(), cloud_url="" if settings.offline else None)

    def prepare(self,job: Job) -> Path:
        prepared=prepare_text(job,self.profile,self.settings.ai_provider)
        directory=self.artifacts/job.identity[:16]/job.revision[:12]
        generate_documents(directory,job,self.profile,prepared)
        message=build_email(job,self.profile,prepared,directory)
        save_preview(message,directory)
        self.store.update(job.identity,"prepared",str(directory))
        return directory

    async def scan(self, send: bool = False, supplied: dict[str,list[Job]] | None = None) -> dict:
        if self.settings.offline and (send or supplied is None):
            raise RuntimeError("Offline demo mode: live scans and email are disabled")
        if self.settings.offline and self.settings.ai_provider != "local":
            raise RuntimeError("Offline mode requires local tailoring")
        if send:
            check_mail_settings(self.profile)
        report={"started_at":utcnow(),"sources":[],"new":0,"updated":0,"baseline":0,"prepared":0,"sent":0,"errors":[]}
        with process_lock(self.artifacts):
            for source in self.settings.sources:
                try:
                    jobs=supplied.get(source.id,[]) if supplied is not None else await scrape(source,self.artifacts/"diagnostics")
                    baseline=not self.store.initialized(source.id) and self.settings.first_run=="baseline"
                    # Store every discovered job before applying the per-scan preparation budget.
                    for job in jobs:
                        previous=self.store.get(job.identity)
                        changed=previous and previous["revision"]!=job.revision
                        if not previous:
                            report["baseline" if baseline else "new"]+=1
                        elif changed:
                            report["updated"]+=1
                        self.store.save_job(job,"baseline" if baseline else "discovered")
                    self.store.source_result(source.id,len(jobs))
                    report["sources"].append({"id":source.id,"count":len(jobs),"baseline":baseline})
                except Exception as exc:
                    message=f"{source.id}: {type(exc).__name__}"
                    # Do not persist credential-bearing exception strings from external SDKs.
                    self.store.source_result(source.id,0,message)
                    report["errors"].append(message)
                    report["sources"].append({"id":source.id,"error":message})
            pending=[r for r in self.store.jobs() if r["status"] in {"discovered","error","prepared"}]
            budget=self.settings.max_jobs_per_scan
            for row in pending:
                if budget<=0:
                    break
                if row["status"]=="prepared" and not send:
                    continue
                budget-=1
                job=Job.model_validate(row["job"])
                directory=Path(row["packet_dir"]) if row["packet_dir"] else None
                try:
                    if row["status"]!="prepared" or not directory or not (directory/"notification.eml").exists():
                        directory=self.prepare(job)
                        report["prepared"]+=1
                    if send:
                        # Persist before SMTP; after a crash or ambiguous network result never auto-resend.
                        self.store.update(job.identity,"sending",str(directory))
                        from email import policy
                        from email.parser import BytesParser
                        message=BytesParser(policy=policy.SMTP).parsebytes((directory/"notification.eml").read_bytes())
                        # Preview may predate current recipient configuration.
                        message.replace_header("From",os.environ["MAIL_FROM"])
                        message.replace_header("To",os.environ["MAIL_TO"])
                        try:
                            send_email(message)
                        except Exception:
                            self.store.update(job.identity,"needs_review",str(directory),"SMTP result uncertain; check inbox before retrying")
                            report["errors"].append(f"{job.identity[:12]}: delivery needs review")
                            continue
                        self.store.update(job.identity,"sent",str(directory))
                        report["sent"]+=1
                except Exception as exc:
                    self.store.update(job.identity,"error",str(directory or ""),type(exc).__name__)
                    report["errors"].append(f"{job.identity[:12]}: {type(exc).__name__}")
            (self.artifacts/"last-run.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
        return report

    def status(self) -> dict:
        jobs=self.store.jobs()
        states={}
        for job in jobs:
            states[job["status"]]=states.get(job["status"],0)+1
        return {"total":len(jobs),"states":states,"sources":self.store.sources(),
                "schedule":{"timezone":self.settings.timezone,"every_minutes":self.settings.interval_minutes,
                            "weekdays":self.settings.weekdays,"hours":[self.settings.start_hour,self.settings.end_hour]},
                "in_window":self.settings.in_window(),"ai_provider":self.settings.ai_provider,"offline":self.settings.offline}
