"""Frozen follow-up acceptance for false confidence and salary regression categories."""
import pytest
from test_dashboard_acceptance import candidate, role, fit
from campus_agent.listing_view import listing_view

DESC='Location: Melbourne VIC\nRequirements\n- Python workflow automation experience.\n- Power Automate workflow experience.\n- Microsoft 365 systems support experience.'

@pytest.mark.parametrize('bullets',[
 ["I don't have Python workflow automation experience.",'I have never created Power Automate approval workflows.','I do not have experience administering Microsoft 365 and Entra ID for IT onboarding.'],
 ['Will build Python workflow automation.','Will deliver Power Automate approval workflows.','Will administer Microsoft 365 and Entra ID.'],
 ['Expect to build Python workflow automation.','Hoping to deliver Power Automate approval workflows.','Would administer Microsoft 365 and Entra ID.'],
 ['Python workflow automation experience is unknown.','Power Automate workflow experience may be developed later.','Microsoft 365 administration remains to be verified.'],
 ['Python workflow automation experience.','Power Automate approval workflows.','Microsoft 365 and Entra ID administration.'],
])
def test_only_affirmed_delivery_can_earn_full_evidence_credit(bullets):
 p=candidate();p.experience[0].bullets=bullets
 value=fit(role(DESC),p)
 assert value['percent']<80 and not value['auto_eligible']
 assert not all(r['status']=='Supported' for r in value['requirements'])

@pytest.mark.parametrize('separator',[', ',' and ',' plus ','; ',' & '])
def test_unknown_obligations_survive_recognised_tool_matches(separator):
 text=DESC.replace('Python workflow automation experience.','Python workflow automation experience'+separator+'professional fluency in Japanese.').replace('Power Automate workflow experience.','Power Automate workflow experience'+separator+'hands-on SAP S/4HANA migration ownership.').replace('Microsoft 365 systems support experience.','Microsoft 365 systems support experience'+separator+'an active CISSP certification.')
 value=fit(role(text))
 assert not value['auto_eligible'] and value['percent']<80
 assert all(r['status']!='Supported' for r in value['requirements'])

@pytest.mark.parametrize('text',[
 'Salary: $120,000 - $140,000 per year + super + annual bonus.',
 'Salary: $120,000 - $140,000 per year + $2,000 training allowance.',
 'Salary: $120,000 - $140,000 per year plus a learning budget of $2,000.',
])
def test_base_salary_survives_benefit_wording(text):
 pay=listing_view(text)['salary']
 assert pay['status']=='stated' and pay['minimum']==120000 and pay['maximum']==140000
 assert pay['period']=='year' and pay['evidence']==text

@pytest.mark.parametrize('text',[
 'Salary: includes a $10,000 sign-on bonus; base salary negotiable.',
 'Salary: not disclosed. The budget for this project is $120,000 per year.',
 'Benefits\n$2,000 annual training allowance.',
])
def test_benefits_and_project_budgets_are_not_base_pay(text):
 assert listing_view(text)['salary']['status']=='not_stated'
