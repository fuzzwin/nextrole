"""Output-quality regressions for the generated PDFs, using synthetic data only."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from pypdf import PdfReader

from campus_agent.application_review import focus_application
from campus_agent.document_style import DocumentStyle
from campus_agent.documents import DOCUMENT_STYLE_VERSION, generate_documents, letter_date
from campus_agent.models import Experience, Job, Profile
from campus_agent.packet_checks import check_pdfs
from campus_agent.tailor import first_person_summary, grounded_cover, local_selection, prepare_text


def nurse(**changes):
    data = dict(
        name="Sam Example", headline="Registered Nurse", email="sam@example.com", phone="0400 000 000",
        location="Geelong VIC",
        summary="Registered nurse with six years of acute ward experience, including two years as a team leader.",
        education=["Bachelor of Nursing, Example University, 2018"],
        skills=["Patient assessment", "Medication administration", "Wound care"],
        experience=[Experience(organization="Example Health", role="Registered Nurse", dates="2020 - present", bullets=[
            "Recorded care in the electronic medical record each shift.",
            "Precepted eight graduate nurses through their first rotation",
            "Led after-hours shifts of six nurses on a surgical ward."])])
    data.update(changes)
    return Profile(**data)


def educator_job():
    return Job(source_id="synthetic", title="Clinical Nurse Educator", employer="Example Community Health",
               url="https://example.com/jobs/educator", location="Melbourne VIC",
               description="Design education programs and precepting support for nursing staff.")


def packet(profile, job, mode="focused"):
    draft = prepare_text(job, profile, "local")
    style = DocumentStyle(resume_focus=mode)
    draft["document_preferences"] = style.model_dump()
    draft = focus_application(job, profile, draft, mode)
    draft["cover_letter"] = grounded_cover(job, profile, draft)
    draft.update(document_style_version=DOCUMENT_STYLE_VERSION, job_identity=job.identity, job_revision=job.revision)
    return draft


def text(path):
    return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)


def test_letter_date_is_australian_long_form():
    today = datetime.now(ZoneInfo("Australia/Melbourne"))
    assert letter_date("Australia/Melbourne") == f"{today.day} {today:%B %Y}"
    assert not re.search(r",|^0", letter_date())


def test_cover_letter_has_australian_date_and_reads_in_first_person(tmp_path):
    user, job = nurse(), educator_job()
    prepared = packet(user, job)
    generate_documents(tmp_path, job, user, prepared, timezone="Australia/Melbourne")
    letter = " ".join(text(tmp_path / "Cover Letter.pdf").split())
    assert letter_date("Australia/Melbourne") in letter
    assert "I am a registered nurse with six years" in letter
    assert "I precepted eight graduate nurses through their first rotation." in letter  # period added
    assert "I recorded care" in letter or "I led after-hours" in letter
    assert len(PdfReader(tmp_path / "Cover Letter.pdf").pages) == 1
    for bad in ("None", "[]", "{", "TODO", "I I "):
        assert bad not in letter


def test_summary_rewording_only_applies_when_it_repeats_the_headline():
    assert first_person_summary(nurse()).startswith("I am a registered nurse with")
    already = nurse(summary="I have six years of ward experience on surgical and medical units.")
    assert first_person_summary(already) == already.summary
    unrelated = nurse(headline="Nurse Educator", summary="Passionate about patient safety and teaching.")
    assert first_person_summary(unrelated) == unrelated.summary


def test_tailoring_matches_word_forms_for_any_occupation():
    ranked = local_selection(educator_job(), nurse()).bullet_ids
    assert ranked[0] == "0:1"  # "Precepted" ranks first for an advert about "precepting"


def test_resume_text_reads_body_before_footer(tmp_path):
    user, job = nurse(), educator_job()
    generate_documents(tmp_path, job, user, packet(user, job), timezone="Australia/Melbourne")
    extracted = PdfReader(tmp_path / "Resume.pdf").pages[0].extract_text()
    assert extracted.startswith("Sam Example\nsam@example.com")
    assert extracted.rstrip().endswith("1")


def test_nurse_resume_has_no_it_headings_or_empty_sections(tmp_path):
    user = nurse(skills=[], education=[])
    job = educator_job()
    generate_documents(tmp_path, job, user, packet(user, job), timezone="Australia/Melbourne")
    resume = text(tmp_path / "Resume.pdf")
    assert "TECHNICAL" not in resume
    assert "SKILLS" not in resume and "EDUCATION" not in resume
    assert "EXPERIENCE" in resume
    assert check_pdfs(tmp_path, job, user, prepared=packet(user, job))["errors"] == []


def test_page_limit_message_says_what_to_do(tmp_path):
    bullets = ["Delivered patient care task %d including assessment, medication administration and documentation "
               "in the electronic medical record for a group of patients each shift." % i for i in range(60)]
    user = nurse(experience=[Experience(organization="Example Health", role="Registered Nurse",
                                        dates="2020 - present", bullets=bullets)])
    job = educator_job()
    prepared = packet(user, job, "complete")
    generate_documents(tmp_path, job, user, prepared, timezone="Australia/Melbourne")
    errors = check_pdfs(tmp_path, job, user, {"resume_pages": 2}, prepared)["errors"]
    message = next(e for e in errors if "review limit" in e)
    assert "runs to" in message and "Focused" in message and "prepare again" in message


def test_saved_file_names_are_human_friendly_and_safe(tmp_path):
    from fastapi.testclient import TestClient
    from campus_agent.workspace import Workspace
    from campus_agent.workspace_web import create_workspace_app, download_name

    class Bridge:
        def call(self, *args, **kwargs):
            return {}
        def pending_approvals(self):
            return []
        def close(self):
            pass

    workspace = Workspace(tmp_path, Bridge())
    try:
        workspace.save_profile(nurse())
        row = {"payload": '{"title": "Registered Nurse / Surgical <Ward>", "employer": "Example: Hospital"}'}
        name = download_name(workspace, row, "resume")
        assert name == "Sam Example - Resume - Registered Nurse Surgical Ward - Example Hospital.pdf"
        assert not re.search(r'[\\/:*?"<>|]', name)
        assert download_name(workspace, {"payload": "not json"}, "cover") == "Sam Example - Cover Letter.pdf"
        assert TestClient  # the route itself is exercised in the browser run
    finally:
        workspace.close()
