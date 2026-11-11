import pytest
from campus_agent.transfer_fit import apply_guards, score, assess
from campus_agent.semantic import AssessmentError
from test_workspace import profile


def row(identifier, status, importance='standard'):
    return dict(id=identifier,text='Example',quote='Example',kind='competency',importance=importance,status=status,evidence=[])


def test_transfer_credits_and_unknown_confidence_are_separate():
    result=score([row('1','direct','essential'),row('2','strong_transfer','essential'),row('3','partial_transfer'),row('4','unknown')])
    assert result['percent']==80
    assert result['evidence_coverage_percent']==83
    assert result['assessed_weight']==5 and result['total_weight']==6
    assert result['coverage']['unconfirmed']==1 and not result['auto_eligible']


def test_unknown_is_not_a_confirmed_zero():
    assert score([row('1','unknown')])['percent'] is None
    assert score([row('1','unknown')])['evidence_coverage_percent']==0
    result=score([row('1','direct'),row('2','confirmed_gap')])
    assert result['percent']==50 and result['evidence_coverage_percent']==100


def test_optional_and_conditions_do_not_reduce_fit():
    optional=row('2','confirmed_gap','optional');condition={**row('3','confirmed_gap'),'kind':'condition'}
    assert score([row('1','direct'),optional,condition])['percent']==100


def test_skills_and_prototypes_cannot_earn_delivery_credit():
    req={'text':'Build production Power Automate workflows'}
    for fact in [dict(kind='skill',text='Power Automate'),dict(kind='work',text='Built prototype Power Automate workflows.')]:
        status,_=apply_guards(req,'direct',[fact],[fact])
        assert status=='foundation'


def test_missing_record_cannot_become_a_confirmed_gap():
    req={'text':'Hold CCNA certification'}
    status,_=apply_guards(req,'confirmed_gap',[dict(kind='education',text='ITIL Foundation')],[])
    assert status=='unknown'


def test_different_credential_cannot_prove_requested_credential():
    req={'text':'Hold CCNA certification'}
    status,_=apply_guards(req,'direct',[dict(kind='education',text='ITIL Foundation')],[])
    assert status=='unknown'


def test_current_process_and_explicit_equivalent_experience_can_be_reviewed():
    fact={'kind':'work','text':'Mapped business processes and delivered approval workflows.'}
    for text in ['Experience reviewing current processes and finding improvements.',
                 'Tertiary qualification in technology or equivalent practical experience.']:
        assert apply_guards({'text':text},'direct',[fact],[fact],scope_reviewed=True)[0]=='direct'
    assert apply_guards({'text':'Hold current CCNA certification.'},'direct',[fact],[fact],scope_reviewed=True)[0]=='unknown'


def test_model_cannot_infer_three_enterprise_solutions_from_one_replication_and_a_prototype():
    requirement={'text':'Delivery of at least 3 enterprise-scale Power Platform solutions.'}
    facts=[{'kind':'work','text':'Delivered a Power Automate approval workflow.'},
           {'kind':'work','text':'Recreated the same approval workflow for another site.'},
           {'kind':'work','text':'Built a prototype Power App.'}]
    assert apply_guards(requirement,'direct',facts,facts)[0]=='partial_transfer'


def test_transfer_verifier_is_isolated_from_retrieval_and_grades_the_facts(profile):
    calls=[]
    def invoke(system,data):
        calls.append(data)
        if 'requirements' in data:return {'matches':[dict(id='a',evidence_ids=['work:0:0'],reason='Relevant confirmed record')]}
        assert set(data['proposals'][0])=={'id','claim','facts'}
        return {'checks':[dict(id='a',status='direct',reason='Attempted upgrade')]}
    requirement={**row('a','unknown'),'text':'Coordinate stakeholder tasks'}
    result=assess([requirement],profile.model_copy(update={'is_example':False}),invoke)
    assert result['requirements'][0]['value'] in {1,.25}
    assert len(calls)==2


def test_duplicate_criteria_cannot_distort_denominator():
    with pytest.raises(AssessmentError):score([row('a','direct'),row('a','unknown')])


def test_general_project_record_cannot_receive_direct_credit_for_scheduling():
    req={'text':'Manage project handover documentation and scheduling.', 'logic':'all'}
    fact=dict(kind='work',role='IT Support',organisation='Example',dates='2021 - Present',text='Manage IT projects with stakeholder coordination, testing, change control and handover documentation.')
    grade,_=apply_guards(req,'direct',[fact],[fact])
    assert grade=='partial_transfer'


def test_explicit_specialist_years_are_accepted_without_inferring_from_role_dates():
    req={'text':'Minimum 5 years of experience administering SQL databases.'}
    fact=dict(kind='work',role='Database Administrator',organisation='Example',dates='2011 - Present',text='Administered SQL databases for 8 years.')
    grade,_=apply_guards(req,'unknown',[],[fact])
    # Retrieval must select the explicit statement before it can become a specialist match.
    assert grade=='unknown'
    grade,_=apply_guards(req,'direct',[fact],[fact])
    assert grade=='direct'


def test_reviewed_grade_keeps_quoted_evidence_and_attribution(profile):
    from campus_agent.transfer_fit import reviewed_fit
    requirement=row('a','unknown')
    decision={'id':'a','status':'strong_transfer','evidence_ids':['work:0:0'],'reason':'Closely comparable delivered work, with scope still to confirm.'}
    # A prototype record must remain preparation-level even in an explicit review.
    from campus_agent.semantic import facts_from_profile
    fact=facts_from_profile(profile)[0]
    from campus_agent.fit import custom_work_value
    if custom_work_value(fact['text']) != 1:
        decision['status']='foundation'
    result=reviewed_fit([requirement],profile,[decision],'assistant')
    assert result['reviewed_by']=='assistant'
    assert result['requirements'][0]['evidence'][0]['text']==fact['text']
    assert result['provisional'] and not result['auto_eligible']


def test_review_cannot_invent_evidence_or_omit_a_criterion(profile):
    from campus_agent.transfer_fit import reviewed_fit
    requirement=row('a','unknown')
    for decisions in [[],[{'id':'a','status':'direct','evidence_ids':['made-up'],'reason':'Claim'}]]:
        with pytest.raises(ValueError):reviewed_fit([requirement],profile,decisions)
