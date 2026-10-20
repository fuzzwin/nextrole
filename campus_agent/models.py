from __future__ import annotations
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def canonical_url(value: str) -> str:
    p = urlsplit(value)
    query = sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                   if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid", "lang", "source", "ref"})
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), urlencode(query), ""))

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Experience(StrictModel):
    organization: str
    role: str
    dates: str
    bullets: list[str] = Field(min_length=1)

class Referee(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    role: str = ""
    organization: str = ""
    relationship: str = ""
    email: str = ""
    phone: str = ""
    sharing_confirmed: bool = False

class Profile(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    email: str
    phone: str = ""
    location: str = ""
    summary: str = Field(min_length=10, max_length=2000)
    education: list[str]
    skills: list[str]
    experience: list[Experience]
    availability: str = ""
    is_example: bool = False
    references_mode: Literal["omit", "on_request", "named"] = "omit"
    referees: list[Referee] = Field(default_factory=list)

class Source(StrictModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    url: HttpUrl
    kind: Literal["browser", "adp", "html", "json"] = "browser"
    allowed_hosts: list[str]
    job_selector: str = "a[href*='jobId='], a[href*='jobid='], a[href*='job-details']"
    empty_selector: str = ""
    title_selector: str = ""
    description_selector: str = "main"
    wait_seconds: int = Field(default=5, ge=0, le=30)

    @model_validator(mode="after")
    def validate_hosts(self):
        if self.url.host not in self.allowed_hosts:
            raise ValueError("Source URL host must be in allowed_hosts")
        return self

class Settings(StrictModel):
    offline: bool = False
    timezone: str = "America/Los_Angeles"
    interval_minutes: int = Field(default=10, ge=1, le=1440)
    weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4], min_length=1)
    start_hour: int = Field(default=7, ge=0, le=23)
    end_hour: int = Field(default=21, ge=1, le=24)
    database: str = "data/agent.db"
    artifacts: str = "artifacts"
    profile: str = "profile.example.json"
    ai_provider: Literal["local", "gemini"] = "local"
    first_run: Literal["baseline", "notify"] = "baseline"
    max_jobs_per_scan: int = Field(default=25, ge=1, le=250)
    sources: list[Source] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_schedule(self):
        ZoneInfo(self.timezone)
        if self.start_hour >= self.end_hour:
            raise ValueError("start_hour must be before end_hour")
        if any(d not in range(7) for d in self.weekdays):
            raise ValueError("weekdays must use Monday=0 through Sunday=6")
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("Source IDs must be unique")
        return self

    def in_window(self, now: datetime | None = None) -> bool:
        local = (now or datetime.now(timezone.utc)).astimezone(ZoneInfo(self.timezone))
        return local.weekday() in self.weekdays and self.start_hour <= local.hour < self.end_hour

class Job(StrictModel):
    source_id: str
    employer: str
    title: str = Field(min_length=2, max_length=300)
    url: HttpUrl
    description: str = Field(min_length=20, max_length=100_000)
    location: str = "Long Beach, CA"

    @property
    def identity(self) -> str:
        return hashlib.sha256(f"{self.source_id}|{canonical_url(str(self.url))}".encode()).hexdigest()

    @property
    def revision(self) -> str:
        text = re.sub(r"\s+", " ", self.title + "\n" + self.description).strip()
        return hashlib.sha256(text.encode()).hexdigest()

def load_settings(path: Path) -> Settings:
    return Settings.model_validate_json(path.read_text(encoding="utf-8"))

def load_profile(path: Path) -> Profile:
    return Profile.model_validate_json(path.read_text(encoding="utf-8"))
