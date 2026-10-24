"""Browser UI regression anchors for explainable private candidate applications."""
from pathlib import Path


def test_role_application_controls_exist():
    html = (Path(__file__).resolve().parents[1] / "campus_agent/workspace.html").read_text(encoding="utf-8")
    for marker in (
        'id="p-headline"', 'id="p-interests"', 'id="technical-projects"',
        'id="add-technical-project"', 'id="doc-resume-focus"',
        '<option value="focused">', '<option value="complete">',
        'id="detail-tailoring-review"',
        "function technicalProject(", "function renderApplicationReview(",
        "documentStyleFields=", "resume_focus:'doc-resume-focus'",
        "p.technical_projects=", "p[key]=$('p-'+key).value.trim()",
    ):
        assert marker in html, f"Missing candidate-facing application UI: {marker}"


def test_reviews_do_not_embed_private_candidate_records():
    root = Path(__file__).resolve().parents[1]
    for relative in (
        "docs/ROLE-TAILORING.md",
        "campus_agent/application_review.py",
        "campus_agent/workspace.html",
        "tests/test_focused_application_2026.py",
    ):
        text = (root / relative).read_text(encoding="utf-8")
        assert "pete@spencerit.com.au" not in text.lower()
        assert "jesse.juzwin@gmail.com" not in text.lower()
        assert "Jesse Juzwin" not in text
