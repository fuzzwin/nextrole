## 0.9.5 — 30 October 2026 (assessment flow)

- Read up to 12 relevant new or filtered saved listings for evidence-based assessment and show source outcomes. Open role details from the card.

## 0.9.4 — 28 October 2026 (usability polish)

- Clarify match gaps, listing summaries, location and pay uncertainty; add previous/next role navigation.

## 0.9.3 — 28 October 2026 (live refresh performance)

- Reuse unchanged derived listing views and evidence assessments; invalidate them on source, profile, preferences, full-listing, closure or location changes.
- Keep manual pins, application status and packet/delivery checks fresh on every read.
- Coalesce overlapping browser refreshes so a large saved-job workspace does not queue repeated requests.

## 0.9.2 — 28 October 2026 (incomplete-match check)

- Unread, requirements-free or unidentified listings show Assessment pending and neutral component bars, with no numerical match or automatic promotion.
- Restore flattened Markdown headings/lists and keep job-board tags separate from employer-written requirements.
- Resolve explicit company headers on supported role pages and match employer-suffixed titles against JobPosting metadata without guessing company identity from a title.
- Reproduce the saved GBST screenshot case read-only; preserve the private profile and live workspace.

## 0.9.1 — 28 October 2026 (dashboard density)

- Job rows use roughly half the vertical space on desktop while retaining the same facts, badges, score, explanation and actions.
- Put pagination beside the result count and combine desktop filters into one row to show more jobs before scrolling.
- Keep readable wrapping and the existing stacked layout on narrower screens.

## 0.9.0 — 28 October 2026 (dashboard and evidence review)

- Multi-role browsing matches any selected family; selections persist across reloads and can be cleared individually.
- Denser job cards put the original listing link first, followed by salary, location, dates and evidence fit.
- A short popup summary precedes expandable scoring, source pay wording and full listing details.
- Full work credit requires affirmative delivery evidence; sparse listings, unknown obligations, prototypes and missing credentials hold automatic strong matches.
- Automatic strong matches default to 80%, with a 75% floor, full listing, identified employer, preferred location and no outstanding fit checks. Manual saved picks remain separate; this is not an applicant ranking.
- Employer JobPosting metadata must match the selected role. Pay retains period/currency and source quotes, flags conflicts, and separates base amounts from benefits.
- Existing private workspace, sample approval, delivery and application-submission boundaries remain in place.

## 0.8.4 — 24 October 2026 (candidate review)

- New Focused and Complete résumé content options with exact employment titles/dates preserved, source facts never rewritten, and selected/omitted examples explained in a private application review.
- Requirement-to-evidence review distinguishes matching saved evidence, unselected evidence and genuine gaps; keyword matches remain advisory.
- Optional professional headline, separately staged Selected technical projects and one-line interests, editable in Profile & sources and preserved on résumé re-import.
- Three-paragraph role-specific cover letters prioritise selected achievements plus supported user/stakeholder delivery.
- Expanded applicant review tips and Australian recruitment documentation; updated audit rules invalidate prior sample approval.
- No automatic mailing or employer application submission has been enabled.

## 0.8.3 — 24 October 2026 (candidate release)

- Choose brief introductions when job instructions request them; otherwise create grounded three-paragraph cover letters from existing confirmed facts.
- Add an evidence-stage/user review guide, prominent in-app application tips and synthetic regression tests.
- Check the requested application type during packet validation; invalidate old approved samples with document/rules version v5.
- Include the new user guide in the private-data-audited source distribution. This update does not enable sending, schedules or employer applications.

# Changes

## 0.8.2 — MIT licence

- Added the MIT licence to source, package metadata and the clean Mac download.
- Dependency licences and private or third-party content remain separate.

## 0.8.1 — Sharing artwork and privacy review

- Added a NextRole banner to the README and clean Mac ZIP.
- Binary artwork is pinned to its reviewed hash before release export.
- Rechecked source history and earlier release packages before public sharing.

## 0.8.0 — Preview, adjust and approve

- Added document style choices and side-by-side sample PDF previews.
- Both review confirmations and approval of the exact sample are required before any automatic email.
- Approval is bound to current profile, preferences, document rules and PDF hashes.
- Profile/style changes, a new sample or modified sample PDFs require renewed approval.
- Morning, afternoon, standout packets and digest receipts enforce the gate in the backend.
- Samples stay local, preserve résumé facts and do not replace existing job packets.
- Automatic email opt-in and existing paused schedules remain separate.

## 0.7.0 — NextRole

- Name and Mac launcher updated to NextRole; existing module IDs and launcher remain compatible.
- Light, dark and system modes with Violet, Ocean and Forest themes; optional extra contrast.
- Paginated job cards, combined role/location/date/match filters and saved browsing preferences.
- Experience and requirement evidence beside match scores; Auto top eligibility checks.
- Source-fact, stale-packet, referee and PDF checks before connected delivery.
- Guided setup from a clean ZIP plus the new user’s own résumé and connections.
- Clean source distribution excludes personal workspace, documents, credentials and schedules.

Known limits: macOS source release; Python 3.12+ required. Connected features depend
on Codex CLI/app-server and available account tools. Local scheduled jobs require an
awake, connected Mac. A match score measures evidence coverage, not hiring probability.
