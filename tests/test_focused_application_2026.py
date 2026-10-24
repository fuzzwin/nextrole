"""Synthetic test of focused applications and factual transparency.

No real user identity, private résumé, reference contact or network connection.
"""
import re
from pathlib import Path

from pypdf import PdfReader
from campus_agent.application_review import focus_application
from campus_agent.document_style import DocumentStyle
from campus_agent.documents import DOCUMENT_STYLE_VERSION, generate_documents
from campus_agent.models import Experience, Job, Profile, TechnicalProject
from campus_agent.packet_checks import check_content, validate_packet
from campus_agent.role_types import matched_types
from campus_agent.tailor import prepare_text, grounded_cover


def candidate():
    return Profile(
        name="Candidate Example", email="candidate@example.com",
        headline="Systems and Automation Specialist",
        summary="IT systems specialist supporting business teams with practical automation and training.",
        interests="Music and photography",
        skills=["Microsoft 365", "Power Automate", "NetSuite", "AI Hub guidance",
                "Intune", "User training", "ServiceNow", "Python",
                "SharePoint", "MCP", "SQL", "Vendor support", "Teams", "Reporting"],
        education=["ITIL 4 Foundation", "Bachelor of Applied Computing (deferred)"],
        experience=[
            Experience(organization="Example Manufacturing", role="IT Support Specialist",
                dates="Jun 2021–Present", bullets=[
                    "Delivered an approval workflow used by Quality for business documentation.",
                    "Built and tested an employee review workflow ahead of rollout.",
                    "Created an AI Hub guide and delivered a demonstration for colleagues.",
                    "Mapped business processes and reviewed business value with department managers.",
                    "Administered Microsoft 365 and Entra ID for corporate and laboratory users.",
                    "Coordinated application vendors on NetSuite ERP issues and upgrades.",
                    "Developed a reusable AI presentation template with output checks.",
                    "Created a business-request intake with stakeholder review.",
                    "Prepared internal support documentation and staff induction guides.",
                    "Contributed to a network upgrade project under the infrastructure team.",
                ]),
            Experience(organization="Example Support", role="IT Technician",
                dates="2019–2021", bullets=[
                    "Resolved ServiceNow incidents and escalated complex cases to vendors.",
                    "Installed endpoint devices and supported technical users.",
                    "Wrote troubleshooting guides for colleagues.",
                ]),
        ],
        technical_projects=[
            TechnicalProject(title="Route Puzzle", stage="private_release",
                summary="Built a privately published route-planning game and tested route scoring."),
            TechnicalProject(title="Agent to CAD", stage="prototype",
                summary="Prototyped MCP connection to 3D CAD software for a physical product."),
            TechnicalProject(title="Unrelated Artwork", stage="proposed",
                summary="Proposed digital art experiments; no application was built."),
        ],
    )


def vacancy():
    return Job(source_id="synthetic", title="AI Automation Specialist",
        employer="Example Retail", url="https://example.com/jobs/ai-role",
        location="Melbourne VIC",
        description="Use AI guidance, training, and Power Automate. Create dashboards in Power BI. "
                    "Work with business stakeholders and improve processes. "
                    "Submit a CV and a cover letter detailing relevant examples.")


def packet(profile,job,mode="focused",original=False):
    families=matched_types(job)
    role_type_id=families[0]["id"] if families else None
    draft=prepare_text(job,profile,"local",role_type_id=role_type_id)
    style=DocumentStyle(resume_focus=mode,fact_order="original" if original else "relevant",
                        resume_pages=2,layout="compact")
    draft["document_preferences"]=style.model_dump()
    if original:
        draft["skills"]=list(profile.skills)
        draft["experience"]=[exp.model_dump() for exp in profile.experience]
    draft=focus_application(job,profile,draft,style.resume_focus)
    draft["cover_letter"]=grounded_cover(job,profile,draft)
    draft.update(document_style_version=DOCUMENT_STYLE_VERSION,
                 job_identity=job.identity,job_revision=job.revision)
    return draft


def text_from_pdf(path):
    return " ".join(page.extract_text() or "" for page in PdfReader(path).pages)


def test_focused_achievements_keep_all_jobs_with_exact_claims():
    user=candidate()
    result=packet(user,vacancy())
    review=result["application_review"]
    assert review["mode"]=="focused"
    assert review["bullet_count"] < review["bullets_in_master"]
    assert review["omitted_examples"]
    assert [(e["organization"],e["role"],e["dates"]) for e in result["experience"]] == [
        (e.organization,e.role,e.dates) for e in user.experience]
    for i,entry in enumerate(result["experience"]):
        assert entry["bullets"]
        assert all(b in user.experience[i].bullets for b in entry["bullets"])
    assert len(result["skills"])<=12
    assert all(s in user.skills for s in result["skills"])
    assert "Power BI" in review["gaps"]


def test_complete_mode_does_not_delete_employment_facts():
    user=candidate()
    result=packet(user,vacancy(),mode="complete")
    assert sum(len(e["bullets"]) for e in result["experience"]) == sum(len(e.bullets) for e in user.experience)
    assert len(result["skills"])==len(user.skills)


def test_private_projects_are_staged_and_separate_from_employment(tmp_path):
    user=candidate()
    result=packet(user,vacancy())
    assert "Unrelated Artwork" not in result["application_review"]["selected_project_titles"]
    generate_documents(tmp_path,vacancy(),user,result,timezone="Australia/Melbourne")
    resume=text_from_pdf(tmp_path/"Resume.pdf")
    letter=text_from_pdf(tmp_path/"Cover Letter.pdf")
    assert "SELECTED TECHNICAL PROJECTS" in resume
    assert "Systems and Automation Specialist" in resume
    assert "Music and photography" in resume
    assert "Bachelor of Applied Computing (deferred)" in resume
    assert "IT Support Specialist" in resume
    assert "AI Automation Specialist" in letter
    assert "APPLICATION:" in letter
    assert len(PdfReader(tmp_path/"Resume.pdf").pages)<=2
    assert len(PdfReader(tmp_path/"Cover Letter.pdf").pages)==1
    report=validate_packet(tmp_path,vacancy(),user,result)
    assert report["passed"],report
    assert report["application_review"]==result["application_review"]


def test_focus_integrity_refuses_rewritten_metrics_or_project_stage():
    user=candidate()
    job=vacancy()
    result=packet(user,job)
    assert check_content(job,user,result)["passed"]
    result["experience"][0]["bullets"][0]="Saved the employer $900,000 a year."
    report=check_content(job,user,result)
    assert not report["passed"]
    assert any("source-backed" in issue for issue in report["errors"])
    unchanged=packet(user,job)
    if unchanged["technical_projects"]:
        unchanged["technical_projects"][0]["stage"]="in_use"
        assert not check_content(job,user,unchanged)["passed"]


def test_third_paragraph_uses_source_evidence_not_invented_management():
    user=candidate()
    result=packet(user,vacancy())
    paragraphs=result["cover_letter"]
    assert len(paragraphs)==5
    assert "Example Retail" in paragraphs[1]
    assert "Example Retail" in paragraphs[3]
    assert not any("Deputy" in text for text in paragraphs)
    assert not any("$900,000" in text for text in paragraphs)


def test_original_order_can_be_selected_without_fabricating_facts():
    user=candidate()
    result=packet(user,vacancy(),original=True)
    assert result["experience"][0]["bullets"][0]==user.experience[0].bullets[0]
    assert result["application_review"]["mode"]=="focused"
