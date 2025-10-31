# pdum_gcp

[![CI](https://github.com/habemus-papadum/pdum_gcp/actions/workflows/ci.yml/badge.svg)](https://github.com/habemus-papadum/pdum_gcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/habemus-papadum-gcp.svg)](https://pypi.org/project/habemus-papadum-gcp/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

GCP utils

## What This Project Is

`pdum_gcp` is a toolbox for seasoned administrators who need to nurture Google Cloud estates that sprawl across multiple organizations. Think of the kind of tasks you might script in Terraform, except you want an interactive, incremental workflow that lets one trusted human explore, prototype, and tidy up quickly. This library intentionally does **not** scale beyond a tiny circle of grizzled operators—ideally a team of one—because it assumes every participating identity has god-like access across those organizations.

The focus here is admin hygiene: inspecting estates, checking IAM, enabling required APIs, and wiring up billing or quota projects. Once the scaffolding exists, you drop back into the regular Google Cloud Python clients to actually use the resources. A core tenet is “bring your own identity”: everything runs under your Application Default Credentials, which belong to you, not the orgs you help. That makes this powerful, but also dangerous—misplaced trust, compromised credentials, or sloppy copy/paste can translate into real financial and operational damage.

Use this library only if you:

- Operate in small, high-trust environments where rapid create/tear-down cycles matter.
- Regularly hop between organizations or short-lived projects.
- Understand that you are working with loaded weapons and accept the risk.

### Feature Highlights

- Pre-flight your environment with `doctor()` to confirm identity, quota project, and API readiness.
- Explore estates with `list_organizations()`, `walk_projects()`, and container helpers.
- Resolve quota projects and billing details with `quota_project()` and billing sentinels.
- Inspect IAM with `get_iam_policy()` and `list_roles()` before making changes.
- Map friendly API names to service IDs via `lookup_api()` and the bundled catalog.

🧭 Ready to see it in action? Follow the [Interactive Admin Tutorial](tutorial.md) for a guided, output-rich walkthrough (with sensitive identifiers anonymized).


## Development

This project uses [UV](https://docs.astral.sh/uv/) for dependency management.

### Setup

```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone the repository
git clone https://github.com/habemus-papadum/pdum_gcp.git
cd pdum_gcp

# Provision the entire toolchain (uv sync, pnpm install, widget build, pre-commit hooks)
./scripts/setup.sh
```

**Important for Development**:
- `./scripts/setup.sh` is idempotent—rerun it after pulling dependency changes
- Use `uv sync --frozen` to ensure the lockfile is respected when installing Python deps

### Running Tests

```bash
# Run all tests
uv run pytest

# Run a specific test file
uv run pytest tests/test_example.py

# Run a specific test function
uv run pytest tests/test_example.py::test_version

# Run tests with coverage
uv run pytest --cov=src/pdum/gcp --cov-report=xml --cov-report=term
```

### Code Quality

```bash
# Check code with ruff
uv run ruff check .

# Format code with ruff
uv run ruff format .

# Fix auto-fixable issues
uv run ruff check --fix .
```

### Building

```bash
# Build Python + TypeScript artifacts
./scripts/build.sh

# Or build just the Python distribution artifacts
uv build
```

### Publishing

```bash
# Build and publish to PyPI (requires credentials)
./scripts/publish.sh
```

### Automation scripts

- `./scripts/setup.sh` – bootstrap uv, pnpm, widget bundle, and pre-commit hooks
- `./scripts/build.sh` – reproduce the release build locally
- `./scripts/pre-release.sh` – run the full battery of quality checks
- `./scripts/release.sh` – orchestrate the release (creates tags, publishes to PyPI/GitHub)
- `./scripts/test_notebooks.sh` – execute demo notebooks (uses `./scripts/nb.sh` under the hood)
- `./scripts/setup-visual-tests.sh` – install Playwright browsers for visual tests

## License

MIT License - see LICENSE file for details.
