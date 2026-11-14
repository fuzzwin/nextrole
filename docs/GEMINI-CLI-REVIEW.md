# Gemini CLI pull request reviews

This repository uses [google-github-actions/run-gemini-cli](https://github.com/google-github-actions/run-gemini-cli) to prepare advisory pull-request reviews via Gemini CLI.

## One-time owner setup

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/app/apikey).
2. Open [NextRole Actions secrets](https://github.com/fuzzwin/nextrole/settings/secrets/actions).
3. Add a **repository secret**, named exactly `GEMINI_API_KEY`. Paste the key **only in GitHub Settings**. Never commit or post it in an issue, PR, chat or log.
4. Merge the PR that adds `.github/workflows/gemini-cli-review.yml`. After merging, repository actions must be enabled for the workflow to run.
5. Create a small, same-repository, non-draft test PR to confirm Gemini can post a review.

The API-key path uses the GitHub Actions-provided `GITHUB_TOKEN` rather than a separate GitHub App. It does **not** require the Developer Connect / billing-enabled Google Cloud setup from Gemini Code Assist for GitHub. API quotas and possible costs still depend on your Google account and usage.

## Review triggers

- Automatic: an opened, reopened or updated **same-repository, non-draft** PR, or a PR marked ready for review.
- On demand: a repository owner, collaborator or member comments `@gemini-cli /review` on a PR.
- Manual: Actions → **Gemini CLI PR review** → Run workflow, supply an existing PR number.

The workflow checks out the **trusted default branch**, not the PR head. It reads the PR diff through restricted GitHub MCP review tools, can submit a review, and is not authorised to modify project code, create commits, approve, or merge. Fork PRs are excluded from **automatic** review; do not enable automatic fork access with `pull_request_target` and secrets.

The root `GEMINI.md` sets project-specific review criteria. The Google action and checkout action are pinned to fixed commits; review dependency updates deliberately.

## Limits and validation

- No review runs until the workflow is on the default branch and `GEMINI_API_KEY` is configured.
- This workflow is advisory. Existing Python tests, release audits and human review remain required.
- Issues and PR text are untrusted input; verify each Gemini recommendation before acting.
- If a run fails, open the Actions run log. Never enable verbose output that can disclose secrets.
- Authentication and limits: [official action documentation](https://github.com/google-github-actions/run-gemini-cli).
