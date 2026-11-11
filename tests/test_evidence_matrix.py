from campus_agent.evidence_matrix import matrix_requirements, summarise_matrix
from campus_agent.listing_view import listing_view


def matrix(text):
    return matrix_requirements(listing_view(text,'IT Support','Example Employer'))


def test_duties_are_captured_independently_of_legacy_criteria():
    rows=matrix('Key Responsibilities\n- Organise project workshops and meetings.\n- Provide scheduling and action tracking.\nSkills & Experience\n- Experience coordinating projects.')
    assert len(rows)==3
    assert summarise_matrix(rows)['duties']==2
    assert all(row['text']==row['quote'] for row in rows)


def test_optional_conditions_and_application_text_are_separate():
    rows=matrix('Requirements\n- Microsoft 365 support experience required.\n- CRM experience preferred.\n- Resume Required to apply\n- Work mode In office\n- AGSVA NV2 Security Clearance\n- Python is not required.')
    summary=summarise_matrix(rows)
    assert summary['scored']==1 and summary['optional']==1
    assert summary['conditions']==2 and summary['administrative']==2


def test_inline_heading_preserves_source_context_and_alternatives():
    view={'sections':[{'title':'Key Responsibilities','blocks':[
        {'kind':'paragraph','text':'Skills & Experience'},
        {'kind':'list','items':['Experience with SQL or Python.','Minimum 5 years of experience with SQL and Python.']},
    ]}]}
    rows=matrix_requirements(view)
    assert [row['logic'] for row in rows]==['any','all']
    assert rows[1]['text']=='Minimum 5 years of experience with SQL and Python.'
    assert all(row['category']=='requirement' for row in rows)


def test_repeated_source_is_one_criterion_and_benefits_are_excluded():
    rows=matrix('Requirements\n- Strong communication skills.\n- Strong communication skills.\nBenefits\n- Excellent holiday allowance.')
    assert len(rows)==1
    assert len(rows[0]['source_locations'])==2


def test_mixed_required_optional_scope_requires_review():
    rows=matrix('Requirements\n- You must have SQL experience, with Python experience preferred.')
    assert summarise_matrix(rows)['needs_review']==1


def test_recruiter_footer_does_not_inherit_requirement_status():
    rows=matrix('Requirements\n- Excellent stakeholder engagement and communication skills.\n\nCandidate Manager Example Person\n\nExample Recruiter is a wholly owned subsidiary of Parent.\n\nPlease indicate your preferred method of communication in your resume.')
    assert summarise_matrix(rows)['scored']==1
    assert not any(row['kind']=='competency' and 'subsidiary' in row['text'] for row in rows)


def test_unrecognised_inline_duty_heading_is_structurally_classified():
    rows=matrix_requirements({'sections':[{'title':'About the role','blocks':[
        {'kind':'paragraph','text':'Key role responsibilities'},
        {'kind':'list','items':['Partner with operational teams to identify AI opportunities.']},
        {'kind':'paragraph','text':'Skills & Experience'},
        {'kind':'list','items':['Experience with business improvement.']},
    ]}]})
    assert summarise_matrix(rows)['duties']==1
    assert summarise_matrix(rows)['scored']==2


def test_mixed_polarity_cannot_drop_the_required_half():
    rows=matrix('Requirements\n- Python is not required, but SQL experience is required.')
    assert summarise_matrix(rows)['needs_review']==1


def test_required_scope_inside_optional_section_requires_review():
    rows=matrix('Desirable\n- Must hold current CCNA certification.')
    assert summarise_matrix(rows)['needs_review']==1


def test_generic_project_evidence_cannot_fully_cover_a_detailed_task_list():
    from campus_agent.evidence_matrix import unconfirmed_group_scope
    requirement={'text':'Provide project support including scheduling, action tracking, status reporting and documentation management.', 'logic':'all'}
    facts=[{'text':'Manage IT projects with stakeholder coordination, testing, change control and handover documentation.'}]
    missing=unconfirmed_group_scope(requirement,facts)
    assert 'scheduling' in missing and 'tracking' in missing


def test_exact_m365_scope_passes_the_same_group_cross_check():
    from campus_agent.evidence_matrix import unconfirmed_group_scope
    requirement={'text':'Administer Microsoft 365, Exchange Online and Entra ID accounts and licensing', 'logic':'all'}
    facts=[{'text':'Administer Microsoft 365, Exchange Online and Entra ID accounts and licensing; resolve service incidents with vendor escalation.'}]
    assert unconfirmed_group_scope(requirement,facts)==[]
