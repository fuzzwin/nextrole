"""Paired evidence review. Neither arm writes a job rating."""
import argparse
import json
import re

from . import semantic
from .fit import custom_facts, task_supported
from .tenure import DURATION, general_support_duration


def quoted_requirements(row):
    """Build the shared matrix from the advert, independently of legacy ratings."""
    from .evidence_matrix import matrix_requirements
    return matrix_requirements(row['reading_view'])


def rules_review(requirements, profile):
    """Require direct task evidence or calculated general support tenure."""
    facts = [fact for fact in semantic.facts_from_profile(profile) if fact['kind'] == 'work']
    clauses = list(custom_facts(facts))
    rows = []
    for requirement in requirements:
        text = requirement['text']
        proof = general_support_duration(text, facts)
        if proof is None and not re.search(DURATION, text, re.I):
            match = next((fact for fact in clauses if task_supported(text, fact)), None)
            if match is not None:
                # Return the complete saved fact, including any surrounding qualifiers.
                proof = next(fact for fact in facts if fact['id'] == match['id'])
        rows.append({**requirement, 'status': 'supported' if proof else 'not_documented',
                     'evidence': [proof] if proof else []})
    return rows


def _arm(rows, model):
    result = semantic.render({'requirements': rows, 'model': model}, {})
    return {'percent': result['percent'], 'coverage': result['coverage'],
            'requirements': result['requirements'], 'coverage_range': result['coverage_range']}


def compare(job, profile, requirements, *, with_qwen=False, invoke=None):
    if not requirements:
        raise ValueError('No explicit, quoted requirements are available for this comparison.')
    from .evidence_matrix import summarise_matrix
    matrix = summarise_matrix(requirements)
    if matrix['needs_review']:
        raise ValueError('This advert mixes mandatory and preferred scope. Review the flagged matrix clauses before calculating a percentage.')
    assessed_requirements = [row for row in requirements if row['kind'] == 'competency' and row['importance'] != 'optional']
    if not assessed_requirements:
        raise ValueError('The matrix contains no scored duties or requirements.')
    if len(assessed_requirements) > 80:
        raise ValueError('This advert has too many requirements for one local comparison.')
    from .transfer_fit import score as score_transfer
    rule_rows = [{**row, 'status': 'direct' if row['status'] == 'supported' else 'unknown'}
                 for row in rules_review(assessed_requirements, profile)]
    result = {'rules': score_transfer(rule_rows),
              'qwen': None, 'qwen_error': None, 'matrix': matrix,
              'separate_requirements': [row for row in requirements if row not in assessed_requirements]}
    if with_qwen:
        if not semantic._LOCK.acquire(blocking=False):
            result['qwen_error'] = 'A local model check is already running. Try again after it finishes.'
            return result
        try:
            from .transfer_fit import assess as assess_transfer
            result['qwen'] = assess_transfer(assessed_requirements, profile, invoke or semantic.call_model)
        except semantic.AssessmentError as exc:
            result['qwen_error'] = str(exc)
        finally:
            semantic._LOCK.release()
    return result


# Human-labelled controls. Agreement alone cannot tell which method is right.
CONTROL_CASES = (
    ('Administer Microsoft 365, Exchange Online and Entra ID accounts and licensing', 'supported'),
    ('Minimum 2 years of experience in IT support.', 'supported'),
    ('Minimum 5 years of experience deploying production Copilot Studio agents.', 'not_documented'),
    ('Own and maintain RAID registers.', 'not_documented'),
    ('Hold current CCNA certification.', 'not_documented'),
    ('Deploy production Copilot Studio agents.', 'not_documented'),
)


def run_controls(*, with_qwen=False, invoke=None):
    from .models import Job
    from .qwen_harness import synthetic_profile

    rows = [dict(id=str(i), quote=claim, text=claim, importance='standard', kind='competency')
            for i, (claim, _) in enumerate(CONTROL_CASES)]
    job = Job(source_id='controls', title='IT Support', employer='Example Employer',
              url='https://example.invalid/job', location='Melbourne',
              description='Requirements\n' + '\n'.join(claim for claim, _ in CONTROL_CASES))
    result = {'rules': _arm(rules_review(rows, synthetic_profile()), 'Rules only'), 'qwen':None, 'qwen_error':None}
    if with_qwen:
        report = semantic.assess(job, synthetic_profile(), {}, invoke or semantic.call_model, fixed_requirements=rows)
        result['qwen'] = _arm(report['requirements'], report['model'])
    for arm in ('rules', 'qwen'):
        if result[arm] is None:
            continue
        decisions = result[arm].pop('requirements')
        by_id = {row['id']: row['evidence_state'] for row in decisions}
        checks = [{'claim': claim, 'expected': expected, 'actual': by_id[str(i)],
                   'passed': by_id[str(i)] == expected}
                  for i, (claim, expected) in enumerate(CONTROL_CASES)]
        result[arm]['checks'] = checks
        result[arm]['correct'] = sum(check['passed'] for check in checks)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--with-qwen', action='store_true', help='Also run the local model arm')
    args = parser.parse_args()
    result = run_controls(with_qwen=args.with_qwen)
    print(json.dumps(result, indent=2))
    arms = ['rules', 'qwen'] if args.with_qwen else ['rules']
    return int(any(result[arm] is None or result[arm]['correct'] != len(CONTROL_CASES)
                   for arm in arms))


if __name__ == '__main__':
    raise SystemExit(main())
