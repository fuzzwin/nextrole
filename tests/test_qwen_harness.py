from pathlib import Path
import pytest
from campus_agent import semantic
from campus_agent.qwen_harness import qualification_current, rules_hash, HARNESS_VERSION


def test_failed_or_changed_model_receipts_cannot_qualify(tmp_path):
    weights=tmp_path/'model.gguf';weights.write_bytes(b'GGUF-fixture')
    stat=weights.stat()
    receipt={'status':'passed','model':semantic.MODEL,'rules_hash':rules_hash(),'runtime':{'path':str(weights),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns}}
    assert qualification_current(receipt)
    assert not qualification_current({**receipt,'status':'failed'})
    assert not qualification_current({**receipt,'model':'other-model'})
    assert not qualification_current({**receipt,'rules_hash':'old-code'})
    weights.write_bytes(b'GGUF-changed-model')
    assert not qualification_current(receipt)


def test_alternatives_cannot_become_multiple_obligations():
    quote='At least 3 years of experience in IT support or systems administration.'
    view={'sections':[{'heading':'Requirements','blocks':[{'kind':'paragraph','text':quote}]}]}
    def bad(*_):return {'requirements':[{'source_id':'0','text':text,'importance':'essential','kind':'competency'} for text in ['3 years IT support','3 years systems administration']]}
    with pytest.raises(semantic.AssessmentError,match='alternative requirement'):semantic.extract(view,bad)


def test_harness_profile_is_valid_and_contains_negative_cases():
    from campus_agent.qwen_harness import synthetic_profile
    profile=synthetic_profile()
    assert not profile.is_example
    assert any('not hold CCNA' in fact for fact in profile.experience[0].bullets)
