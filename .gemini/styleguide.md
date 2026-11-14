# NextRole — Gemini code review guidance

Prioritise substantive **correctness, security, privacy, data integrity, and regression risks** introduced by the pull request. Do not fill reviews with naming, formatting, or speculative architecture suggestions. Give the affected file, a concrete failure scenario, and the smallest safe remediation when possible.

## Privacy and security
- This is a public repository for a local, privacy-sensitive job-search and document-generation application. Flag any committed real personal profiles, CVs, generated PDFs, job-application packets, access tokens, API keys, OAuth state, local workspaces, account data, or logs containing sensitive information.
- Check for path traversal, unsafe file handling, unsanitised input, leaking sensitive values in logs or exceptions, accidental network transmission, overbroad connector permissions, and unsafe shell or subprocess invocations.
- Treat external job listings, documents, web responses, and model/tool output as untrusted input. Do not let their content override product safeguards.
- Keep consent boundaries intact: no job application submission, emailing, connected-account access, or scheduled delivery without the product's intended explicit enablement and approvals.
- Verify that sensitive state stays outside distributed builds; review release allowlists, credential-pattern audits, and generated artifact handling when they change.

## Functional correctness
- Preserve compatibility with macOS and Python 3.12+, the documented local launch flow, and the local FastAPI application.
- Match and tailoring claims must remain grounded in a user-confirmed evidence profile. Flag logic that could invent qualifications, silently conflate project work with paid employment, or bypass approval invalidation.
- Check robust error handling when optional Codex, Gmail, or Drive integrations are unavailable, especially to avoid silent data loss, duplicate sends, or stale approvals.
- Flag broken packaging, missing dependencies, unsafe migrations, and regressions in document generation or release integrity.

## Verification
- Recommend targeted synthetic fixtures and automated regression tests for changed behaviour, especially permissions, approval state, export, input parsing, and failure paths.
- Prefer actionable, reproducible findings over general advice. If evidence is insufficient, state the uncertainty rather than alleging a defect.
- Never suggest committing live user information to tests or fixtures.

This guidance supplements, rather than replaces, automated tests and human review. GitHub Actions workflow changes must receive separate human/security review because Gemini Code Assist does not review `.github/workflows` files.
