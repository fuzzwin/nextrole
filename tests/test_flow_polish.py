"""String and structure anchors for the guided-flow polish of workspace.html."""
import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "campus_agent/workspace.html").read_text(encoding="utf-8")


def test_fit_review_comes_before_next_steps_and_steps_are_numbered():
    fit = HTML.index('<section class="detail-evidence"')
    prepare = HTML.index('<section class="detail-next-steps"')
    assert fit < prepare
    assert "Review your fit</p>" in HTML
    assert '<h3 id="detail-next-title">Prepare your application</h3>' in HTML
    assert 'id="detail-fit-hint"' in HTML
    assert "Review your fit first so documents use confirmed evidence." in HTML
    assert "$('detail-fit-hint').hidden=!!row.evidence_comparison?.reviewed" in HTML
    # hint only: the prepare buttons are never disabled by the fit state
    assert "prepare-full-job').disabled=!row.evidence_comparison" not in HTML


def test_scoring_explanations_are_collapsed():
    assert 'id="how-scoring"' in HTML and "<summary>How scoring works</summary>" in HTML
    assert "Fit uses direct and transferable experience." in HTML.split('id="how-scoring"')[1].split("</details>")[0]
    assert "$('how-scoring-extra')" in HTML
    assert "Direct work earns 100% credit" in HTML


def test_totals_lines_are_unambiguous():
    assert "Direct evidence found for" not in HTML
    assert "Automatic exact-wording check: " in HTML and "% of weighted criteria matched" in HTML
    assert "Fit % is the average over assessed criteria. Assessed is how much of the advert was graded." in HTML
    assert "provisional" in HTML


def test_search_summary_for_new_users():
    assert "No search set up yet. Add a role you have found, or set up a search." in HTML
    assert "!state.profile&&!state.jobs.length" in HTML


def test_secondary_stats_hidden_without_account_or_activity():
    assert "stat.hidden=!(on||Number($(id).textContent)>0)" in HTML
    assert "gmail?.connected||drive?.connected" in HTML


def test_profile_save_is_always_reachable_with_state():
    assert 'id="save-profile-bottom"' in HTML and 'class="profile-savebar"' in HTML
    assert re.search(r"\.profile-savebar\{position:sticky;bottom:0", HTML)
    assert "Unsaved changes" in HTML and "setProfileDirty" in HTML
    assert 'id="p-skills" rows="6"' in HTML
    assert "Add your full name before saving." in HTML


def test_add_role_dialog_guidance_and_location_default():
    assert "Paste the advert's web address. It identifies the role and lets you reopen it." in HTML
    assert "Paste the whole advert, including duties and requirements." in HTML
    assert "(state.profile?.location||'')" in HTML
    assert "state.preferences.location:'')" not in HTML
    assert 'id="edit-error"' in HTML and 'role="alert"' in HTML
    assert "Could not save this role: " in HTML


def test_touch_target_and_text_size_overrides_exist():
    assert "/* touch targets and minimum text size (flow polish) */" in HTML
    assert "min-height:28px!important" in HTML and "min-height:40px!important" in HTML
