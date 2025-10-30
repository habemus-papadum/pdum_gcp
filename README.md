# pdum_gcp

[![CI](https://github.com/habemus-papadum/pdum_gcp/actions/workflows/ci.yml/badge.svg)](https://github.com/habemus-papadum/pdum_gcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/habemus-papadum-gcp.svg)](https://pypi.org/project/habemus-papadum-gcp/)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

A layered automation framework for Google Cloud Platform that enables organization-level infrastructure management through admin service accounts.

## ⚠️ Important Security Caveat

**This tool is designed for individual researchers and small teams who want complete control of their cloud infrastructure.** It creates service accounts with full organization-level admin permissions, which can be a significant security risk.

**This is NOT recommended for large-scale organizations or production environments.**

### Why This Approach Has Risks

- **Single Point of Failure**: If the admin bot credentials are compromised, an attacker has full control of your entire GCP organization
- **Broad Permissions**: Organization Admin and Billing Admin roles grant essentially unlimited access
- **Credential Management**: Service account keys stored locally need to be carefully protected

### When to Use This Tool

✅ **Good Use Cases:**
- Individual researchers managing their own cloud resources
- Small teams with full trust between members
- Development/testing environments
- Learning and experimentation
- Early-stage projects requiring rapid iteration

❌ **Not Recommended For:**
- Enterprise organizations with compliance requirements
- Multi-team environments with varying trust levels
- Production systems handling sensitive data
- Any scenario requiring audit trails and separation of duties

### Graduating from This Approach

As your organization grows, you should consider:

1. **Migrate to proper IAM hierarchy**: Use folders, fine-grained roles, and service account impersonation
2. **Implement least-privilege access**: Reduce the admin bot's permissions to only what's needed
3. **Use Workload Identity**: For GKE/Cloud Run workloads, avoid long-lived service account keys
4. **Enable audit logging**: Track all actions taken by service accounts
5. **Consider GCP's Organization Policy Service**: Enforce constraints across your organization

### Alternative: Lock Down Permissions

If you want to continue using this tool but reduce risk:

1. Remove the broad Organization Admin role
2. Grant only specific permissions needed for your workflows
3. Use [IAM Conditions](https://cloud.google.com/iam/docs/conditions-overview) to limit when/where the bot can operate
4. Regularly rotate service account keys
5. Monitor admin bot activity closely

## Overview

`pdum_gcp` provides a structured approach to managing GCP resources at scale. The core concept is creating **admin bots** - service accounts with organization-level permissions - that serve as the foundation for all downstream automation.

### Key Features

- 🤖 **Admin Bot Management**: Bootstrap organization-level service accounts with full admin permissions
- 🔧 **Multi-Organization Support**: Manage multiple GCP organizations from a single machine using gcloud configs
- 📦 **Layered Architecture**: Clear separation between bootstrap (CLI-based) and automation (API-based) layers
- 🔒 **Secure Credential Storage**: Local configuration management in `~/.config/gcloud/pdum_gcp/`
- 🔄 **Idempotent Operations**: All commands can be safely re-run without side effects
- 🏢 **Personal & Organization Modes**: Automatic detection and handling of GCP account types

## Personal vs Organization Mode

`pdum_gcp` automatically detects and adapts to two different GCP account types:

### Organization Mode

**When you have a GCP Organization:**
- Admin bots get organization-level permissions (Organization Admin, Billing Admin)
- Projects can be created in folders within the organization hierarchy
- Service accounts can create projects via Python API (with organization as parent)
- Full automation capabilities

**Use Case:** Enterprise accounts, companies, teams with formal GCP organization structure

### Personal Mode

**When you have a personal Gmail/Workspace account without an organization:**
- Admin bots are created but don't get organization-level permissions (no org to attach to)
- Projects are created at root level (no folders available)
- Service accounts cannot create projects (GCP limitation) - uses gcloud CLI with human credentials instead
- Limited automation but still functional for project management

**Use Case:** Individual developers, personal projects, learning/experimentation

### How Mode is Determined

Mode is automatically detected during bootstrap:
- **Organization mode**: If `--org` is provided or an organization is detected
- **Personal mode**: If no organization is found

The mode is saved to `~/.config/gcloud/pdum_gcp/<config>/config.yaml` and used by the Python API to determine the correct approach for operations like project creation.

## Architecture

The framework is designed in distinct layers, each building on the previous:

### Phase 1: Bootstrap Layer (CLI-Based)

The bootstrap phase uses the **gcloud CLI** (not the Python API) to create the foundational admin bot. This is intentional - it leverages your existing human credentials to set up the automation infrastructure.

**Commands:**
- `pdum_gcp bootstrap` - Create a new admin bot for an organization
- `pdum_gcp import` - Import an existing admin bot configuration to a new machine
- `pdum_gcp manage-billing` - Manage billing account access for the admin bot

**What it does:**
1. Creates an admin project (e.g., `h-papadum-admin-abc123`)
2. Links billing account to the project
3. Enables required APIs (Cloud Resource Manager, IAM, Cloud Billing, Service Usage)
4. Creates a service account (`admin-robot@h-papadum-admin-abc123.iam.gserviceaccount.com`)
5. Grants organization-level permissions (Organization Admin, Billing Admin)
6. Grants billing account admin access (for the billing account used in step 2)
7. Saves configuration to `~/.config/gcloud/pdum_gcp/<config>/`
   - `config.yaml` - Admin bot email and trusted humans list
   - `admin.json` - Service account credentials

**Multi-Organization Support:**

Each gcloud config can have its own admin bot. For example:

```bash
# Bootstrap for work organization
pdum_gcp bootstrap --config work

# Bootstrap for personal organization
pdum_gcp bootstrap --config personal

# Import existing config on a new machine
pdum_gcp import --config work
```

This creates separate admin bots:
- `~/.config/gcloud/pdum_gcp/work/` - Work organization admin
- `~/.config/gcloud/pdum_gcp/personal/` - Personal organization admin

### Phase 2: Admin Layer (Python API-Based) [In Progress]

The admin layer uses the **Python GCP API** with admin bot credentials to perform automated operations.

**Current Status:** ✅ Credential loading implemented

**Capabilities:**
- ✅ Load admin credentials from `~/.config/gcloud/pdum_gcp/<config>/`
- ✅ Validate configuration and service account keys
- ✅ List available configurations
- ✅ List billing accounts and get default billing account
- ✅ Create and manage GCP projects programmatically
- ✅ Set up billing, IAM policies, service accounts, and API enabling
- 🚧 Provision infrastructure at scale (coming soon)

**Example:**
```python
from pdum.gcp import admin

# Load admin bot credentials for a specific config
creds = admin.load_admin_credentials(config="work")

# Access credential properties
print(f"Admin bot: {creds.admin_bot_email}")
print(f"Project: {creds.project_id}")
print(f"Trusted humans: {creds.trusted_humans}")

# List billing accounts
billing_accounts = creds.list_billing_accounts()
for account in billing_accounts:
    print(f"{account.display_name}: {account.account_id} (open={account.open})")

# Get default billing account (when there's exactly one open account)
try:
    default_account = creds.get_default_billing_account()
    print(f"Using billing account: {default_account.display_name} ({default_account.account_id})")
except admin.AdminCredentialsError as e:
    print(f"Cannot use default: {e}")
    # Handle multiple accounts or no accounts

# Create a new GCP project with all the bells and whistles
project = creds.create_project(
    project_id="my-ml-project-12345",
    display_name="My ML Project",
    # billing_account_id is optional - uses default if not specified
    # enable_apis is optional - defaults to ML-focused APIs
)
print(f"Created project: {project.project_id}")
print(f"Project state: {project.state}")
print(f"Labels: {project.labels}")

# Create a project with specific billing and custom APIs
project = creds.create_project(
    project_id="my-custom-project",
    display_name="Custom Project",
    billing_account_id="016EF2-C9E743-5BA3D3",
    enable_apis=[
        "firestore.googleapis.com",
        "compute.googleapis.com",
        "storage-api.googleapis.com",
    ]
)

# Use the Google Cloud credentials with any GCP client library
from google.cloud import resourcemanager_v3

client = resourcemanager_v3.ProjectsClient(credentials=creds.google_cloud_credentials)
# Now you can use the client with admin bot permissions

# List all available configurations
configs = admin.list_available_configs()
print(f"Available configs: {configs}")
```

**Creating Projects with `create_project()`:**

The `create_project()` method provides a complete project setup in a single call:

```python
project = creds.create_project(
    project_id="my-ml-project-12345",       # Required: globally unique project ID
    display_name="My ML Project",           # Optional: defaults to project_id
    billing_account_id="016EF2-...",        # Optional: defaults to get_default_billing_account()
    enable_apis=["firestore.googleapis.com"]  # Optional: defaults to ML APIs
)
```

**What it does:**
1. Creates the project with label `managed-by: pdum_gcp`
2. Links the billing account
3. Creates `admin-robot@{project_id}.iam.gserviceaccount.com` service account
4. Grants owner role to admin-robot and all trusted humans
5. Enables specified APIs (or ML defaults)

**Default ML APIs:**
- `firestore.googleapis.com` - Firestore
- `aiplatform.googleapis.com` - Vertex AI / Gemini
- `container.googleapis.com` - GKE
- `storage-api.googleapis.com` - Cloud Storage
- `storage-component.googleapis.com` - Cloud Storage Component
- `bigtable.googleapis.com` - BigTable
- `bigtableadmin.googleapis.com` - BigTable Admin

**Idempotency:**
The method is fully idempotent - you can re-run it safely:
- If project exists: updates labels and continues
- If billing already linked: skips
- If service account exists: skips creation
- If IAM roles exist: skips
- If APIs enabled: skips

**Error Handling:**

The `load_admin_credentials()` function provides helpful error messages if credentials are missing:

```python
try:
    creds = admin.load_admin_credentials("work")
except admin.AdminCredentialsError as e:
    print(e)
    # Error message will tell you whether to run:
    # - pdum_gcp bootstrap --config work
    # - pdum_gcp import --config work
```

### Phase 3: Downstream Layers [Future]

Additional layers will build on top of the admin layer:
- Resource provisioning templates
- Multi-project orchestration
- Cost management and monitoring
- Security policy enforcement

## Installation

Install using pip:

```bash
pip install habemus-papadum-gcp
```

Or using uv:

```bash
uv pip install habemus-papadum-gcp
```

## Quick Start

### 1. Bootstrap Your First Admin Bot

```bash
# Interactive mode - prompts for all options
pdum_gcp bootstrap

# Or specify options explicitly
pdum_gcp bootstrap --config work --billing 0X0X0X-0X0X0X-0X0X0X --org 123456789
```

This will:
- ✅ Create an admin project in your organization
- ✅ Create the admin service account
- ✅ Grant org-level permissions
- ✅ Save configuration locally
- ✅ Download service account key

### 2. Import on Additional Machines

Once you've bootstrapped on one machine, use `import` on other machines:

```bash
pdum_gcp import --config work
```

This will:
- ✅ Find the existing admin project
- ✅ Locate the admin service account
- ✅ Download credentials locally
- ✅ Set up the same configuration

### 3. Verify Configuration

Check your configuration:

```bash
ls -la ~/.config/gcloud/pdum_gcp/work/
# config.yaml - Contains admin bot email and trusted humans
# admin.json  - Service account credentials
```

## CLI Reference

### `pdum_gcp bootstrap`

Create a new admin bot for an organization.

**Options:**
- `--config, -c` - Gcloud configuration name (interactive if not provided)
- `--billing, -b` - Billing account ID (interactive if not provided)
- `--org, -o` - Organization ID (interactive if not provided)
- `--dry-run, -n` - Show what would be done without making changes
- `--verbose, -v` - Print all gcloud commands

**Examples:**
```bash
# Interactive mode
pdum_gcp bootstrap

# Dry run to preview
pdum_gcp bootstrap --dry-run

# Specify all options
pdum_gcp bootstrap --config work --billing 0X0X0X --org 123456789

# Verbose mode for debugging
pdum_gcp bootstrap --verbose
```

### `pdum_gcp import`

Import an existing admin bot configuration to this machine.

**Options:**
- `--config, -c` - Gcloud configuration name (interactive if not provided)
- `--verbose, -v` - Print all gcloud commands

**Examples:**
```bash
# Interactive mode
pdum_gcp import

# Specify config
pdum_gcp import --config work
```

### `pdum_gcp manage-billing`

Manage billing account access for the admin bot.

This command allows you to grant the admin bot access to additional billing accounts using an interactive multi-select interface. The bootstrap command automatically grants access to the billing account used during setup, but you may want to give the admin bot access to other billing accounts as well.

**Why this is needed:** Billing accounts have their own IAM policies separate from organization-level permissions. Even if the admin bot has organization-level billing admin role, it needs explicit access to each billing account to list and manage them via the Python API.

**Options:**
- `--config, -c` - Gcloud configuration name (interactive if not provided)
- `--verbose, -v` - Print all gcloud commands

**Examples:**
```bash
# Interactive mode (shows current access status and multi-select interface)
pdum_gcp manage-billing

# Specify config
pdum_gcp manage-billing --config work

# Verbose mode for debugging
pdum_gcp manage-billing --verbose
```

**What it does:**
1. Displays current billing account access status
2. Shows which billing accounts the admin bot can already access
3. Presents a multi-select interface for billing accounts without access
4. Grants billing admin role for selected accounts

### `pdum_gcp version`

Show the version of pdum_gcp.

```bash
pdum_gcp version
```

## Configuration Structure

Each gcloud config has its own directory under `~/.config/gcloud/pdum_gcp/`:

```
~/.config/gcloud/pdum_gcp/
├── work/
│   ├── config.yaml       # Admin bot email, trusted humans
│   └── admin.json        # Service account credentials (keep secure!)
└── personal/
    ├── config.yaml
    └── admin.json
```

### config.yaml Format

```yaml
mode: personal  # or "organization"
admin_bot: admin-robot@h-papadum-admin-abc123.iam.gserviceaccount.com
trusted_humans:
  - user@example.com
```

### admin.json Format

Standard GCP service account JSON key file. **Keep this secure!** It grants full admin access to your organization.

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
