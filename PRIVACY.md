# Privacy and sharing

NextRole starts with a blank local workspace. Each user supplies their own profile,
source documents, connected accounts and optional schedules. Automatic discovery,
sending and application tracking are off until configured.

Never publish a used installation as a folder ZIP. Use `scripts/build_release.py`,
which exports only listed source files and rejects runtime paths, symlinks, private
keys, common credentials and local home-directory paths. It also accepts additional
private-data patterns through `--private-pattern`; patterns are not saved in releases.

The clean release and source repository exclude runtime databases, source résumés,
referee details, generated PDFs, inbox contents, account state, connection credentials,
logs, screenshots, local settings and automation files. Example identities and test
contacts are synthetic and use reserved example domains. Public no-reply sender
addresses appear only in email-classification test fixtures.

The connected workspace uses local evidence rules and grounded templates. Codex
scheduled runs are separate and use the model selected in Codex; this source does not
pin a paid inference model. Gmail/Drive connections can access private data, and
authorized packet delivery sends PDFs to the connected inbox and optionally Drive.
Review both documents and your factual profile before using them.

No employer applications are submitted. Do not add real documents or private
configuration to issues, screenshots, pull requests, tests or repository history.
