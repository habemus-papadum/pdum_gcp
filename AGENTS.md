# AGENTS.md

This file provides guidance to AI agents when working with code in this repository.

## Project Overview

This is a Python library called `gcp` (package name: `gcp`, module name: `pdum.gcp`). Utilities and tools for Google Cloud

The project uses a modern Python toolchain with UV for dependency management.

## ⚠️ CRITICAL: GCP Estate Mutation Rules

**ABSOLUTELY NEVER RUN ANY CODE THAT MUTATES THE GCP ESTATE.**

This is a library that interacts with real Google Cloud Platform resources. Running mutation operations can:
- Create real cloud resources that incur costs
- Modify production infrastructure
- Delete critical resources
- Affect real users and services

### What Constitutes GCP Estate Mutation

GCP estate mutation includes ANY operation that:
- Creates resources (folders, projects, IAM bindings, etc.)
- Modifies resources (updating names, permissions, configurations)
- Deletes resources (folders, projects, etc.)
- Changes state (enabling APIs, moving resources)

### What You MUST NOT Do

**NEVER:**
- Run any method that creates, modifies, or deletes GCP resources
- Write tests that call mutation methods (even in test environments)
- Execute example scripts that demonstrate mutation operations
- Call methods like `create_folder()`, `create_project()`, `delete_*()`, etc.
- Run manual tests marked with `@manual_test` that perform mutations

**Examples of FORBIDDEN operations:**
```python
# DO NOT RUN THESE - EXAMPLES ONLY
org.create_folder("test")  # Creates real folder - DO NOT RUN
project.delete()  # Deletes real project - DO NOT RUN
folder.update_name("new-name")  # Modifies real resource - DO NOT RUN
```

### What You CAN Do

**You MAY:**
- Read GCP resources (list organizations, folders, projects)
- Implement mutation methods (write the code but never execute it)
- Write documentation for mutation methods
- Create example scripts (but never run them)
- Verify syntax and type checking

**Safe read-only operations:**
```python
# These are safe to run
list_organizations()  # Read-only
org.folders()  # Read-only
org.projects()  # Read-only
org.tree()  # Read-only (just prints)
Project.suggest_name()  # Pure function, no API calls
```

### Testing Policy for Mutation Methods

When implementing methods that mutate GCP estate:

1. **Implementation**: Write the code with proper documentation
2. **No Unit Tests**: Do NOT write automated tests for mutation methods
3. **No Manual Tests**: Do NOT write `@manual_test` tests for mutation methods
4. **User Testing**: Let the user test mutation methods themselves
5. **Documentation**: Provide clear docstrings and examples (but never execute them)

**Example approach:**
```python
# ✅ CORRECT: Implement the method
def create_folder(self, display_name: str) -> Folder:
    """Create a new folder."""
    # ... implementation ...

# ❌ WRONG: Do not write tests
def test_create_folder():  # DO NOT CREATE THIS
    org.create_folder("test")  # This would mutate real GCP estate

# ✅ CORRECT: Only test that the method exists
def test_create_folder_method_exists():
    assert hasattr(Organization, "create_folder")
    assert callable(Organization.create_folder)
```

### If You Accidentally Run a Mutation

If you accidentally run code that mutates GCP estate:
1. **STOP IMMEDIATELY**
2. Inform the user of what happened
3. Provide details about what was created/modified/deleted
4. Do not attempt to "fix" it by running more mutations
5. Let the user decide how to handle the situation

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

## Researching Google Cloud APIs

**ALWAYS research the exact API format before implementing GCP functionality.**

This library uses the `googleapiclient` (Google API Client) to interact with GCP services. The API documentation is essential because:
- Parameter names and formats change between API versions
- Some parameters are passed as method arguments, others in the request body
- Field requirements and constraints are specific to each API

### How to Research GCP APIs

When implementing a new GCP feature:

1. **Identify the API and version** you're using (e.g., Cloud Resource Manager V2)

2. **Find the official Python API documentation** using one of these methods:

   **Method 1: Web Search (Preferred)**
   ```
   Search: "Google Cloud [Service Name] [version] [resource] Python API documentation"
   Example: "Google Cloud Resource Manager v2 folders Python API documentation"
   ```

   This typically leads to URLs like:
   - `https://developers.google.com/resources/api-libraries/documentation/[service]/[version]/python/latest/`
   - `https://cloud.google.com/python/docs/reference/[service]/latest`

   **Method 2: Examine Installed Package**
   ```bash
   # Find the package location
   uv run python -c "import googleapiclient; print(googleapiclient.__file__)"

   # Look for discovery documents or generated client code
   # Usually in: .venv/lib/python3.12/site-packages/googleapiclient/
   ```

3. **Use WebFetch to read the documentation** and look for:
   - Method signatures (what parameters are required)
   - Request body format (what fields go in the `body=` parameter)
   - Response format (what the API returns)
   - Field constraints (length limits, regex patterns, etc.)
   - Long-running operations (some methods return operations, not resources directly)

4. **Pay special attention to:**
   - **Parameters vs. Body**: Some values go in method parameters (like `parent=`), others go in the `body=` dict
   - **API versioning**: V1, V2, V3 APIs have different formats
   - **Long-running operations**: Methods like `create()` may return an operation that needs polling
   - **Pagination**: List methods often require pagination handling

### Example: Researching folders.create()

```python
# WRONG - Don't guess the API format
operation = crm_service.folders().create(body={
    "displayName": name,
    "parent": parent_name,  # ❌ parent should be a parameter!
}).execute()

# CORRECT - Research shows parent is a separate parameter
operation = crm_service.folders().create(
    body={"displayName": name},
    parent=parent_name  # ✅ Correct placement
).execute()
```

### Key Documentation URLs

Keep these bookmarked for reference:

- **Cloud Resource Manager V2 (Folders)**:
  https://developers.google.com/resources/api-libraries/documentation/cloudresourcemanager/v2/python/latest/

- **Cloud Resource Manager V1 (Projects/Organizations)**:
  https://developers.google.com/resources/api-libraries/documentation/cloudresourcemanager/v1/python/latest/

- **Google Cloud Python Client Libraries**:
  https://cloud.google.com/python/docs/reference

### Testing API Implementations

Since you cannot run mutation methods, rely on:
1. Syntax validation (imports work, types are correct)
2. Documentation review (parameters match the docs)
3. Code review (logic follows the documented flow)
4. Let the user test the actual API calls

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

### Keyword-Only Parameters

**IMPORTANT: Prefer keyword-only parameters for optional arguments.**

This project uses keyword-only parameters extensively to make API calls more explicit and prevent accidental parameter mismatches. This is especially important for optional parameters like `credentials`.

#### When to Use Keyword-Only Parameters

Use keyword-only parameters (with `*`) for:
- Optional parameters (anything with a default value)
- Parameters that aren't critical to understanding the function's purpose at the call site
- Parameters that might be easily confused or misordered

**Examples:**

```python
# ✅ CORRECT: Keyword-only parameters for optional args
def get_email(*, credentials: Optional[Credentials] = None) -> str:
    """Get email from credentials."""
    pass

def create_folder(self, display_name: str, *, credentials=None) -> Folder:
    """Create a folder with required name and optional credentials."""
    pass

def tree(self, *, credentials=None, _prefix: str = "", _is_last: bool = True) -> None:
    """Print tree with all optional parameters."""
    pass

# ❌ WRONG: Positional optional parameters
def get_email(credentials: Optional[Credentials] = None) -> str:  # Bad
    pass

def create_folder(self, display_name: str, credentials=None) -> Folder:  # Bad
    pass
```

#### Calling Convention

When calling methods with keyword-only parameters, always use keyword arguments:

```python
# ✅ CORRECT: Use keyword arguments
email = get_email(credentials=my_creds)
projects = org.projects(credentials=my_creds)
folder = org.create_folder("MyFolder", credentials=my_creds)

# ❌ WRONG: Cannot use positional arguments (will raise TypeError)
email = get_email(my_creds)  # TypeError!
projects = org.projects(my_creds)  # TypeError!
```

#### Benefits

1. **Explicitness**: Call sites clearly show what each argument represents
2. **Safety**: Prevents accidental argument swapping or mismatches
3. **Evolution**: Makes it easier to add new optional parameters without breaking existing code
4. **Readability**: Code is self-documenting at the call site

#### Pattern for Required + Optional Parameters

When you have both required and optional parameters:

```python
def method(self, required_arg: str, *, optional_arg=None, another_optional=None):
    """
    Method with required positional arg and keyword-only optional args.

    Args:
        required_arg: This must be passed positionally
        optional_arg: This must be passed by keyword if provided
        another_optional: This must be passed by keyword if provided
    """
    pass

# Correct usage:
obj.method("required")
obj.method("required", optional_arg="value")
obj.method("required", optional_arg="value", another_optional="other")
```

#### Consistency

**All methods accepting `credentials` parameter use keyword-only:**
- `get_email(*, credentials=None)`
- `list_organizations(*, credentials=None)`
- `Container.parent(*, credentials=None)`
- `Container.folders(*, credentials=None)`
- `Container.projects(*, credentials=None)`
- `Container.create_folder(display_name, *, credentials=None)`
- `Container.tree(*, credentials=None, ...)`
- `Project.billing_account(*, credentials=None)`

When implementing new methods, follow this pattern consistently.

### Testing Strategy
- Test files must start with `test_` prefix
- Test classes must start with `Test` prefix
- Test functions must start with `test_` prefix
- Tests run with `-s` flag (no capture) by default
- Coverage reporting: use `--cov=src/pdum/gcp --cov-report=xml --cov-report=term`

#### Manual Tests (Skipped in CI)
Some tests require real GCP credentials or interact with live APIs. These tests are useful for development but should not run in CI:

**Creating Manual Tests:**
```python
import os
import pytest

# Define a decorator for manual tests
manual_test = pytest.mark.skipif(
    not os.getenv("PDUM_GCP_MANUAL_TESTS"),
    reason="Manual test - requires GCP credentials. Set PDUM_GCP_MANUAL_TESTS=1 to run.",
)

@manual_test
def test_something_requiring_gcp():
    """This test will be skipped in CI."""
    # Test code that requires real GCP access
    pass
```

**Running Manual Tests Locally:**
```bash
# Run all manual tests
PDUM_GCP_MANUAL_TESTS=1 uv run pytest tests/ -v

# Run specific manual test file
PDUM_GCP_MANUAL_TESTS=1 uv run pytest tests/test_admin.py -v

# Run specific manual test function
PDUM_GCP_MANUAL_TESTS=1 uv run pytest tests/test_admin.py::test_get_adc_email -v
```

**When to Use Manual Tests:**
- Tests that require Application Default Credentials (ADC)
- Tests that interact with real GCP APIs (Cloud Resource Manager, IAM, etc.)
- Tests that might incur costs or require specific GCP project setup
- Integration tests that verify end-to-end functionality with real resources

**Guidelines for Manual Tests:**
- Always add clear docstrings explaining what the test does
- Document any required GCP permissions or setup
- Include helpful print statements showing test progress/results
- Keep manual tests separate from unit tests that can run in CI
- Consider adding corresponding unit tests that mock GCP APIs for CI coverage

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
