# NextRole for Mac

## Prepare a full package (0.9.36)

Open a saved job and choose **Prepare full package** in **Next steps**. Before starting, select a ZIP with PDF and Word files, one combined PDF, or separate downloads. Choose **Email me after I review** to send the finished files to your connected Gmail account once you have reviewed them. You can download the output in either mode.

The run rereads the advert, checks evidence, opens employer sources and checks the evidence, prepares interview material, and tailors the résumé and cover letter. You can ask local Qwen for a fit suggestion. A current review is kept when the refreshed advert has the same scored criteria. Research with thin source coverage stays in preview until it can support the guide. The results show what to check next.

### Check more sources for one job

Open **Job research document**. Add official company pages if you have them. For a long page, add a short phrase copied from the public page after a vertical bar. If the saved advert is unreadable, paste another copy of the same job. A readable copy gives you role evidence while the employer’s current application status still needs confirmation.

## Current scoring: transferable fit (0.9.31)

The provisional fit percentage uses direct work (100%), strong transferable work (75%), partial transfer (50%), relevant foundation (25%) and explicit confirmed gaps (0%). Unknown evidence stays outside the fit average. Essential criteria count twice standard criteria. Optional criteria and eligibility/logistics checks remain separate.

The separate **Criteria assessed** percentage shows how much of the extracted advert has an assessment, including partial skills and foundation. It does not mean those criteria are fully met. For example, 100% fit with 10% assessed is too incomplete to use as a whole-job rating.

Use **Assess fit** on a job card to open the criteria and check direct evidence. **Suggest grades with local Qwen** is optional. Review each criterion, choose confirmed evidence, explain the transfer and any gaps, then **Save reviewed fit**. The app labels assistant reviews separately from user reviews. Saved reviews remain provisional and current until the advert, profile or scoring logic changes.

Compounds retain their source qualifiers and AND/OR scope. Exact repeated criteria are removed; near-duplicate concepts and omitted requirements still need source review. Older scoring descriptions below describe historical versions, not this current calculation.

## Start here — give Codex the ZIP and your resume

**Recommended setup: open a local Codex chat, attach the NextRole ZIP and
your current resume, then paste the setup message below.** Codex can unpack
the project, check requirements, help with your own connections and launch it.
You do not need to unzip it or install Python packages yourself first.

No coding knowledge is needed. Set aside a little time for downloads and your
own account sign-ins. You will use **Codex** for setup help and your **browser**
for NextRole. A **Terminal** window may appear to keep the site running.
Keep that window open when the site is in use.

If you already unzipped the download to read this guide, that is fine: attach
the original ZIP if you still have it, or use the manual-folder fallback below.
This is assisted installation on your Mac; merely attaching files does not
start the site until you send the prompt and Codex completes the setup.

## Step 1 — open a local Codex chat

1. Open Codex on your Mac. If needed, follow the
   [official desktop setup guide](https://learn.chatgpt.com/docs/quickstart)
   to install the Mac desktop app and sign into **your own ChatGPT account**.
2. If there is a ChatGPT/Codex selector, choose **Codex**. Start a new chat
   working **locally on this Mac** so it can unpack files and start the site.
3. If the app asks where to work, choose or create an empty local setup folder
   you are happy for Codex to use. The prompt asks Codex to confirm the final
   NextRole location. You do not need GitHub or a cloud environment.

Checkpoint: you can see the Codex message box and add files. Exact controls
vary by app version. Keep your available/default Codex model for setup.
A web-only chat without local file/command access cannot launch this Mac app.

## Step 2 — attach the NextRole ZIP

1. Open **Finder** (the blue smiling face in the Dock), then **Downloads**.
2. Find **NextRole Mac ZIP**, the download you received.
3. Drag the ZIP into the Codex message box. Alternatively, use the chat's
   attachment control and select the ZIP in Downloads.
4. Wait until the attachment appears beside the message. Leave it attached;
   you can add your resume before sending.

Checkpoint: the chat shows the NextRole ZIP as an attachment. If your app
cannot attach ZIPs, or the original ZIP is gone, use the **manual-folder
fallback** further down. Codex will check file access before trying to unpack.
It should keep any existing installation and personal workspace intact.

## Step 3 — attach your current resume, or choose Drive

1. Find your latest **resume PDF or Word (.docx) file** in Finder. Drag it
   into the **same Codex message**, or add it with the attachment control.
2. Optional: attach a cover-letter example you like. If you include several
   resume versions, tell Codex which one is current so it does not silently
   combine old details with new ones.
3. Prefer Drive? You can skip the resume attachment and tell Codex the exact
   file name in your own Google Drive. It should check the connection, help
   find candidates and ask you to confirm the correct source before importing.
4. Only attach files you want to share with this Codex chat. Do not include
   passwords or verification codes. Your resume belongs in your own setup
   chat, **not inside the clean ZIP you send to other people**.

Checkpoint: the message has the ZIP plus your resume attachment, or your
instructions for finding it in Drive. You can enter facts manually later if
no document is available. Codex must show you the extracted profile for
confirmation; uploading a file alone does not make every statement current.

## Step 4 — copy this message, paste and send

Click **Copy setup prompt** below. Click the Codex message box with your
attachments, press **Command+V**, then send the message. You can also click
inside the prompt box, press **Command+A** then **Command+C** to copy it.
The same message is in **setup/CODEX SETUP PROMPT.txt** inside the extracted package.

```setup-prompt
Set up this NextRole ZIP on my Mac. I am not technical: use plain English, explain what I should see, and guide me through anything that needs my input.

Locate the ZIP I attached, confirm a suitable local project folder with me, and unpack it there. Do not overwrite an existing installation or personal workspace. If the folder is already extracted, reuse the correct folder containing launcher.py and Start NextRole.command. If you cannot access the attachment or write to the intended folder, help me choose a permitted local location. Read setup/START HERE.txt, docs/USER-GUIDE.md and the launcher instructions before making changes.

Check Python 3.12 or later, the project dependencies and Codex CLI. Help install missing requirements from official sources, keep Python packages in the project's .venv, and launch with the supplied launcher. Do not create API keys or ask me to paste passwords or tokens into chat.

Check whether my existing Gmail, Google Drive and search connections are available in this local Codex setup. Reuse authorized connections where available; guide me through connecting anything missing. I will complete sign-in and consent screens myself. Confirm my accounts and explain unavailable tools rather than promising they will work.

Use my attached current resume to draft my profile. If I named a Drive file instead, help find it and confirm the correct document with me before importing it. If versions conflict, ask which is current. Treat cover-letter examples as style references, not proof of additional experience. Show me extracted contact details, employment dates, skills, qualifications and factual bullets for review before saving my confirmed profile. Preserve prototype, proposal, deployment and unmeasured-outcome qualifiers. Do not use the sample profile as my information or invent missing details.

Help me choose role types and location, run one manual search, then open Document style so I can choose a layout, tone and length. Generate a local sample for a fully read role and show me both PDFs. I will review both documents and click their review boxes and Approve myself; do not approve on my behalf. Keep automatic sending, extra daytime discovery, standout alerts and application-email tracking off during setup. Do not create schedules, email packets, upload generated PDFs or submit employer applications. Let me review my profile and sample packet first.

Finish by telling me the exact folder and launcher to open tomorrow, which windows to keep open, and how to stop the app. Reuse this chat for future help; I should not need a new chat every day.
```

Checkpoint: Codex confirms where it will unpack the project, then checks
requirements and connections. Complete provider sign-ins yourself. It should
show a draft of your own profile for review before saving it. Check dates,
current contact details and qualifiers carefully, especially with older files.
If stuck, tell the **same chat**: **“Please explain the next click more slowly.”**

## Step 5 — let Codex check the requirements

Codex can check these for you. You do not need to install every item by hand first.

1. **Python 3.12 or later** runs the app. If missing, use the Mac installer from
   [python.org](https://www.python.org/downloads/macos/). Open the downloaded
   installer and follow its instructions. Ask Codex if you are unsure which one
   to choose for your Mac.
2. **Codex CLI** is the command-line component the site uses for connected
   tools. Having the desktop app does not always mean this component is
   installed. Ask the setup chat to check it and guide installation using the
   [official Codex CLI instructions](https://learn.chatgpt.com/docs/codex/cli).
3. **Your own connections** supply Gmail, Google Drive and search. In Codex,
   use its [plugins/connections settings](https://learn.chatgpt.com/docs/plugins)
   and complete the sign-in prompts. Then use **Gmail & Drive → Check connections**
   in NextRole to confirm the displayed accounts are yours.

If Gmail or Drive are already connected in ChatGPT, ask Codex to check whether
those authorized tools are available here before connecting anything again.

Checkpoint: the setup chat tells you what is ready and what is unavailable.
Accounts and managed workspaces can expose different tools. If a required tool
is not offered, Codex should explain the limit; a ChatGPT login alone does not
guarantee connected search/Google access. You can still enter a profile, paste
job details and prepare local PDFs while sorting out connections.

The Python packages install automatically into a private folder called **.venv**
inside NextRole. You do not need to open that hidden folder or understand its
contents. First install needs internet and can take several minutes. Wait for
it to finish. No API key, Google app password or Docker is needed for the
connected workflow. Follow prerequisites of the official Codex installer if asked.

## Step 6 — open the site and try one job

Codex can launch it for you. To launch it yourself:

1. In Finder, open the **NextRole folder Codex confirmed during setup**.
2. Double-click **Start NextRole.command**. A Terminal window opens and shows
   progress. Leave it open; do not keep clicking the launcher while it installs.
3. Wait for your browser to open **http://127.0.0.1:8877/**. If Terminal says the
   app is ready but the browser has not opened, copy that address into the browser.

Checkpoint: the browser shows **NextRole** with an empty list and your profile
still to set up. The address points to an app running on your Mac. It will not
open on another person's computer unless they start their own copy.

Next, work through these buttons in the site, with Codex's help if needed:

1. **Gmail & Drive → Check connections**: confirm your accounts. This check
   does not send mail or upload files.
2. **Profile & sources**: review the profile Codex drafted from your attached
   resume or chosen Drive source. Confirm contact details, employment dates,
   skills, qualifications and factual bullets before saving. If it is still
   blank, ask the same chat to help, or enter facts yourself and **Save profile**.
   Drive imports are also available here. Correct extraction errors manually.
3. **References**: choose omit, available on request or named referees. Only
   enter contact details you have permission to share and confirm sharing.
4. **Optional headline, projects and interests**: a professional headline does not change your formal employment titles; keep personal technical projects in their own section with honest stages and interests to one line. The job packet explains which items were selected and what was left out.
5. **Opportunities**: open **Change search roles & preferred location**, choose
   the role types you want, change Melbourne if needed, then **Save my search**.
6. Click **Find jobs**, then open **View details** and **Why this match** for
   one role. Check its employer, location, requirements and review flags.
7. Click **Check & prepare** for a suitable role. Open and read both PDFs.
   Ask Codex about anything that looks wrong before using email or Drive actions.

Checkpoint: your profile is accurate and you have reviewed a sample resume and
cover letter. Missing referee details, a long profile or an unverified listing
can hold packet preparation/delivery; inspect the displayed reason. Keep
prototypes, proposals and unmeasured outcomes explicitly qualified. You apply
through the actual employer/board yourself; the app does not submit applications.

Automatic email and tracking stay off until you deliberately enable them.
You have finished the first setup. The remaining sections explain daily use
and optional features; you do not have to configure schedules now.

## Step 7 — tomorrow, just double-click

1. Turn on your Mac and connect to the internet. Open Codex when you want
   connected features or scheduled assistant runs available.
2. Open **Finder → the NextRole folder Codex confirmed during setup**.
3. Double-click **Start NextRole.command** and wait for the site to open.
4. Keep its Terminal window open. Your saved profile and jobs are in this same
   folder, so you can continue where you left off.

You **do not need to start a new chat** each day. Return to your existing Job
Seeker setup chat when you want help, changes or optional schedules.
To stop the site, click its Terminal window and press **Control+C** (hold the
Control key and press C). Closing a browser tab alone does not stop the server.
If Codex started the site in its own terminal, ask that same chat to stop it.

The Mac must be awake and online for local scheduled searches. They cannot run
while it is shut down. The launcher creates no login item, background service or
schedule. If it opens an existing instance, that site must belong to this folder.
Different extracted folders have separate workspaces; keep using your original one.

## Browse saved jobs without a long scroll

The job list starts with **10 roles per page**. Use **Next**, **Previous**, or
page numbers above or below the cards. **Roles per page** offers 10, 20 or 50.
The result count tells you which roles you are viewing. Changing a filter starts
at page 1; your view is remembered in this browser when you return.

Use **Search saved roles**, **Role type** and **Location / remote** together.
**More filters** adds a minimum match score, date posted, full listings versus
leads, and a checkbox to hide closed roles. Date filters exclude unknown posting
dates. Click the × on a filter chip to remove just that filter, or **Clear filters**
to return to all unarchived roles. **Sort by** controls match, dates or top listings.
These are browsing filters; they do not change your scheduled search preferences.

Open **Change search roles & preferred location** when you want to change the
saved role types/location used by discovery. The large preferences panel stays
collapsed for returning users so the results are closer to the top.

## Choose a comfortable appearance

Click **Appearance** at the top right of the site. Choose **Dark**, **Light**,
or **Follow my Mac / system**, then choose **Violet**, **Ocean** or **Forest**.
Turn on **Extra contrast** for stronger borders and clearer secondary text.
Changes appear immediately; click **Done** to return to your jobs.

Your choice is saved automatically in this browser and survives closing the
site. **Reset appearance** restores system mode, Violet and standard contrast.
Appearance changes affect the site; résumé and cover-letter PDFs keep their
black-text document rules. Search schedules and filters stay as they were.

## Preview, adjust and approve before automatic emails

1. Save your own confirmed facts in **Profile & sources**. Check dates, contact
   details, qualifiers and optional referees before continuing.
2. Open **Document style** in the left menu. Choose Classic, Compact or
   Comfortable spacing; a maximum of 2 or 3 résumé pages; Professional, Warm or
   Direct letter tone; Standard or Brief letter detail; and relevant or original
   fact order. PDFs remain black text on A4. Focused résumé mode selects the strongest relevant evidence from your original profile and reports what was omitted; Complete mode keeps all saved employment bullets.
3. Choose **Focused** for relevant achievements or **Complete** for the full employment evidence. The job packet displays the selected bullets, omitted examples and evidence gaps. Choose a saved role with a fully read listing and confirmed employer, then
   click **Generate sample résumé & cover letter**. This saves the choices and
   makes a local sample. It sends nothing and does not replace an existing packet.
4. Open both PDF links or scroll through their rendered page previews. Check the facts, tone, page breaks,
   readability, length and contact details. If you want a change, adjust the
   choices or your confirmed profile, then generate another sample.
5. When you are happy, tick **both review boxes** and click **Approve this sample
   for automatic emails** yourself. Approval is saved for these exact PDF files,
   your current profile, your style choices and the current document rules.
6. Only then review **Search settings** and opt in to automatic emails if wanted.
   Approval does not enable emails, create schedules or resume a paused schedule.

Automatic morning, afternoon and standout sends, including digest receipts,
are blocked without current approval. Existing installations are also required
 to approve a sample; earlier email opt-in does not count as style approval.
Profile/style changes, a new sample, changed/missing sample PDFs or updated
rules hold automatic delivery until the sample is approved again. Old job
packets must be regenerated if they use an earlier style or ruleset.

A page limit is a readability check, not permission to rewrite history. In **Focused** mode, the app selects relevant original bullets and visibly reports omitted facts while retaining formal job entries, titles and dates. In **Complete** mode, all saved professional bullets remain. If the PDF exceeds your page limit, review the omissions, adjust your selected scope or page count and regenerate; the master evidence is not deleted.
You can still turn email delivery off while approval is pending.

## Role-tailored application writing and tips

NextRole now distinguishes a job advertisement requesting a **brief introduction** from a standard cover letter. Both are produced as a compatible one-page PDF called **Cover Letter.pdf**, with the correct heading shown inside. Check the actual employer's application instructions before attaching the file or putting the introduction in your email body. The writer uses only saved candidate facts and preserves qualifiers; it does **not** invent outcomes or prove the facts itself. Review the three body paragraphs for voice, relevance and true role fit. Selection criteria and required portfolio examples still need separate review and preparation.

Read [Role-tailoring and evidence guide](ROLE-TAILORING.md) for end-user guidance about relevance, metrics, personal projects, referee consent and the proof loop. Every change to document rules makes old sample approval stale; approve a **new** sample after this release.

## See the document guardrails

Inside a role, open **Résumé & cover-letter guardrails**. The panel shows the
packet's recorded check status and any issues holding delivery. It checks your
saved facts/qualifiers, role/employer, grounded letter wording, named-referee
sharing, A4/black text, page limits, and stale or modified packets. Checks run
again before Gmail/Drive delivery. Manual sends also require the PDF review box;
scheduled delivery is a separate opt-in.

**Checks passed** means the document checks passed, not that the job is suitable
or every claim is independently verified. Match review flags are separate.
Keep your confirmed profile accurate and read both PDFs before using them.

## Manual-folder fallback — only if attachments do not work

You can use the same setup prompt with an already-extracted folder.

1. In **Finder → Downloads**, double-click the NextRole ZIP once to unzip it.
2. Drag the whole **NextRole Mac** folder into **Documents**.
3. Open it and check that **launcher.py** and **Start NextRole.command** are
   inside. Keep all files together; do not move only the launcher to the Desktop.
4. In Codex, use its project/folder chooser to open **that extracted folder**,
   then start a local chat there. Choose the folder, not Documents or the ZIP.
5. Attach your current resume, or give the name of the Drive source you want.
6. Paste the setup prompt above. Add: **“The project is already extracted in
   this selected folder. Use it instead of unpacking a ZIP.”**

Checkpoint: Codex can read the launcher in the selected folder and knows which
resume is yours. Continue with its requirements check. No terminal commands
need to be typed by you for this fallback; ask the chat if you need help.

## If you are stuck — paste this into the same chat

> I am setting up NextRole and I am stuck. Please check which folder I am
> using, explain what should be on screen now, and give me the next click in
> plain English. Keep my saved profile and jobs. Do not reset send records,
> send mail, upload files or create schedules while troubleshooting.

If an error appears, tell Codex the exact message. Do not delete the workspace,
reinstall repeatedly or turn off Mac security to guess at a fix. The
Troubleshooting table further down has specific next steps.

## How GPT / Codex work

The browser is the interface; a Python server runs locally and stores your jobs.
Codex CLI's app-server supplies connected tools: Search Service finds/reads public
listings; Gmail reads matching alerts and optional application evidence; Drive
reads chosen source documents and can save prepared PDFs.

The connected workspace calls tools directly through an ephemeral connector
context. It **does not start a model turn or make an LLM inference request**.
Matching uses local rules. Tailoring reorders your confirmed facts, preserves
qualifiers, and uses a grounded cover-letter template. ReportLab creates A4 PDFs
with black text. There is no GPT model selector or required API key in this mode.
Search Service's internal processing is supplied by the provider.

A separate Codex chat can operate the app or schedule the command. That chat
uses the model selected in Codex, with its own usage/account limits. Local code
does not mean external services are free or unlimited. The legacy campus CLI
has optional Gemini/SMTP integrations; those are a separate mode, not normal setup.

Match scoring weights skills 30%, work experience 40%, and stated requirements
30%. Reasons cite saved evidence and flag unconfirmed essentials, specialist
tenure, credentials, eligibility and seniority. Scores estimate supported overlap,
not hiring probability or proof that every requirement was parsed correctly.

Auto top defaults to 80% and also requires a complete listing, **Good match**,
no review gaps, and a role that is not applied, archived or closed. Change the
threshold in Search settings. Manual stars remain separate. Auto top alone
does not authorize email delivery.

Normal searches budget up to 10 public queries / 12 listing reads; extended
searches up to 24 queries / 32 reads, plus matching Gmail alerts when available.
Results may be duplicates, old or blocked. The app does not bypass sign-ins or
guarantee complete market coverage. Inspect the actual listing before applying.

## Optional schedules

New users start with automatic daytime discovery, scheduled email, standout
alerts and application tracking **off**. Auto top is on because it only changes
your local list. The switches authorize/pause features; they **do not install
Codex schedules**. The original owner's schedules are not included.

After reviewing one packet, enable scheduled email in Search settings. Save to
bind delivery to your connected Gmail inbox; choose packet cap (default 3),
timezone and optional Drive copies. With this folder selected in Codex, ask:

> Set up NextRole in this folder for 8 am and 4 pm in my saved timezone.
> Inspect the CLI and saved preferences first. Use morning and afternoon
> sessions; add extended search on Sunday morning. Reuse matching schedules
> rather than creating duplicates. Keep extra daytime discovery off. Check
> the delivery toggle before each run. Send only to my connected Gmail account,
> preserve process locks and shared send records, and report only meaningful
> failures in chat. Never submit applications. Preserve all factual qualifiers.
> Tell me which schedules you created.

Only if you want exceptional alerts, also ask:

> Add one hourly standout check for this folder, using the standout session,
> only when both delivery and standout switches are enabled. Email at most one
> qualifying exceptional match; no empty receipts. Reuse existing schedules
> and shared delivery records. Never submit employer applications.

The underlying commands, from this folder:

```bash
.venv/bin/python -m campus_agent morning --directory workspace --session morning
.venv/bin/python -m campus_agent morning --directory workspace --session afternoon
# Sunday morning: append --extended to the morning command.
# Optional exceptional check:
.venv/bin/python -m campus_agent morning --directory workspace --session standout
```

The command reuses the open site or runs directly. Keep your Mac awake, online
and the scheduler/Codex available. It cannot run while shut down. Do not assume
missed sends replay on startup. Manual **Find jobs**, **Extended search** and
**Run morning check now** remain available. Hosting is not included in this release.

Application tracking is separately opt-in: enable it to read matching employment
confirmation/interview/outcome emails. It records explicit evidence with source
links and skips applied roles in automatic packets. Job alerts, drafts and packet
emails are not evidence you applied. It does not reply or alter Gmail labels.

## Dependencies

`requirements-lock.txt` pins Python packages. The launcher checks all versions
and installs missing/mismatched packages in `.venv`, without administrator
privileges or changes to system Python packages.

| Component | Purpose | Setup |
| --- | --- | --- |
| Python 3.12+ | Runs app/installer | Install once from python.org |
| Codex CLI and connections | Search, Gmail, Drive tools | Install/sign in with your own account |
| FastAPI / Uvicorn | Local server | Automatic |
| Pydantic / SQLModel / SQLAlchemy | Validated data / SQLite | Automatic |
| ReportLab / pypdf | Creates/checks PDFs | Automatic |
| httpx / BeautifulSoup | HTTP/content handling | Automatic |
| tzdata / tzlocal / APScheduler | Timezones / legacy timers | Automatic |
| Playwright / MCP / Google GenAI | Shared legacy adapters/tooling | Automatic Python packages |
| Safari/Chrome/other browser | Displays site | Use an installed browser |

The main connected workflow does not need a Playwright browser download.
Legacy browser scanning does (see LEGACY-CLI.md). No API key is requested by
the installer. Arial from macOS is used when available, with a built-in fallback;
system fonts are not redistributed.

Internet is needed for PyPI/build dependency downloads, Codex and selected
providers/listings. Package/build dependencies execute during installation;
use a release from a source you trust.

## Data, sharing and updates

The release starts blank. Launching creates `workspace/` containing your profile,
source-document text, saved jobs, application evidence, PDFs and operation history.
Keep it private. The site binds only to localhost, but other processes running
under your account can still access your files. It is not a hardened multi-user
or public internet server.

Credentials remain managed by Codex/providers outside this project; the app
does not copy tokens into its workspace. Selected data is passed to providers
when actions need it: Gmail drafts/emails carry the PDFs. Optional Drive saves
may create an unsent Gmail draft as the PDF handoff, then verify Drive copies.
Imported Drive source files are read, not overwritten.

Back up by stopping the app and scheduled activity, then copying the entire
folder including `workspace/` to private storage. Never copy a live SQLite
database in isolation. To update/move Macs, unzip a fresh release, copy your
private `workspace/` into it, reconnect accounts and update schedule paths.
Keep a backup; recreate `.venv` with the launcher instead of copying it between
machines. Never reset send ledgers: they prevent duplicate/uncertain emails.

Share only the original clean ZIP, never your used folder or private backup.
The builder excludes workspace, PDFs, credentials, evidence, caches and schedules.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| macOS blocks the launcher | Verify the source. Use System Settings → Privacy & Security → Open Anyway if offered, then confirm. Do not disable Gatekeeper globally. |
| Launcher not executable | In Terminal type `chmod +x ` (trailing space), drag Start NextRole.command in, press Return, then double-click again. |
| Python missing or old | Install Python 3.12+; close the old Terminal and relaunch. |
| Python certificate errors | Run Install Certificates.command supplied with your python.org install; do not disable TLS verification. |
| Dependency install fails | Check internet/proxy access and the first pip error. Keep the error text; relaunch can resume dependency installation. Do not delete workspace. |
| Codex not found | Install CLI via official instructions. It must be on PATH or in ~/.local/bin, /opt/homebrew/bin or /usr/local/bin. Relaunch. |
| Gmail/Drive/search unavailable | Check your sign-in, account/admin access and plugin permissions in Codex, then Check connections. Do not paste credentials into the project. |
| App-server method/argument error after updating Codex | Experimental methods can change. Record the error and CLI version; a compatibility fix may be required. Do not repeatedly retry an uncertain send. |
| Port 8877 busy | Close the other copy. For manual local use, `python3 launcher.py --port 8878` uses another port. Scheduled commands must use the same `--port`. |
| Blocked listing or Needs review | Check full listing access/filters; try pasted text or extended search. Blocked pages do not prove no jobs exist. |
| Résumé import fails | Enter/correct the profile manually; extraction supports a limited layout. |
| Packet check fails | Correct the listed issue or shorten the profile, regenerate and review again. Profile/referee edits make old packets stale. |
| Interrupted / needs_review write | Check Gmail/Drive and Activity before resolving. Never blindly resend or reset records. |
| No scheduled email | Confirm your own schedule exists, delivery is enabled, the path/timezone are correct and the Mac is awake/online. Check Activity. |
| Empty workspace after relaunch | Use the same folder. Different extracted copies have separate data. |

Local-only diagnostic (no installation, sign-in, searches, mail or schedules):

```bash
python3 launcher.py --check
```

It checks Python/dependency/CLI presence, not private account access.


## Evidence fit and compact browsing (0.9.7)

Use **Role types** to tick several families. A role matches any selected family;
location, minimum fit, date and status filters still combine with that selection.
Remove individual chips or use **Clear filters**. These browsing choices do not
change the role families used by discovery.

The role title opens the original advert. **View details** opens the short summary,
location, listed pay and the main evidence check. Expand **Fit and evidence details**
for supported/partial/unconfirmed counts and exact saved facts. Weighted points are
available in each component's explanation; a full bar describes the recognised
criteria, not independent proof of every possible skill or hiring probability.

A short advert cannot establish a 100% strong match. Automatic strong matches need
at least three distinct stated requirements, two supporting work examples, a full
listing, identified employer, preferred location and no outstanding fit checks.
The default threshold is 80%; older lower settings use a minimum of 75%.
Unknown or compound obligations stay for manual review. Skills-only, prototype,
future and uncertain work evidence does not establish delivered experience.
These conservative local rules may hold a suitable role for review; confirm the
actual advert and your source profile. **Your saved pick** is a separate manual pin.

Listed pay preserves its period and currency where stated. Open **Pay source and
basis** for the exact captured wording. A likely annual basis is labelled inferred;
hourly/day rates are not silently annualised. Conflicting figures need checking
against the original advert. Blocked pages still require pasted employer text.


Unread leads, listings with no assessable requirements and unconfirmed employer identities show **Assessment pending**. Their bars stay neutral; missing information does not become zero fit or a fixed49% score. Read or paste the full employer advert and confirm identity to assess. Job-board keyword tags alone are not mandatory requirements.

## Usability improvements (0.9.7)

Use Previous and Next in a role to move through the current filtered and sorted results. A pending assessment tells you what listing information to check. Pay is shown as captured; an inferred annual basis or conflicting figures need verification.

## Reading and assessing roles (0.9.7)

Find jobs reads up to 12 relevant new listings. Use Read & assess filtered roles to process up to 12 eligible saved roles at a time. Blocked sources remain visible: open the listing and paste the original advert in Edit role, or retry that role explicitly. These actions do not prepare or send applications.

## Salary source checks (0.9.7)

Company funding and valuation figures are excluded from pay. Confirm any listed salary and its basis against the original advert.

## Source recovery (0.9.7)

Role assessment uses confirmed source text. When a source is unavailable or a role cannot be identified, its assessment remains pending for review.

## Dashboard layout (0.9.8)

Your opportunities puts saved roles first. Find jobs and Add a role stay beside the heading. The slim summary shows saved roles, prepared packets, Drive files and confirmed emails. Auto-email paused still means your sample documents need review before automatic email can run.

Open **Search setup** for search roles, preferred location and Extended search. Open **List actions** beside the result count for Read & assess filtered roles, its progress and Clear filters. Filters and page controls stay next to the list. Job rows keep their original link, employer, fit gauge, location, pay, dates, review reason and actions; click the row or press Enter to open it. Completed notifications clear after ten seconds; errors stay until dismissed.

## Location and work arrangement (0.9.9)

Choose a geographic **Location**, then tick one or more choices under **Work arrangement**: Hybrid, Remote, On-site or Not stated. Selecting Hybrid and Remote matches either arrangement.

For Melbourne hybrid jobs plus remote jobs elsewhere in Australia, choose **Melbourne**, tick **Hybrid** and **Remote**, and leave **Include Australian remote listings outside this location** checked. Uncheck that option to restrict results to the chosen location. Explicit source location restrictions still need review. Roles with an unknown location enter the Australian remote exception only when the advert explicitly states an Australian remote scope.

Your choices are remembered in this browser. Remove an individual filter chip or use **List actions → Clear filters**. Older Hybrid/Remote choices in the Location dropdown migrate to Work arrangement automatically. These browsing choices do not change fit scores or automatic-top eligibility.


## Assessment reliability (0.9.10)

The result count shows how many filtered roles have scores and how many need the original advert. **Needs advert**, **Source unavailable**, **Wrong source** and **Source incomplete** explain why a number cannot be calculated. A page being saved does not prove its requirements are complete. Use **Read & assess**, or **Paste original advert** if the board blocks access. The filtered batch reads up to 12 eligible roles; unchanged failed sources are held after one attempt until the source or assessment version changes. A direct Read & assess lets you retry deliberately.

Evidence fit combines relevant tools (30 points), specific work examples linked to job requirements (40), and the stated requirements (30). Supported evidence earns full credit; transferable or qualified evidence earns partial credit; unconfirmed obligations earn none. Components show their numerator and denominator. Missing wording no longer forces every role to 59%. A sparse advert or too few work examples still caps automatic strong-match judgement at 79%; closed roles show 0. Review flags continue to block automatic Top listings even when the percentage is higher.

This is a conservative text-based evidence aid, not a hiring probability. It can miss differently phrased experience. Specialist tenure needs a direct explicit record; overall employment dates or a company's age do not prove years using a tool. Open **Why this match** to review each criterion and its saved source evidence. Blocked, expired, anonymous or summary-only adverts may remain pending until you supply the complete original text and employer identity.


## Updating saved advert details (0.9.11)

Open **List actions → Update missing job details** to start a background queue for all incomplete saved roles. It is independent of **Find jobs** and its automatic discovery setting. The queue saves each readable original advert and updates the displayed employer, pay, requirements and score where the source supports them. Archived, applied and closed roles are skipped.

The result area shows checked, scored, closed, source-needed and waiting counts. Use **List actions → Pause details refresh** to pause after the current read; **Resume details refresh** continues without discarding progress. Progress survives restarting NextRole. Your Mac must be awake and NextRole must be running for reads to continue.

Reads are paced by source site. Blocked or still incomplete adverts get one retry after 24 hours, then remain held for an original advert or deliberate manual retry. A connection failure pauses the queue rather than repeatedly failing every saved role. After reconnecting, choose Resume. A real source edit makes that role eligible again. Unknown pay, employer or requirements remain unknown; a successful page fetch alone does not establish a complete advert.

Previous advert revisions are retained locally. Your notes, stages, original saved links, stars and prepared-packet links are preserved; changed adverts continue to flag older packets for review. This queue only reads source pages and saves job details. Existing document approval and delivery controls are unchanged.

Clicking Find jobs or Extended search again while a search is active shows that search's progress. Wait for it to finish before starting a different search.


## Completing saved source details (0.9.12)

Resuming detail refresh also rechecks already-saved adverts for supported employer headers. A recognised employer is saved without resetting your notes, stages, stars or packet links. Additional headings such as Who you are, What you bring and You might thrive in this role if you can supply original applicant requirements. Optional skills, company descriptions and board-generated summaries remain separate.

A score can describe the saved advert even when a later source check is blocked. Those cards retain a review warning and cannot become automatic Top listings until the source issue is resolved. A recruiting agency or platform name does not establish an undisclosed client employer. Truncated adverts, role mismatches and anonymous employers can still need the original employer posting or a deliberate review.

A position-description document also needs a current vacancy check. Original saved links and previous source revisions remain available locally; source completion does not claim a vacancy is currently accepting applications without evidence.


## Search beyond IT

Open **Search setup**, select **My job titles**, and enter the Australian job titles you want, one per line. Save the search and choose **Find jobs**. To use your saved IT presets, switch to **IT role presets**. The match panel shows search relevance separately from evidence fit.

Under **Profile & sources → Licences & registrations**, save credential names, jurisdictions, statuses and expiry dates where known. Use **Australia** for a national credential. Enter a class or registration scope when the advert asks for it. Leave out licence and registration numbers. The app compares your recorded details with the advert and flags missing evidence for review.

Custom searches use manual packet review and manual Top stars. Use **Check & prepare** on a complete advert to generate a résumé and cover letter for review.


## Saved-job assessment progress

The bar above **Saved opportunities** counts active jobs across the workspace before filters. Closed, applied and archived jobs are excluded. **Left for the app to check** includes ready, running and delayed source checks. **Need your input** means the app needs a profile, employer or advert details before it can score the job. **View all unrated** opens the unrated list across saved jobs.

A directory is a link to several listings. Use an individual vacancy's exact title and employer and paste its complete advert. A search excerpt, blocked advert or unidentified employer can also leave a job unrated. Open **Why unrated** on the card to see the reason.

### Filter vacancies and check other sources

Use **Vacancy status** to hide closed roles, find roles closing within seven days, or inspect closed records. Open / unconfirmed includes roles without a confirmed closing status; it does not guarantee that applications remain open. **View** groups matches, unrated roles, prepared packets and application stages. Role types, minimum score, posting date and page size are under **More filters**.

Inside a job, **Search other listings** looks for possible copies using its title and confirmed employer. Results are saved with their source links and check time. Open and verify the exact vacancy before using any quoted pay, location or requirements: reposts can be expired, estimated or for a similar role. Search excerpts do not change the saved advert or fit score. **Refresh listing** reads the saved original source.

### Choose your automatic Top listings percentage

Select **Top listings** in View, then **Change auto-top percentage**. Choose a whole percentage from **70 to 100** and select **Save Top listings preferences**. The default for new workspaces is 70%. Existing saved choices are retained. Full listing, evidence, employer and preferred-location checks still apply; closed, applied, archived and unresolved roles are excluded from automatic selection. Manually starred roles remain saved independently of their score. This setting does not submit applications or enable emails.

### Refresh missing listing details

Use the filters to select the saved roles you want checked, then click **Refresh missing details** just below the filter controls. Each click checks up to ten eligible jobs across all filtered pages, including jobs that already have scores. Applied, archived, closed and metadata-complete roles are skipped.

The check targets only missing employer, pay, location, work arrangement, employment type, posted date and closing date. It reads the original advert and, when gaps remain, makes one online search and reads up to two possible copies. A copy must identify the same role and employer and link to the exact saved vacancy before its fields can be imported. Search excerpts and salary estimates are not imported as verified facts. Only public job information is sent to search; your profile and notes are not included.

Known values and the original description are preserved. Confirmed employer/location corrections retain their prior record. Other verified fields retain a source link, evidence and check time. A source conflict stays for review. In the popup, open **Metadata check · sources and missing details** to inspect results or possible copies that need confirmation. Finding metadata does not invent requirements or guarantee a higher score.

The status line shows jobs checked, fields filled and unresolved jobs. An unsuccessful check means the checked sources did not confirm the field; it does not mean the employer never advertised it. Each job is eligible again after 24 hours, or after its saved advert changes. The next click continues with other eligible filtered jobs. The app must remain running; it records interrupted runs and preserves completed results.


## Per-role research and interview preparation

Open a saved opportunity and choose **Deep Research** or **Interview Prep**. Choose the scope, stage and frameworks before starting. Review the evidence and any missing details, then download the editable guide and quick sheet or practise one question at a time. Deep Research checks the original advert, maps duties and requirements to saved evidence, and shows conditions to confirm. Rehearsal drafts use your saved work examples. These are reviewable evidence workbooks, not independently verified company conclusions or a generative interview-writing service. See [Career Harness guide](CAREER-HARNESS.md) for limits and usage.


## Evidence scoring

The score measures recorded evidence, not your chance of being hired. Explicit essential requirements count twice standard requirements; desirable extras do not currently contribute. Weak single-word overlap receives less credit than broader transferable evidence. Known credential requirements still contribute to the score and are also shown as eligibility checks; location and schedule are checked separately. Evidence confidence identifies sparse or unresolved assessments. Adverts containing only logistics remain unrated. Some repeated scores are legitimate.


## Reading your application tracker

Applications uses compact rows with employer, role, latest status, dates and a source email link. Expand the email details to inspect the evidence. The tracker reads message contents; it does not assume every email from a company proves a new application. Prior-thread identity can help resolve a reply, while ambiguous company-only messages remain for review. Position cancellation is distinct from rejection. Older receipts are rechecked in bounded batches as the parser changes. Checking Gmail never sends, archives or labels mail.


## Local Qwen evidence review

Open a fully read, open role and choose **Assess with local Qwen**. List actions can review up to ten eligible filtered roles. Allow several minutes per advert. This requires a local llama.cpp service at 127.0.0.1:9931 with model alias `qwen3.5:9B`; the tested model is Qwen3.5-9B Q4_K_M, with a 4096-token context and one request at a time. The model itself is not included in the download.

The model interprets requirements and selects saved profile facts by ID. Original quotations are retrieved by code. An independent pass reviews the selected evidence without seeing the initial verdict. Code computes documented evidence coverage: supported = 1, partial = 0.5, undocumented = 0; explicit essential criteria count twice, optional criteria and conditions are separate. This is not a verified ability score or hiring probability. Low coverage must not dismiss a role. Review each quoted fact and the original requirement. A second model pass is not independent human verification.

Reviews remain marked Needs review and cannot automatically become strong matches or trigger application actions. Existing rule estimates remain clearly labelled until a current local review is available. Saved reviews become stale after profile, advert or date changes. Incomplete or excluded adverts are not sent to the model. The local service receives only the saved advert and relevant profile records, excluding contact details and referees. Requests cannot redirect to an external endpoint and have no cloud fallback or tools.

Malformed, incomplete, oversized or timed-out output is rejected without replacing a saved review. Check the task result for failures. If the model service is offline, start your local model service and retry. An 8 GB machine has not been qualified; memory measurements on a larger Mac do not establish smooth 8 GB operation.

Before assessment, choose **Check local Qwen rules** in List actions. The harness checks alternative requirements, compound abilities, source-link and instruction exclusion, prototype/production claims, absent credentials, strongest-evidence selection, tenure, fixed arithmetic and the actual full assessment pipeline. Every check must pass. A failed or incomplete run cannot qualify the model. Qualification is bound to the model weights, model name and rule-code hash; changing those invalidates it. Even after passing, every assessment remains subject to source/evidence validation and human review. Passing a finite test set is not proof of correctness for every advert.

The same harness can run from the installation directory with `python -m campus_agent.qwen_harness --output /path/to/report.json --workspace /path/to/workspace`. It exits nonzero on failure and stores a readable JSON report. All fixtures are synthetic; private career facts are not part of the distributed harness.


## Compare evidence coverage

Open a complete, active job and expand **Compare evidence coverage** under **Requirements and your evidence**. **Run rules only** gives a conservative check against recorded work and dates. **Compare with local AI** also runs Qwen on this Mac and shows both percentages and the quotes behind each decision.

The methods share the same explicit requirements from the saved advert. Essential requirements count twice. Full evidence earns one point, partial evidence earns half a point, and missing evidence earns zero. The rules-only arm awards full credit for direct work evidence or dated general support and leaves other cases for review. The comparison covers the extracted requirements and may miss requirements that the advert parser did not identify.

Completed comparison previews appear on job cards. Calculate coverage runs local Qwen for one complete, open job. The label identifies a Qwen preview or a rules-only preview. A preview becomes unavailable when the profile or advert changes. Automatic recommendations still require a validated rating. From the source folder, run `python -m campus_agent.scoring_comparison` for the labelled controls. Add `--with-qwen` to run both arms against the same controls using the local model service.

Use **Update saved jobs** for missing facts and adverts. In a job, **Next steps** contains the research document, interview preparation document, and résumé and cover letter. Research can use public search service credits. The research setup explains its scope before you start.


## Source matrix (0.9.29)

Coverage comparisons now collect quoted duties as well as candidate requirements directly from the advert. Repeated identical statements share one row. Optional criteria, logistics, eligibility conditions and application/source instructions are listed separately and excluded from the percentage. A clause that mixes mandatory and preferred scope requires review before calculation.

An AND group must have all its stated parts established for full credit. An OR group requires a qualifying alternative, including shared scope or duration. Source wording stays intact so qualifiers are visible. Different descriptions of a related duty can still overlap and need human review.

The fixed formula remains one point for supported evidence, half a point for partial evidence, and zero for undocumented evidence. Explicit essential criteria have double weight. The comparison also shows the fully documented percentage and the percentage that would result if its partially documented criteria were completed. The rules-only result is labelled a lower bound because it misses equivalent experience.

Changing the matrix invalidates older previews. Recalculate a job to see its current set of duties, optional items, conditions and evidence.

A proposed full-credit AND/list match also passes a literal scope cross-check. Residual unconfirmed terms reduce it to partial and are shown for review. Equivalent wording can trigger this conservative check, so it is a review aid with false negatives.


## Transferable-fit scoring (0.9.30)

Job cards now distinguish transferable fit from evidence coverage. Direct demonstrated work earns 100% credit. Strongly comparable delivered work earns 75%, a meaningful demonstrated subset earns 50%, and relevant training, prototypes or conceptual foundations earn 25%. An explicitly confirmed capability gap earns zero. Missing evidence remains unknown.

The fit percentage is the weighted mean of assessed criteria. Unknown criteria are excluded from that denominator and reduce the separate evidence-coverage percentage. Essential criteria count twice, ordinary criteria once. Preferred criteria and logistics/eligibility conditions stay separate. A high score based on little assessed evidence is provisional.

The model must quote confirmed records and explain the transfer bridge and remaining scope. Its evidence verifier sees only the selected facts and the claim. A prototype or saved skill alone cannot receive delivery credit. Missing facts cannot become confirmed gaps. Relevant support tenure is calculated from dates, while specialist tool tenure stays unknown unless documented. Current structured credentials are included in the evidence pool.

The rules-only check reports the share of weighted criteria with direct evidence. The job card displays a reviewed fit or a labelled Qwen suggestion when available. Changes to the advert, profile or scoring logic require a new review.
