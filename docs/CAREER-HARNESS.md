# Career Opportunity Harness integration

Each saved role has separate research and interview preparation workflows. Results remain private in the local workspace, separate from applications and fit scores. Nothing in these workflows submits applications or sends emails.

## Source and validation limits

The generic validation and rendering contracts in `career_contract.py` and `career_render.py` are adapted from the user-supplied NextRole Career Opportunity Harness package. Private company examples, candidate files and replay fixtures are not distributed. The package tests and fictional replays are development checks, not verification of a real employer or candidate claim.

The supplied Proof Loop 0.3.0 CLI was used for development replays (upstream commit 18fe931cc4961a2476a676ac13e0390bcdc00da8, MIT); it is not bundled as an app runtime dependency. Structural validation remains distinct from factual review and external acceptance.

The app uses the existing connected search service and saved profile evidence. It does not silently provision a language-model API or incur model calls. Drafts and rehearsal feedback explain their extractive or rule-based limits. Exact connected-service tokens and billing are unavailable.

## Using it

Open a saved role, then choose **Deep Research** or **Interview Prep**. Before starting, select the research scope or interview stage, preparation time and answer frameworks. The disclosure explains the call/time cap and unavailable billing telemetry. Existing results can be reused; Refresh creates a new result. Cancelling stops further work and prevents late results replacing the cancelled state.

Research first searches for company pages, then reopens and checks their content. The guide uses short excerpts attributed to the publisher and groups unresolved details into questions for the employer. Employer research must cover business context and at least three topics across two company pages to unlock document exports. Research that falls short stays in preview. Interview Prep uses saved experience and can reuse recent employer research that passed the source checks.

Download a guide or quick sheet as editable DOCX or PDF. Mark only the specific output you have reviewed. Practice accepts your real answer, gives explicitly rule-based feedback, and offers retry or the next question. Updating a role, profile or options creates a different cached input; completed older outputs remain available in run history.
