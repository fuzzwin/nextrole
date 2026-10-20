from __future__ import annotations
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from sqlmodel import SQLModel, Field, create_engine
from .models import Job, utcnow

class JobRecord(SQLModel, table=True):
    __tablename__ = "jobs"
    id: str = Field(primary_key=True)
    revision: str
    source_id: str = Field(index=True)
    payload: str
    status: str = "discovered"
    seen_at: str
    updated_at: str
    packet_dir: str = ""
    error: str = ""

class SourceRecord(SQLModel, table=True):
    __tablename__ = "sources"
    id: str = Field(primary_key=True)
    initialized: int = 0
    last_scan: str = ""
    last_error: str = ""
    count: int = 0

class Store:
    def __init__(self, path: Path, cloud_url: str | None = None):
        self.path = path
        self.cloud_url = os.getenv("SQLITECLOUD_URL") if cloud_url is None else cloud_url
        if not self.cloud_url:
            path.parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(f"sqlite:///{path.as_posix()}")
            SQLModel.metadata.create_all(engine)
            engine.dispose()
        else:
            with self.connect() as db:
                db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, revision TEXT NOT NULL, source_id TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, seen_at TEXT NOT NULL, updated_at TEXT NOT NULL, packet_dir TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '')")
                db.execute("CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, initialized INTEGER NOT NULL DEFAULT 0, last_scan TEXT NOT NULL DEFAULT '', last_error TEXT NOT NULL DEFAULT '', count INTEGER NOT NULL DEFAULT 0)")

    @contextmanager
    def connect(self):
        if self.cloud_url:
            import sqlitecloud
            db = sqlitecloud.connect(self.cloud_url)
        else:
            db = sqlite3.connect(self.path, timeout=30)
            db.execute("PRAGMA busy_timeout=30000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, id: str) -> dict | None:
        with self.connect() as db:
            cur = db.execute("SELECT * FROM jobs WHERE id=?", (id,))
            row = cur.fetchone()
            return dict(zip([d[0] for d in cur.description], row)) if row else None

    def jobs(self) -> list[dict]:
        with self.connect() as db:
            cur = db.execute("SELECT * FROM jobs ORDER BY seen_at DESC")
            names = [d[0] for d in cur.description]
            rows = [dict(zip(names, row)) for row in cur.fetchall()]
        for row in rows:
            row["job"] = json.loads(row.pop("payload"))
        return rows

    def sources(self) -> list[dict]:
        with self.connect() as db:
            cur = db.execute("SELECT * FROM sources ORDER BY id")
            return [dict(zip([d[0] for d in cur.description], row)) for row in cur.fetchall()]

    def initialized(self, source_id: str) -> bool:
        with self.connect() as db:
            row = db.execute("SELECT initialized FROM sources WHERE id=?", (source_id,)).fetchone()
            return bool(row and row[0])

    def source_result(self, id: str, count: int, error: str = ""):
        with self.connect() as db:
            db.execute("INSERT INTO sources (id,initialized,last_scan,last_error,count) VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET initialized=MAX(sources.initialized,excluded.initialized),last_scan=excluded.last_scan,last_error=excluded.last_error,count=excluded.count",
                       (id, int(not error), utcnow(), error, count))

    def save_job(self, job: Job, status: str = "discovered") -> dict:
        previous = self.get(job.identity)
        now = utcnow()
        if previous and previous["revision"] == job.revision:
            return previous
        with self.connect() as db:
            db.execute("INSERT INTO jobs (id,revision,source_id,payload,status,seen_at,updated_at,packet_dir,error) VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,payload=excluded.payload,status=excluded.status,updated_at=excluded.updated_at,packet_dir='',error=''",
                       (job.identity, job.revision, job.source_id, job.model_dump_json(), status,
                        previous["seen_at"] if previous else now, now, "", ""))
        return self.get(job.identity)

    def update(self, id: str, status: str, packet_dir: str = "", error: str = ""):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?,packet_dir=?,error=?,updated_at=? WHERE id=?",
                       (status, packet_dir, error[:1000], utcnow(), id))
