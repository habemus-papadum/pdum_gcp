# Interactive Admin Tutorial

This walkthrough shows how to use the read-only and low-risk administration helpers in `pdum.gcp`. The snippets were executed with Application Default Credentials (ADC) and the outputs were manually sanitized so that organization names, project IDs, and email addresses are replaced with fictitious placeholders such as `acme-research`, `org-123456789`, or `user@example.com`.

> ⚠️ **Dangerous territory:** These tools assume you already have broad administrator access across multiple Google Cloud organizations. They are great for rapid exploration and teardown in tiny, high-trust circles. They are a terrible fit for larger companies or low-trust environments.

## Prerequisites

- Application Default Credentials are configured (`gcloud auth application-default login`).
- The identity behind those credentials has the necessary organization- and project-level permissions.
- Mutating helpers (project creation, IAM changes, API enablement, etc.) are intentionally **out of scope** for this tutorial. Stick to the read-heavy snippets unless you are absolutely certain about the impact.

---

## Step 1 – Run `doctor()`

`doctor()` performs a preflight check: it confirms your active identity, reports the quota project, compares enabled APIs against the package’s required baseline, and inspects organization-level role coverage.

```python
from pdum.gcp.admin import doctor

doctor()
```

```text
# Output (sanitized sample)
╭─ Identity ───────────────────────────────────────────╮
│ Active identity: user@example.com                    │
╰──────────────────────────────────────────────────────╯
╭─ Quota Project ──────────────────────────────────────╮
│ Quota project: acme-research                         │
╰──────────────────────────────────────────────────────╯
╭─ APIs ───────────────────────────────────────────────╮
│ Status   Service                                      │
│ OK       cloudbilling.googleapis.com                  │
│ OK       cloudresourcemanager.googleapis.com          │
│ Missing  serviceusage.googleapis.com                  │
╰──────────────────────────────────────────────────────╯
╭─ Grant Missing Roles ────────────────────────────────╮
│ gcloud organizations add-iam-policy-binding 123456789│
│   --member="user:user@example.com"                   │
│   --role="roles/resourcemanager.projectCreator"      │
╰──────────────────────────────────────────────────────╯
```

Take action on any missing APIs or roles before continuing.

---

## Step 2 – “Just Go” Quick Survey

Once the environment is healthy, run a minimal survey to understand the landscape you can touch.

```python
from pdum.gcp import get_email, list_organizations, quota_project, walk_projects

email = get_email()
orgs = list_organizations()
qp = quota_project()
projects = list(walk_projects(active_only=True))

print("Identity:", email)
print("Containers:", [f"{o.display_name} ({o.resource_name})" for o in orgs])
print("Quota project:", qp.id, qp.lifecycle_state)
print("First three projects:", [p.id for p in projects[:3]])
```

```text
# Output (sanitized sample)
Identity: user@example.com
Containers: ['Acme Research (organizations/123456789)', 'No Organization (NO_ORG)']
Quota project: acme-research ACTIVE
First three projects: ['acme-sandbox-001', 'acme-data-lab', 'personal-scratchpad']
```

### Explore containers interactively

```python
target = next(o for o in orgs if o.display_name == "Acme Research")

print("Folders:", [f.display_name for f in target.folders()])
print("Projects:", [p.id for p in target.projects()])

target.tree()
```

```text
# Output (sanitized sample)
Folders: ['Platform', 'Experiments']
Projects: ['acme-research-admin']
🌺 Acme Research (organizations/123456789)
├── 🎸 Platform (folders/444444444444)
│   └── 🎵 platform-admin (ACTIVE)
└── 🎸 Experiments (folders/555555555555)
    ├── 🎵 acme-lab-001 (ACTIVE)
    └── 🎵 acme-lab-archived (DELETE_REQUESTED)
```

### Navigate folders explicitly

```python
from pdum.gcp.types import Folder

platform = next(f for f in target.folders() if f.display_name == "Platform")
experiments = target.cd("Experiments")

print("Platform parent:", platform.parent_resource_name)
print("Experiments projects:", [p.id for p in experiments.projects()])
```

```text
# Output (sanitized sample)
Platform parent: organizations/123456789
Experiments projects: ['acme-lab-001', 'acme-lab-archived']
```

### Inspect IAM roles you personally hold

```python
roles = target.list_roles(user_email=email)
print("Roles on organization:", [r.name for r in roles])
```

```text
# Output (sanitized sample)
Roles on organization: [
    'roles/resourcemanager.organizationAdmin',
    'roles/iam.securityAdmin',
    'roles/billing.user'
]
```

### Check quota project APIs

```python
enabled = qp.enabled_apis()
print(f"{qp.id} has {len(enabled)} APIs enabled.")
print("Sample:", sorted(enabled)[:5])
```

```text
# Output (sanitized sample)
acme-research has 37 APIs enabled.
Sample: [
    'bigquery.googleapis.com',
    'cloudbilling.googleapis.com',
    'cloudresourcemanager.googleapis.com',
    'iam.googleapis.com',
    'serviceusage.googleapis.com'
]
```

### Resolve human-friendly API names

```python
from pdum.gcp import lookup_api

print("Compute:", lookup_api("Compute Engine"))
print("Billing:", lookup_api("Cloud Billing API"))
```

```text
# Output (sanitized sample)
Compute: compute.googleapis.com
Billing: cloudbilling.googleapis.com
```

### Peek at billing accounts

```python
billing_accounts = target.billing_accounts(open_only=True)
for account in billing_accounts:
    print(account.display_name, account.id, account.status)
```

```text
# Output (sanitized sample)
Acme Master Billing 000000-111111-222222 OPEN
Acme Sandbox Billing 333333-444444-555555 OPEN
```

### Look up resources by ID

```python
from pdum.gcp.types import Organization, Project

org_lookup = Organization.lookup("123456789")
project_lookup = Project.lookup("acme-research-admin")

print("Organization display name:", org_lookup.display_name)
print("Project parent:", project_lookup.parent.resource_name)
```

```text
# Output (sanitized sample)
Organization display name: Acme Research
Project parent: organizations/123456789
```

---

## Mutation Syntax Reference (Do Not Run Here)

The snippets below show the APIs for write operations. They are intentionally **not** executed in this tutorial. Review credentials, confirm the target resources, and double-check prerequisites before running them in your own session.

Most helpers grab credentials from the resource itself or fall back to Application Default Credentials automatically. If you ever need an explicit override, the pattern is:

```python
from google.auth import default

creds, _ = default()
```

### Create a Folder

```python
new_folder = target.create_folder(
    "Research Staging",
)
```

### Create a Project

```python
from pdum.gcp.types import NO_BILLING_ACCOUNT, Project

project_id = Project.suggest_name(prefix="acme-research")
# Use the first billing account visible to the organization; fall back to NO_BILLING_ACCOUNT if none.
billing_account = next(iter(target.billing_accounts()), NO_BILLING_ACCOUNT)

created = target.create_project(
    project_id,
    "Acme Research Sandbox",
    billing_account=billing_account,
    timeout=600.0,
    polling_interval=5.0,
)
```

### Update Project Billing

```python
# Reuse an existing billing account from the parent organization
new_billing_account = next(iter(target.billing_accounts(open_only=True)), None)
if new_billing_account:
    created.update_billing_account(new_billing_account)

# Or by ID without a Project instance
Project.update_billing_account_for_id(
    project_id,
    "000000-111111-222222",
)
```

### Grant Owners on a Project

```python
project = Project.lookup(project_id)
project.add_user_as_owner("trusted-human@example.com")
```

### Grant Org-Level Owner Roles

```python
target.add_user_as_owner("trusted-human@example.com")

# Fine-grained control:
target.add_user_roles(
    "trusted-human@example.com",
    roles_to_add=[
        "roles/resourcemanager.organizationAdmin",
        "roles/billing.admin",
    ],
)
```

### Enable APIs on a Project

```python
services = [
    lookup_api("Compute Engine API"),
    lookup_api("Cloud Resource Manager API"),
]
project.enable_apis(
    services,
    timeout=300.0,
    verbose=True,
    polling_interval=5.0,
)
```

---

## Where to Go Next

- Need a refresher on every public class and helper? See the [API Reference](reference.md).
- Thinking about mutations (project creation, IAM changes)? Re-read the warnings, audit your permissions, and script cautiously.
- If anything in this tutorial drifts out of date, follow the [tutorial rebuild guide](tutorial_rebuild.md) to regenerate fresh snippets with anonymized outputs.
