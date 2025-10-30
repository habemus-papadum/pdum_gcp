# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

This is a Python library called `gcp` (package name: `gcp`, module name: `pdum.gcp`). Utilities and tools for Google Cloud

The project uses a modern Python toolchain with UV for dependency management.

## Important Rules

### Version Management
**NEVER modify the version number in any file.** Version numbers are managed exclusively by humans. Do not change:
- `pyproject.toml` version field
- `src/pdum/gcp/__init__.py` `__version__` variable
- Any version references in documentation

If you think a version change is needed, inform the user but do not make the change yourself.

### Release Management
**ABSOLUTELY NEVER RUN THE RELEASE SCRIPT (`./scripts/release.sh`).** This is a production deployment script that:
- Publishes the package to PyPI (affects real users)
- Creates GitHub releases (public and permanent)
- Pushes commits and tags to the repository
- Triggers documentation deployment

**This script should ONLY be run by a human who fully understands the consequences.** Do not:
- Execute `./scripts/release.sh` under any circumstances
- Suggest running it unless the user explicitly asks about the release process
- Include it in automated workflows or scripts

If the user needs to make a release, explain the process but let them run the script themselves.

## Development Commands

### Environment Setup
```bash
# Bootstrap the full toolchain (uv sync, pnpm install, widget build, hooks)
./scripts/setup.sh
```

**Important for Development**:
- Use `uv sync --frozen` to ensure the lockfile is used without modification, maintaining reproducible builds
- Re-run `./scripts/setup.sh` whenever dependencies change

### Testing
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

### Publishing
```bash
# Build and publish to PyPI (requires credentials)
./scripts/publish.sh
```

## Architecture

### Project Structure
- **src/pdum/gcp/**: Main package source code (src-layout)
  - `__init__.py`: Package initialization and version
- **tests/**: Test suite using pytest
  - `test_example.py`: Example tests

### Key Constraints
- **Python Version**: Requires Python 3.12+
- **Dependency Management**: Uses UV exclusively; uv.lock is committed
- **Build System**: Uses Hatch/Hatchling for building distributions

### Code Standards
- **Ruff Configuration**:
  - Target: Python 3.12
  - Line length: 120 characters
  - Linting rules: E (pycodestyle errors), F (pyflakes), W (warnings), I (isort)
- **Type Hints**: Use type hints where appropriate
- **Docstrings**: NumPy style, include Parameters, Returns, Raises sections

### Testing Strategy
- Test files must start with `test_` prefix
- Test classes must start with `Test` prefix
- Test functions must start with `test_` prefix
- Tests run with `-s` flag (no capture) by default
- Coverage reporting: use `--cov=src/pdum/gcp --cov-report=xml --cov-report=term`

### Testing Configuration
The pytest configuration is in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-s"
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

Coverage configuration is also in `pyproject.toml`:
```toml
[tool.coverage.run]
source = ["src/pdum/gcp"]
relative_files = true
omit = [
    "*/tests/*",
    "*/testing.py",
]
```

## CI/CD

### Continuous Integration
The project uses GitHub Actions for CI (`.github/workflows/ci.yml`):
- Runs on every push to main and pull requests
- Executes linting with ruff
- Runs unit tests with coverage reporting
- Posts coverage report as a PR comment

### Release Process
Releases are managed by the `./scripts/release.sh` script (HUMANS ONLY):
1. Validates git repo is clean
2. Checks version has `-alpha` suffix
3. Runs all validation (tests, linting)
4. Strips `-alpha` from version for release
5. Creates release commit and tag
6. Publishes to PyPI
7. Creates GitHub release
8. Bumps to next development version with `-alpha`

The release script expects versions to follow the pattern: `X.Y.Z-alpha` → `X.Y.Z` → `X.Y.(Z+1)-alpha`
