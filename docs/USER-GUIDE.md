# NextRole for Mac

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
2. Find **NextRole-Mac-0.8.4.zip**, the download you received.
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
The same message is in **CODEX SETUP PROMPT.txt** inside the extracted package.

```setup-prompt
Set up this NextRole ZIP on my Mac. I am not technical: use plain English, explain what I should see, and guide me through anything that needs my input.

Locate the ZIP I attached, confirm a suitable local project folder with me, and unpack it there. Do not overwrite an existing installation or personal workspace. If the folder is already extracted, reuse the correct folder containing launcher.py and Start NextRole.command. If you cannot access the attachment or write to the intended folder, help me choose a permitted local location. Read START HERE.txt, docs/USER-GUIDE.md and the launcher instructions before making changes.

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
2. Drag the whole **NextRole-Mac-0.8.4** folder into **Documents**.
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
