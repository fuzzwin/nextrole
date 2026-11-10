"""Build the Markdown brief and run the protected Proof Loop checks."""
import json
from pathlib import Path
import sys
from .career_contract import base


HERE = Path(__file__).resolve().parent
RESEARCH_AREAS = (
    "Business and history", "Customers and users", "Ownership",
    "Finances and trajectory", "Leadership and culture", "Market and policy",
    "Operating stack and remit",
)
CLAIM_KINDS = {
    "confirmed": {"employer", "regulator", "exchange"},
    "candidate_reported": {"candidate"},
    "market_reference": {"benchmark"},
    "reported_signal": {"secondary", "employer"},
    "inference": set(),
    "unknown": set(),
    "proposal": set(),
}
RANGE_KEYS = ("low", "high", "currency", "basis")


def load(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def money_range(entry):
    return f"{entry['currency']} {entry['low']:,}–{entry['high']:,} {entry['basis']}"


def render(observed, report):
    job = report["vacancy"]
    lines = [
        f"# {job['employer']} | {job['title']}",
        f"Checked {observed['checked_on']} · {job['id']}",
        f"**{job['status'].title()} · {job['mode']} · {job['employment']} · {', '.join(job['locations'])}**",
        f"[Original posting]({observed['sources'][job['source']]['url']})",
        f"**Decision** {report['decision']}",
        report["next_step"],
        f"**Application** {report['submission']['description']}",
        f"**Closing date** {job['deadline'] or 'Undisclosed in the listing'}",
        f"**Employer pay** {money_range(report['employer_pay']) if report['employer_pay'] else 'Undisclosed in the listing'}",
    ]
    if report.get("estimated_pay"):
        lines.append(f"**Discussion estimate** {money_range(report['estimated_pay'])}. {report['pay_note']}")
    for area in RESEARCH_AREAS:
        lines += ["", f"## {area}"]
        for entry in report["claims"]:
            if entry["area"] != area:
                continue
            refs = ", ".join(entry["sources"])
            label = entry["kind"].replace("_", " ").title()
            lines += [f"- **{label}** {entry['text']}" + (f" [{refs}]" if refs else "")]
            if entry.get("question"):
                lines.append(f"  Ask: {entry['question']}")
    lines += ["", "## Fit to the role"]
    for row in report["fit"]:
        lines.append(f"- **{row['requirement']} ({row['level']})** {row['detail']} [{', '.join(row['sources'])}]")
    lines += ["", "## Application files"]
    for item in report["application_files"]:
        lines.append(f"- **{item['label']}** {item['name']}")
    lines += ["", "## Interview practice"]
    for story in report["stories"]:
        refs = ", ".join(story["sources"])
        lines += [f"### {story['label']}", f"{story['answer']} [{refs}]", f"**Cues** {' → '.join(story['cues'])}"]
    lines += ["", "### Proposed first pilot", report["pilot"], "", "### Questions"]
    lines += [f"- {question}" for question in report["questions"]]
    lines += ["", "## Sources"]
    for key, src in observed["sources"].items():
        title = f"[{src['label']}]({src['url']})" if src.get("url") else src["label"]
        lines.append(f"- **{key}** {title}. {src['locator']}")
    return "\n\n".join(lines) + "\n"


def check_references(observed, report, brief):
    base(observed, report)
    sources = observed["sources"]
    findings = []
    claims = report["claims"]
    ids = [entry["id"] for entry in claims]
    if len(set(ids)) != len(ids):
        findings.append("Claim IDs must be unique.")
    if set(RESEARCH_AREAS) != {entry["area"] for entry in claims}:
        findings.append("Cover each required employer research area.")
    if any(not src.get("label") or not src.get("locator") for src in sources.values()):
        findings.append("Each source needs a label and a specific evidence locator.")
    for entry in claims:
        key = entry["id"]
        kind = entry["kind"]
        refs = entry["sources"]
        if kind not in CLAIM_KINDS or not entry["text"].strip() or any(ref not in sources for ref in refs):
            findings.append(f"{key} has a missing source, claim type or statement.")
            continue
        eligible = CLAIM_KINDS[kind]
        if eligible and not any(sources[ref]["kind"] in eligible for ref in refs):
            findings.append(f"{key} needs a source appropriate to {kind}.")
        if kind == "inference" and not refs:
            findings.append(f"{key} needs its basis for the inference.")
        if kind == "unknown" and not entry.get("question"):
            findings.append(f"{key} needs a question to resolve the unknown.")
    if brief != render(observed, report):
        findings.append("Regenerate the brief from the current assessment.")
    return findings


def check_decision(observed, report):
    base(observed, report)
    findings = []
    sources = observed["sources"]
    if report["vacancy"] != observed["vacancy"]:
        findings.append("Vacancy fields differ from the frozen employer observation.")
    if report["submission"] != observed["submission"]:
        findings.append("Submission status differs from the frozen evidence.")
    if report["employer_pay"] != observed["employer_pay"]:
        findings.append("Employer pay differs from the original listing observation.")
    estimate = report.get("estimated_pay")
    if estimate is not None:
        if (
            not all(key in estimate for key in RANGE_KEYS)
            or type(estimate["low"]) is not int
            or type(estimate["high"]) is not int
            or not 0 < estimate["low"] <= estimate["high"]
            or len(estimate["currency"]) != 3
            or not estimate["basis"]
            or not estimate.get("sources")
            or any(sources.get(ref, {}).get("kind") != "benchmark" for ref in estimate["sources"])
            or not report.get("pay_note")
        ):
            findings.append("The discussion estimate needs ordered figures, currency, basis and benchmark evidence.")
    fits = report["fit"]
    if not fits or len({item["requirement"] for item in fits}) != len(fits):
        findings.append("Map the material job requirements, with at least one distinct requirement.")
    for row in fits:
        kinds = {sources.get(ref, {}).get("kind") for ref in row["sources"]}
        if None in kinds or "employer" not in kinds or (
            row["level"] != "Gap" and "candidate" not in kinds
        ):
            findings.append(f"Evidence or an explicit gap is required for {row['requirement']}.")
    if (
        len(report["questions"]) < 3 or not report["pilot"].strip()
        or any(
            not story["answer"].strip() or not story["cues"] or not story["sources"]
            or any(ref not in sources for ref in story["sources"])
            for story in report["stories"]
        )
    ):
        findings.append("Give a proposed improvement scenario and three employer questions; source any included stories.")
    action = report["action"]
    vacancy = observed["vacancy"]
    submission = observed["submission"]
    if action not in {"apply", "check_portal_then_apply", "hold", "follow_up"}:
        findings.append("Choose a defined next action.")
    if action in {"apply", "check_portal_then_apply"}:
        if vacancy["status"] != "open" or submission["status"] == "submitted":
            findings.append("The next action could submit a closed or duplicate application.")
        if action == "apply" and submission["status"] != "not_submitted":
            findings.append("Resolve unconfirmed submission status before applying.")
    if not report["decision"].strip() or not report["next_step"].strip():
        findings.append("Give a decision and a specific next step.")
    return findings

