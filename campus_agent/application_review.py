"""Private, explainable relevance selection for a candidate's saved source facts.

Nothing in this module is a qualification verifier or an ATS prediction. Job ads
are untrusted data. The original profile is never modified or published.
"""
from __future__ import annotations

import re
from collections import Counter

from .models import Job, Profile
from .tailor import local_selection, terms

# Only broad topics are displayed. Matching words are not proof of proficiency.
TOPICS = (
    ("IT support and identity", r"\b(?:it support|service desk|intune|entra id|endpoint|microsoft 365|service ?now)\b"),
    ("Business systems and ERP", r"\b(?:netsuite|erp|business applications?|enterprise applications?)\b"),
    ("Workflow automation", r"\b(?:automati\w*|power automate|workflow|sharepoint flows?)\b"),
    ("AI guidance and adoption", r"\b(?:ai enablement|ai adoption|ai training|ai hub|gen(?:erative)? ai|user enablement)\b"),
    ("AI agents and tooling", r"\b(?:ai agents?|copilot studio|mcp|reusable ai|large language models?|llms?)\b"),
    ("Reporting and dashboards", r"\b(?:dashboards?|reporting|data visualisation|business intelligence)\b"),
    ("Power BI", r"\bpower bi\b"),
    ("Business process and stakeholders", r"\b(?:business process|stakeholders?|business case|business value|requirements? mapping|process mapping)\b"),
    ("Project delivery", r"\b(?:project delivery|project management|agile|waterfall|uat|change management)\b"),
    ("Product design and prototyping", r"\b(?:product design|prototyp\w*|cad|fusion|3d print\w*|product visualisation)\b"),
)

MAX_FOCUSED_SKILLS = 12
MAX_FOCUSED_BULLETS = 14
MAX_PROJECTS = 2


def _tokens(value: str) -> set[str]:
    return terms(value)


def _ranked_project_indices(job: Job, profile: Profile) -> list[int]:
    job_title = _tokens(job.title)
    target = _tokens(job.title + " " + job.description)
    scored = []
    for index, project in enumerate(profile.technical_projects):
        tokens = _tokens(project.title + " " + project.summary)
        score = 5 * len(tokens & job_title) + len(tokens & target)
        # AI roles commonly want applied agent/prototype examples even if the
        # advertisement doesn't use the exact technology label (MCP/CAD).
        if re.search(r"\b(?:ai|artificial intelligence|agentic)\b", job.title, re.I) and re.search(
                r"\b(?:agent|mcp|llm|codex|prototype|ai-assisted)\b",
                project.title + " " + project.summary, re.I):
            score += 2
        scored.append((index, score))
    return [index for index, score in sorted(scored, key=lambda row: (-row[1], row[0])) if score > 0][:MAX_PROJECTS]


def _requirement_report(job: Job, profile: Profile, selected_bullets: list[str], selected_projects: list[dict]) -> list[dict]:
    listing = job.title + "\n" + job.description
    selected = list(selected_bullets) + [p["title"] + " " + p["summary"] for p in selected_projects]
    saved = list(profile.skills) + [b for e in profile.experience for b in e.bullets]
    saved += [p.title + " " + p.summary for p in profile.technical_projects]
    report = []
    for label, pattern in TOPICS:
        if not re.search(pattern, listing, re.I):
            continue
        evidence = next((s for s in selected if re.search(pattern, s, re.I)), None)
        if evidence:
            status = "candidate evidence to review"
        else:
            evidence = next((s for s in saved if re.search(pattern, s, re.I)), None)
            status = "in master, not selected" if evidence else "not evidenced in profile"
        report.append({"requirement": label, "status": status, "evidence": evidence or ""})
    return report[:12]


def focus_application(job: Job, profile: Profile, prepared: dict, mode: str) -> dict:
    """Select only exact source facts; preserve all employment entries and dates.

    complete: keep every professional bullet/skill (legacy full résumé mode).
    focused:  select ranked relevant facts without rewriting their content.
    Projects are independent from employment and are never silently relabelled.
    """
    if mode not in {"focused", "complete"}:
        raise ValueError("Unknown résumé focus")
    # Make a fresh dict. Caller retains its full saved source profile.
    output = dict(prepared)
    ranking = local_selection(job, profile, prepared.get("role_type_id"))
    ranked = dict.fromkeys(ranking.bullet_ids)
    if prepared.get("document_preferences", {}).get("fact_order") == "original":
        ranked = dict.fromkeys(f"{i}:{j}" for i, exp in enumerate(profile.experience)
                               for j in range(len(exp.bullets)))
    selected_ids: list[str] = []
    if mode == "complete":
        selected_ids = [f"{i}:{j}" for i, exp in enumerate(profile.experience) for j in range(len(exp.bullets))]
        output["experience"] = [exp.model_dump() for exp in profile.experience]
        output["skills"] = list(prepared["skills"])
    else:
        remaining = MAX_FOCUSED_BULLETS
        experiences = []
        for i, exp in enumerate(profile.experience):
            # Keep every formal job entry even when only one bullet is relevant.
            candidates = [id for id in ranked if id.startswith(f"{i}:")]
            cap = 7 if i == 0 else 3 if i == 1 else 2
            chosen = candidates[:min(cap, remaining)] if remaining else []
            if not chosen and exp.bullets:
                # Preserve an honest minimal summary of the history when there
                # are more career entries than the overall bullet budget.
                chosen = [f"{i}:0"]
            selected_ids += chosen
            remaining = max(0, remaining - len(chosen))
            experiences.append({**exp.model_dump(),
                                "bullets": [exp.bullets[int(k.split(":")[1])] for k in chosen]})
        output["experience"] = experiences
        skill_indexes = list(dict.fromkeys(ranking.skill_indices + list(range(len(profile.skills)))))
        output["skills"] = [profile.skills[k] for k in skill_indexes[:MAX_FOCUSED_SKILLS]]
    project_indices = _ranked_project_indices(job, profile)
    projects = [profile.technical_projects[i].model_dump() for i in project_indices]
    output["technical_projects"] = projects
    all_ids = [f"{i}:{j}" for i, exp in enumerate(profile.experience) for j in range(len(exp.bullets))]
    unused = [id for id in all_ids if id not in selected_ids]
    selected_bullets = [b for e in output["experience"] for b in e["bullets"]]
    requirements = _requirement_report(job, profile, selected_bullets, projects)
    output["application_review"] = {
        "mode": mode,
        "selected_bullet_ids": selected_ids,
        "selected_examples": selected_bullets[:10],
        "omitted_examples": [profile.experience[int(k.split(":")[0])].bullets[int(k.split(":")[1])] for k in unused][:8],
        "omitted_bullet_ids": unused,
        "selected_project_titles": [p["title"] for p in projects],
        "skills_selected": len(output["skills"]),
        "skills_in_master": len(profile.skills),
        "bullet_count": len(selected_ids),
        "bullets_in_master": len(all_ids),
        "requirements": requirements,
        "gaps": [r["requirement"] for r in requirements if r["status"] == "not evidenced in profile"],
        "tips": [
            "This is a keyword-based relevance draft, not a verified eligibility assessment.",
            "Check required experience, credentials, outcomes and dates against original records.",
            "Separate production work, private technical prototypes and proposed concepts.",
            "Check the actual employer's submission format, page breaks and referee permissions.",
        ],
    }
    return output
