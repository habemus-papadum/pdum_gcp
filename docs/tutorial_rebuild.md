# Tutorial Rebuild Playbook

This guide captures the process I followed to produce `tutorial.md`. Re-run these steps whenever the APIs, outputs, or best practices drift far enough that the tutorial feels stale.

## 1. Prepare a Clean Environment

- Use a workstation with **trusted** Application Default Credentials (ADC). Run `gcloud auth application-default login` if needed.
- Ensure the credentials belong to a human identity with broad read and admin rights across the relevant organizations.
- Verify the working tree is clean (`git status`) and dependencies are up to date (`uv sync --frozen`).

## 2. Refresh Background Knowledge

- Skim `docs/demos/pdum_gcp_demo.ipynb` to recall the flow and API calls.
- Check `AGENTS.md` for policy reminders (no destructive operations in CI, warning language, etc.).
- Review recent code changes in `pdum.gcp.admin` and `pdum.gcp.types` so the tutorial reflects the current public surface.

## 3. Capture Fresh Outputs

1. Launch a Python REPL (I use `uv run python` so the repo environment is respected).
2. Execute only **read-only** helpers in the order used by the tutorial:
   - `doctor()`
   - Identity and quick survey (`get_email`, `list_organizations`, `quota_project`, `walk_projects`)
   - Container exploration (`folders()`, `projects()`, `tree()`)
   - IAM inspection (`list_roles`)
   - API enablement state (`enabled_apis`)
   - Lookup helpers (`lookup_api`)
   - Billing introspection (`billing_accounts`)
3. Copy the terminal output for each section into a scratchpad. Preserve formatting from Rich tables by capturing the terminal text, not HTML.

> ❗️Do **not** run mutation helpers (e.g., `enable_apis`, `create_project`, billing updates) while collecting samples. They belong in separate, human-reviewed workflows.

## 4. Sanitize the Transcript

- Replace every real identifier—emails, project IDs, org numbers, folder IDs, billing account IDs—with consistent fictitious values (`user@example.com`, `acme-research`, `organizations/123456789`, etc.).
- Double-check there are no lingering references to sensitive data (quota project numbers, role bindings that expose teammates, etc.).
- If Rich tables or tree diagrams change width after redaction, reflow them manually so the box-drawing characters align.

## 5. Update `docs/tutorial.md`

- Paste the sanitized output into the existing code/output blocks.
- Adjust surrounding narrative to cover any new warnings, features, or behavior changes.
- Cross-link to new APIs or helper functions if the public surface grew.
- Re-read the file from top to bottom for clarity and tone; keep the “grizzled operator” voice consistent with the intro.

## 6. Validate Locally

- Run `uv run mkdocs serve` (or `mkdocs build`) to make sure the new Markdown renders and links resolve. Fix lint or build warnings immediately.
- Spot-check the tutorial in a browser: code fences, tables, and emoji should render as expected.

## 7. Commit the Refresh

- Stage changes to `docs/tutorial.md` (and this playbook if it evolved).
- Add a concise commit message, e.g., `docs: refresh interactive tutorial`.
- Push, open a PR, and flag reviewers who should verify the sanitized data still looks safe.

Keeping this process documented means the next refresh happens quickly and safely—even if months have passed since the last touch.
