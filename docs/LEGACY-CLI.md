# Job Seeker — connected workspace

The real workspace is launched with **Start-Agent.command** on macOS, or:

```bash
.venv/bin/python -m campus_agent workspace
```

Open http://127.0.0.1:8877. Keep the launcher window open.

This workspace uses your installed **Gmail**, **Google Drive**, and **Search Service**
connections through the supported Codex app-server JSON-RPC interface. Codex CLI
must be installed and signed into the same ChatGPT account. Check connections in
the app. No Google OAuth tokens or passwords are copied into this project.
The connector context is ephemeral and does not start a model turn.

You can:

- Discover Australian IT, automation and AI enablement role leads with editable
  phrases and location. Search results need a current listing check; known past
  closing dates are rejected when readable.
- Import résumé and cover-letter source files from Drive, read their original
  extracted text, choose a résumé, and edit confirmed profile facts.
- Read a full listing, paste a role manually, track notes and application stage,
  and prepare a résumé and cover letter using original supplied facts.
- Review local PDF previews, upload each PDF into a private **Job Agent** folder
  in Drive, create an unsent Gmail draft with both PDFs, or email the packet to
  your own connected Gmail inbox.
- Search only the configured job-alert query in Gmail, read returned messages,
  and save job links as leads for full-listing review.
- Optionally enable weekday discovery, 7 am–9 pm in your chosen timezone, while
  the app remains running. This daytime timer only saves leads; the separate morning routine below prepares and sends packets.

Packet tailoring ranks existing facts and uses a grounded cover-letter template.
It does not claim to perform unrestricted AI rewriting or infer new achievements.
Employer applications and job-board forms are not submitted by the app.

Every cloud action has a persistent idempotency record. An interrupted or
uncertain write becomes **needs review** and is not automatically retried.
Check the provider, then resolve the operation in Activity. Connector approval
requests appear in the app; the client does not silently accept them.

Drive saves use the packet's unsent Gmail draft as the managed file handoff:
the app reads a supported PDF attachment, passes the returned file reference
to Drive, and verifies the resulting Drive file metadata. The draft is created
once per packet and reused. Short-lived file download references stay in memory.

Your personal files, source text, account metadata, job database, packets and
operation history are under `workspace/`, which is Git-ignored and excluded from
release ZIPs. Existing résumé sources in Drive are read, not overwritten.
The original campus-board CLI/demo remains available below as a separate mode.

Implementation references: [Codex app server](https://learn.chatgpt.com/docs/app-server),
[plugins in Codex](https://learn.chatgpt.com/docs/plugins).


## Morning packets and extended search

The configured Codex schedule returns to this chat each morning and runs:

```bash
.venv/bin/python -m campus_agent morning --directory workspace
```

The weekly deeper run adds `--extended`. It uses the open workspace if available;
otherwise it runs directly without opening a browser. Keep the Mac awake, online,
and the Codex desktop app running. The schedule is managed in Codex Scheduled;
Search settings can pause delivery or change the packet cap (default three).

Daily discovery makes up to ten queries and reads up to twelve candidate listings.
Extended discovery makes up to twenty-four queries and reads up to thirty-two.
It adds adjacent role families, Australian cities, employer career sites, SEEK,
LinkedIn and Indeed, plus three recent matching Gmail alerts (six extended).
These are search budgets, not guaranteed numbers of jobs or exhaustive coverage.
Login barriers, unindexed vacancies and blocked listings can prevent verification.

Before delivery the routine refreshes the listing, requires Australian location,
an application invitation, a known employer and multiple confirmed skill/fact
matches. It skips known closed roles, uncertain clearance/credential requirements
and clearly mismatched seniority for manual review. It ranks original facts and
uses the existing grounded cover-letter template; it does not certify eligibility.
Up to the configured number of new packets are emailed to the authorized connected
Gmail account, followed by a daily search receipt (including no-match days).
Optional Drive copies use the same verified file handoff as manual saves.
No employer application is submitted. Each packet is for the user's review.

A local date ledger, process lock and delivery records prevent automatic repeat
sends. A failed or interrupted morning run is held for inspection, and uncertain
writes are never blindly retried. Previously emailed roles are skipped even when
found under another URL with the same employer and title. Search failures and
blocked candidates are included in the receipt and Activity.

---

# Campus Job Agent

Python 3.12+ implementation of the supplied screenshots: monitor campus boards, detect new roles, rank relevant resume facts, generate two PDFs, and deliver the packet to your inbox.

Includes a local dashboard, CLI worker, and MCP stdio server. It prepares application packets; it does not submit applications.

## Quick start

On macOS, double-click **setup/Start-Demo.command**. It uses Python 3.12 or later,
installs missing dependencies into `.venv`, creates the sample packets, and
opens the local dashboard. Keep its Terminal window open; press Ctrl+C to stop.
The first installation requires internet access. Later demo runs work offline.
The launcher uses `requirements-lock.txt` for the versions verified in this build.

Run from this folder with Python 3.12 or later:

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m campus_agent demo
.\.venv\Scripts\python.exe -m campus_agent --config demo/config.json serve
~~~

Open http://127.0.0.1:8876. The demo creates three **sample** application packets without contacting job boards, Gemini, SMTP, or SQLite Cloud. Repeat it to check duplicate suppression. The demo dashboard disables live scanning. In a normal configured workspace, **Scan sources** runs a live scan and prepares documents only.

On macOS/Linux, use .venv/bin/python. Start-Demo.ps1 installs and runs the demo on Windows.

## Your profile

Copy profile.example.json to profile.local.json. Replace every fictional fact, including contact details, education, employment, and availability. Set is_example to false.

Copy config.example.json to config.local.json and set its profile field to profile.local.json.

~~~powershell
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json scan
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json status
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json serve
~~~

PLAYWRIGHT_EXECUTABLE_PATH can select an existing Chromium installation. Otherwise Playwright uses its installed Chromium. The adapter uses an isolated temporary browser profile. It does not log in, fill application forms, or submit applications.

## Sources

Default URLs come from the official [ASI Work page](https://www.asicsulb.org/corporate/11-work) and [Beach Shops Work For Us page](https://www.csulb.edu/beach-shops/work-for-us), checked October 15, 2026. Rendering and selectors can change.

Adapters:
- adp: rendered ADP Current Openings components, actual job-detail URLs, and a listing-count completeness check.
- browser: Playwright, JobPosting JSON-LD, configured job links, bounded pagination, rendered job details.
- html: HTTP pages containing JSON-LD or configured links.
- json: an array, or an object with a jobs array, containing title, url, description, and optional employer and location.

The macOS build was checked on October 16, 2026 with Python 3.14.3 and
installed Google Chrome. Live discovery read 6 ASI and 11 Beach Shops roles,
including descriptions. All 19 tests passed with the Chrome integration
checks enabled. Desktop/mobile dashboard checks and six sample PDFs also
passed. See `evidence/macos-build-verification.json` and
`evidence/macos-live-sources.json` for this build; the original
`evidence/verification.json` describes the supplied ZIP's earlier environment.

To include real-browser regression checks on a Mac with Google Chrome:

~~~bash
PLAYWRIGHT_EXECUTABLE_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' .venv/bin/python -m pytest -q
~~~

Each source declares allowed_hosts. HTTP redirects and browser main-frame navigation are checked against that list. Essential page scripts may load from third-party asset hosts.

Set job_selector to the board's job-link selector when needed. title_selector optionally selects a child within a link; description_selector selects the detail body. empty_selector must identify a verified no-vacancies message. Without it, zero extracted jobs is an error, not a successful empty scan. The browser adapter saves a diagnostic screenshot when no job links match.

The generic pagination adapter recognizes buttons labeled “Next page”; other layouts need adapter adjustments. A source must produce complete usable results before it is initialized.

Default first_run is baseline: existing roles are recorded without flooding the inbox. Later new roles and changed descriptions queue a packet. Set first_run to notify to prepare existing roles on the initial scan. A per-scan preparation budget limits PDF generation, not discovery storage.

## Gemini

Local mode needs no key and is clearly labeled **local keyword ranking**.

For Gemini, set these shell variables and change ai_provider to gemini:

~~~powershell
$env:GEMINI_API_KEY = "<your key>"
$env:GEMINI_MODEL = "<model available to your account>"
~~~

Gemini receives the job description and supplied resume facts. It selects and reorders fact IDs and skill indices. The app validates references and renders the original facts. Cover letters use grounded, role-specific templates. This avoids inventing degrees, achievements, dates, and skills.

This differs from the screenshot's freeform resume rewriting. The original prompts were not supplied. The model is configurable because the screenshot's Gemini 2.0 Flash may no longer be available to a given account.

Keys remain in environment variables. .env.example documents names; .env files are not automatically loaded.

## Inbox delivery

Set SMTP variables, using your own inbox as MAIL_TO:

~~~powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "465"
$env:SMTP_USERNAME = "<your Gmail address>"
$env:SMTP_PASSWORD = "<Google app password>"
$env:MAIL_FROM = "<your Gmail address>"
$env:MAIL_TO = "<your receiving inbox>"
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json scan --send
~~~

Use a Google app password, not your normal account password. SMTP port 465 uses TLS; 587 uses STARTTLS. Plaintext SMTP is not supported.

Every packet contains Resume.pdf, Cover Letter.pdf, notification.eml with both attachments, notification.html for browser preview, and tailoring.json containing the method and matched skill phrases.

Ordinary scans, the dashboard, demo, and MCP tools never send email. Delivery requires scan --send or watch --send and a non-example profile.

## Scheduler

~~~powershell
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json watch --send
~~~

Defaults: every 10 minutes, Monday-Friday, 07:00 inclusive until 21:00 exclusive in America/Los_Angeles, following the reference email. Configure timezone, weekdays (Monday=0), hours, and interval_minutes for your situation.

Startup checks immediately if within the configured window. APScheduler coalesces missed ticks and prevents overlapping scheduled scans. Keep the worker and computer running. No OS background service or unattended automation was installed.

## State and recovery

Pydantic validates input. SQLModel defines local SQLite tables. Canonical source URLs identify jobs; title and normalized-description hashes identify revisions. Revisions queue an updated packet. Preparation failures retry on subsequent scans.

Run one worker per database/artifact directory. A file lock prevents local concurrent scans. After a crash, verify the PID in artifacts/.scan.lock has exited before removing a stale lock.

Delivery states: prepared -> sending -> sent. An ambiguous SMTP result becomes needs_review; interrupted workers may leave sending. Neither state is automatically resent, since SMTP cannot guarantee exactly-once delivery.

After checking your inbox:

~~~powershell
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json resolve-delivery JOB_ID --result sent
# Only if you confirmed it was not delivered:
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json resolve-delivery JOB_ID --result retry
~~~

Rebuild an unsent packet after profile edits:

~~~powershell
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json prepare JOB_ID
~~~

Fetch errors do not advance the initial baseline. A preparation budget leaves remaining jobs queued. External SDK exception text is not persisted, avoiding credential-bearing connection strings in logs.

## Optional SQLite Cloud

~~~powershell
.\.venv\Scripts\python.exe -m pip install -e ".[cloud]"
$env:SQLITECLOUD_URL = "<your connection string>"
~~~

Without this variable, the app uses the configured local SQLite file. The cloud adapter uses the SQLite Cloud SDK's DB-API interface, the same schema, and bound parameters. It needs an existing database and table-creation permission.

Cloud credentials were not supplied; that integration remains unverified. Cloud storage does not synchronize local PDFs. Run one worker per database; distributed coordination is not implemented.

## MCP

Tools: agent_status, list_jobs, scan_jobs, prepare_packet. There is no email-sending or application-submission tool.

~~~powershell
.\.venv\Scripts\python.exe -m campus_agent --config config.local.json mcp
~~~

Example client registration; replace every path:

~~~json
{
  "mcpServers": {
    "campus-jobs": {
      "command": "C:/path/to/campus-job-agent/.venv/Scripts/python.exe",
      "args": ["-m", "campus_agent", "--config", "C:/path/to/campus-job-agent/config.local.json", "mcp"],
      "cwd": "C:/path/to/campus-job-agent"
    }
  }
}
~~~

Adapt the outer configuration key for your MCP client. No global agent configuration was changed.

## Dashboard

Binds only to 127.0.0.1. Shows jobs, PDF/email previews, source health, queue state, and configured schedule. Manual scans prepare files only and require an origin and per-process token. The dashboard does not start the scheduler. Keep the local development server off public networks.

## REA provenance and limits

REA 6.4.0, distributed by [morluto/rea](https://github.com/morluto/rea), inspected a ZIP of the supplied screenshots. evidence/rea-artifact.json is actual REA output, with member hashes and Evidence IDs. evidence/reference-screenshots.zip retains the input.

**REA establishes artifact identity and inventory here. It does not recover program behavior or source from pixels.** Features were read from the screenshots; implementation details are new design choices. No original source repository, runnable program, HAR, database, or private backend was supplied. Exact source recovery and behavioral equivalence are not claimed.

evidence/reconstruction.json maps features to implementation and distinguishes unknowns. The original Jobright target was superseded by your screenshot request.

## Checks

~~~powershell
.\.venv\Scripts\python.exe -m pytest -q
~~~

Tests cover duplicates, baselining, revisions, queue limits, retries, SMTP ambiguity, attachments, grounded facts, daylight saving time, URL boundaries, dashboard security, and MCP registration. Actual build verification is recorded in evidence/verification.json.

## Runtime data

Profiles, PDFs, and email previews contain personal information. Keep data/ and artifacts/ private. Ignore rules exclude runtime state, credentials, and local profiles from Git. Demo facts and example.com links are fictional.


## Isolation and safe testing

A virtual environment isolates dependencies, not OS permissions. The ordinary Python process can access files and networks permitted to your user account. Playwright browser contexts isolate browser data; they are not a hardened system sandbox.

The demo explicitly blocks live scans and email, forces local tailoring, and ignores SQLITECLOUD_URL. No secrets or personal data are needed.

For a more restricted demo, run Run-Sandboxed-Demo.ps1 with Docker Desktop installed. Its image build downloads dependencies; the **running demo** has networking disabled, a read-only root filesystem, a non-root user, dropped Linux capabilities, no-new-privileges, and CPU/memory/process limits. Only a named output volume is writable. No home directory, Docker socket, or credentials are mounted. It copies sample output to container-demo afterwards and retains the stopped container and volume for inspection.

The container recipe has not been executed in this environment; see evidence/verification.json. Containers reduce risk but do not prove security against every possible vulnerability.

## Packet rules and references

Application PDFs use black text on A4, with bold headings and consistent spacing.
References are editable in Profile & sources: omit, available on request, or named.
Named referees require professional/contact details and an explicit sharing
confirmation. Missing details hold packet delivery; no contact details are guessed.
Choosing another source résumé preserves the separately entered referees.

The executable harness is `campus_agent/packet_checks.py`. Every connected packet
preparation writes `quality-report.json` beside its PDFs. Every Drive/Gmail write
runs the current checks again before contacting the provider. Rules include:

- The résumé's skills and experience must match the confirmed profile exactly;
  ranking may change, but qualifiers, employer names and dates must remain intact.
- Cover-letter prose must follow the grounded template and supplied evidence.
- The job identity and revision must match the actual packet; board metadata,
  unknown employers, markup and common placeholders hold preparation.
- The rendered résumé must contain the confirmed facts and candidate identity.
- Documents must use A4 and black text, with a one-page letter and at most three
  résumé pages. Named referees must appear intact when sharing is confirmed.
- The profile, style version and PDF hashes must still match at delivery time.
  Modified files or stale packets require regeneration.
- Automatic shortlisting separately screens location, application status,
  supported skills, specialist requirements and eligibility uncertainties.

These are deterministic checks, not a promise of perfect prose or complete job
eligibility assessment. PDF previews and human application review remain useful.

## Role-based job seeker

The home screen lets you choose IT support/systems, Power Platform/automation,
AI enablement/adoption, AI platform operations, business analysis/consulting,
business applications/ERP, IT project delivery and service delivery/implementation.
The delivery area includes IT service delivery, implementation specialists, release
coordination and service transition. It uses confirmed technology experience;
specialist years and other unconfirmed requirements remain held for review.
Save your choices and preferred
location once; the morning routine and manual searches use the same preferences.
Optional extra phrases can be enabled in Search settings. Daily discovery has a
ten-query / twelve-listing budget; extended discovery has twenty-four queries and
thirty-two listing reads. Candidate reads are shared across selected role families.

Filter saved jobs by role family, shortlist status or tracking stage. Match reasons
include transferable capabilities backed by exact facts from the confirmed résumé. Check & prepare
reads the original listing, applies the suitability rules and prepares PDFs only
when that check passes. Requirements that need confirmation appear under Needs
review; manual editing and PDF review remain available.

Role examples holds imported past applications with readable source text and real
Drive links. Importing an example does not merge historical claims into the
confirmed profile. Role families guide which original facts lead in the packet;
the applicable examples and chosen focus are recorded in its provenance. The
current fact, referee, PDF and own-inbox delivery checks still apply.

Scheduled email delivery now supports distinct morning and afternoon sessions,
with independent per-session ledgers and shared cross-session job deduplication.
The configured times are 08:00 and 16:00 Australia/Melbourne; Sunday mornings use
extended discovery. The separate hourly standout check can send one strong match
between digests, including overnight, and sends no empty receipt. A standout
requires at least three confirmed skill phrases, three transferable capability
matches, three supporting facts, score >= 50, preferred-city or Australian remote
work, and no detected eligibility, required-tool or seniority concerns. These
heuristics are review aids, not a complete eligibility assessment.

CLI: `morning --session morning|afternoon|standout --directory workspace`.
The main email checkbox pauses all sends; the standout checkbox independently
pauses priority alerts. The existing process lock and acknowledged/uncertain
send records apply to every session, so a job sent in an alert is skipped in
later digests. Local runs need the computer awake, online and the desktop app open.

## Applications from Gmail

Applications shows explicit employment receipts, interviews, assessments, offers
and outcomes with links to the source emails. Checks cover the last twelve months
of matching mail, up to 100 returned candidates and 30 new metadata reads per run;
remaining candidates are reported. Non-employment applications, recommendations
and the agent's own packets are filtered before full bodies are read. The scanner
stores only extracted employment events and brief evidence, not complete emails.
Ambiguous employer/role identities remain for review, and later outcomes take
precedence over older receipts regardless of the order messages are processed.

The settings checkbox enables a sync before every scheduled search. Twice-daily
receipts include the application snapshot. Confirmed company-and-role matches are
marked Applied and excluded from both digests and standout alerts, including
matching listings discovered later. No application is inferred from a prepared
packet, Drive file, job alert or draft. No replies, labels, mailbox changes or
employer submissions are performed by tracking.
