"""0.11.0 clearer job view: one primary action, plain status, pay and date wording."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "campus_agent/workspace.html").read_text(encoding="utf-8")
GROUP = HTML.split('class="actions detail-listing-actions"')[1].split('<section class="detail-quick"')[0]


def test_new_labels_present_and_old_labels_gone():
    for text in ("Review your fit ↓", "Open original listing ↗", "More actions", "Re-check advert",
                 "Look for other listings", "Edit details & notes", "Fit not reviewed yet",
                 "Not matched to your saved search", "Where this pay comes from",
                 "Probably per ", "Per year assumed — check the advert", "Pay period not stated"):
        assert text in HTML, text
    for text in ("Revalidate role", "Pay source and basis", "Fit review pending", "Outside your current search",
                 "Find another copy", "Review evidence ↓", "Pay period inferred"):
        assert text not in HTML, text
    assert "This role was added or saved outside the search terms you set." in HTML


def test_primary_action_comes_first_and_secondary_buttons_are_tucked_away():
    assert GROUP.index('id="jump-to-fit"') < GROUP.index('id="detail-link"') < GROUP.index('<summary>More actions</summary>')
    assert re.search(r'<button id="jump-to-fit" class="primary"', GROUP)
    more = GROUP.split('<details class="more-actions"')[1].split("</details>")[0]
    for ident in ("read-job", "research-job", "edit-job", "read-job-help"):
        assert f'id="{ident}"' in more
        assert f'id="{ident}"' not in GROUP.split('<details class="more-actions"')[0]
    assert "Re-check advert re-reads the saved listing for changes to its text, employer and closing date." in more
    assert HTML.count('id="read-job-help"') == 1


def test_touch_targets_and_bindings():
    assert "#jump-to-fit{min-height:44px" in HTML
    assert ".more-actions>summary{display:inline-flex;align-items:center;min-height:44px" in HTML
    for binding in ("$('read-job').onclick", "$('research-job').onclick", "$('edit-job').onclick", "$('jump-to-fit').onclick"):
        assert binding in HTML


def test_status_chip_is_a_button_that_jumps_to_fit():
    assert "chip.onclick=()=>$('jump-to-fit').click()" in HTML
    assert "'status-chip'" in HTML and ".status-chip .chip-icon" in HTML


def test_not_stated_facts_are_muted():
    assert "fact.value==='Not stated'?'not-stated'" in HTML
    assert "#detail-facts .not-stated{color:var(--muted)" in HTML


def test_pay_logic_still_flags_conflicts_and_period():
    assert "Conflicting figures. Check the original advert." in HTML
    assert "Pay period not stated" in HTML
    guide = (ROOT / "setup/START HERE.html").read_text(encoding="utf-8")
    assert "Where this pay comes from" in guide and "Pay source and basis" not in guide
