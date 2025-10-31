Code Review: pdum.gcp

Date: 2025-10-31

Scope
- Reviewed Python source under `src/pdum/gcp`, tests in `tests/`, packaging/CI in `pyproject.toml` and `.github/workflows`, and AGENTS.md.
- Per request: removed mistaken CLI entrypoint, began converting docstrings to NumPy format, and identified refactor/test improvements.

Summary
- The library is well-structured with clear separation between admin utilities and resource types. Optional credentials are consistently keyword-only and ADC fallback is used correctly. Read-only operations dominate; mutation methods exist but are never executed in tests (consistent with AGENTS.md).
- Biggest immediate fix: a broken console script entry pointing to a non-existent `pdum.gcp.cli:main` (removed).
- Documentation is generally thorough but mixed style. NumPy-style conversions started; suggest completing in a follow-up sweep.
- Tests are mostly safe in CI; several “existence” tests are low-value and could be consolidated to reduce CI time.

Strengths
- Clear modeling of GCP resources with dataclasses (`Organization`, `Folder`, `Project`, `BillingAccount`) and sentinels (`NO_ORG`, `NO_BILLING_ACCOUNT`).
- Thoughtful traversal helpers (`walk_projects`, `tree`, `cd`) and pagination handling via `list_next`.
- Packaging includes `py.typed` and data-file bundling for `api_map.txt`.
- Good adherence to “keyword-only optional parameters” guideline.

Issues and Code Smells
1) Broken CLI entry
   - `pyproject.toml` defined `pdum_gcp = "pdum.gcp.cli:main"` but no `cli.py` exists. Installing the wheel would expose a dead console script.
   - Action: removed the `[project.scripts]` entry.

2) Docstring style inconsistency
   - Docstrings mix styles; several are narrative or Google-style. NumPy format is the project standard.
   - Action: converted several high-visibility functions to NumPy format (admin: `get_email`, `list_organizations`, `quota_project`, `walk_projects`, `_load_api_map`, `lookup_api`; types: `Container.tree`, `Container.cd`, `Organization.billing_accounts`, `Project.enabled_apis`). Recommend a follow-up sweep to complete the conversion.

3) Unused import
   - `admin.py` imports `backoff` but does not use it.
   - Action: removed the unused import. Optionally drop `backoff` from runtime deps later if not needed elsewhere.

4) Service client construction duplication
   - Repeated `discovery.build("cloudresourcemanager", version, ...)` and other service clients across methods.
   - Suggestion: introduce small internal helpers (non-public) to construct clients, e.g. `_crm_v1(creds)`, `_crm_v2(creds)`, `_service_usage(creds)`, `_cloud_billing(creds)` to reduce repetition and make it easier to change options (timeouts, user agent, etc.). Keep them private in `types.py` or a `clients.py` to avoid expanding public API.

5) `quota_project` project-id sourcing
   - Current behavior pulls the project id from environment via `google.auth.default()` even when explicit credentials are passed, which is fine but potentially surprising.
   - Suggestion: allow an explicit `project_id: str | None = None` keyword-only parameter. If provided, prefer it; else fall back to environment. This preserves existing behavior while improving clarity.

6) Fuzzy API resolution UX
   - `lookup_api` normalizes by removing the word "cloud" and tries substring matching for short queries; this is pragmatic but can still be surprising.
   - Suggestions:
     - Return structured candidates on ambiguity (e.g., top N matches) with service ids; or add `return_candidates: bool = False` to optionally surface options without raising.
     - Cache the loaded `api_map` module-wide to avoid re-parsing the large text file on repeated calls.

7) `tree` printing duplication
   - `tree` and `_tree_children` share similar code paths for printing children.
   - Suggestion: refactor to a single recursive function that takes a flag indicating whether to print the current node, or to generate lines via a generator to simplify control flow.

8) Tests – low-value assertions
   - Several tests only assert that attributes/methods exist or that functions are callable (`test_admin_module_imports`, `test_types_module_imports`, `test_admin_functions_are_callable`, `test_container_has_*`). These provide minimal safety beyond import smoke-tests and can be consolidated.
   - Suggestions:
     - Keep one import smoke test per module and drop granular attribute existence tests unless they guard a known regression.
     - Focus CI-safe unit tests on behavior that doesn’t hit live APIs (e.g., `Project.suggest_name` edge cases, `lookup_api` behavior using a small fixture map, error handling paths for `cd`, sentinel semantics).
     - Retain manual tests for live API interactions behind `PDUM_GCP_MANUAL_TESTS`.

9) Dependencies
   - `typer` is listed but the CLI was removed; if no other code uses `typer`, consider removing it from runtime dependencies to speed installs. Similarly confirm whether `google-cloud`, `google-cloud-iam`, etc. are needed at runtime vs. development.

10) Safety and mutation rules
   - `Folder.create_folder` and `Project.enable_apis` implement mutation as required, with correct parameter placement and LRO polling; they are not called in tests.
   - Optional improvement: Add docstring “Safety” notes to these methods (already present) and consider an opt-in guard (environment variable or param) to reduce accidental use in ad-hoc scripts—balance with not hindering legitimate users.

Docstring Conversions (examples implemented)
- Converted to NumPy style with explicit Parameters/Returns/Raises and "Examples" blocks:
  - `admin.get_email`, `list_organizations`, `quota_project`, `walk_projects`, `_load_api_map`, `lookup_api`.
  - `types.Container.tree`, `types.Container.cd`, `types.Organization.billing_accounts`, `types.Project.enabled_apis`.
- Follow-up: complete remaining methods/classes to keep the public surface consistent.

Refactor Opportunities (non-breaking)
- Add private client factories to reduce repetition and centralize options.
- Extract a small `traverse_children(container)` generator used by both `tree` and `walk_projects` to unify traversal logic.
- Cache `api_map` after first load in `admin.py` to avoid repeated file I/O.

Testing Recommendations
- Consolidate existence/callable tests into a single smoke test per module.
- Add fixture-based tests for `lookup_api` with a tiny in-repo map to exercise exact/fuzzy/ambiguous paths without hitting the network.
- Add edge-case tests for `Project.suggest_name` (length boundaries, invalid prefixes, random_digits bounds) — some exist already; extend where valuable.

CI/Packaging
- Console script removed to avoid broken entrypoints.
- Wheel `force-include` already packages `data/` correctly; keep `api_map.txt` refreshed per AGENTS.md.

Conclusion
- Codebase is in solid shape for a utilities library. The targeted cleanup (CLI removal, docstring normalization start, unused import removal) improves quality. Next high-impact steps are docstring sweep, consolidating low-value tests, and small internal helpers for client construction/caching. No breaking API changes are recommended at this time.

