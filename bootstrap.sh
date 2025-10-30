#!/bin/bash
#
# A script to bootstrap a super-admin service account for GCP automation.
# This script is IDEMPOTENT and self-configuring.
#
# Usage: ./bootstrap_robot.sh <GCLOUD_CONFIG_NAME> <BILLING_ACCOUNT_ID>
#   e.g., ./bootstrap_robot.sh work 0X0X0X-0X0X0X-0X0X0X
#

# --- Configuration ---
# The KEY to store the bot project ID in your gcloud config.
CUSTOM_CONFIG_KEY="bootstrap/bot_project_id"

# The prefix for the bot project ID. MUST start with a letter.
# GCP project IDs must be 6-30 chars, lowercase, digits, hyphens.
BOT_PROJECT_PREFIX="my-org-admin-bots"

# The short name for your new service account.
BOT_SA_NAME="admin-robot"
# ---------------------

# Exit immediately if a command exits with a non-zero status.
set -euo pipefail

# --- Argument Validation ---
if [[ "$#" -ne 2 ]]; then
    echo "Usage: $0 <GCLOUD_CONFIG_NAME> <BILLING_ACCOUNT_ID>"
    echo "  e.g.:  $0 work 0X0X0X-0X0X0X-0X0X0X"
    exit 1
fi

CONFIG_NAME=$1
BILLING_ID=$2
BILLING_ACCOUNT_NAME="billingAccounts/${BILLING_ID}"

# --- State & Cleanup ---
ORIGINAL_CONFIG=$(gcloud config configurations list --filter="IS_ACTIVE:True" --format="value(NAME)")
ORIGINAL_PROJECT=$(gcloud config get-value core/project 2>/dev/null || echo "")

function restore_config {
    echo ""
    echo "--- Cleanup ---"
    echo "Restoring original gcloud config: ${ORIGINAL_CONFIG}"
    gcloud config configurations activate "${ORIGINAL_CONFIG}"
    if [[ -n "$ORIGINAL_PROJECT" ]]; then
        gcloud config set project "${ORIGINAL_PROJECT}"
    fi
    echo "Bootstrap complete."
}
trap restore_config EXIT

# --- Script Start ---
echo "Activating config: ${CONFIG_NAME}"
gcloud config configurations activate "${CONFIG_NAME}"

# --- Variable Setup (NEW LOGIC) ---
echo "--- Step 0: Determine Bot Project ID ---"
# Try to read the project ID from the active config
BOT_PROJECT_ID=$(gcloud config get-value "${CUSTOM_CONFIG_KEY}" 2>/dev/null || echo "")

if [[ -n "$BOT_PROJECT_ID" ]]; then
    echo "Found project ID in config: ${BOT_PROJECT_ID}"
else
    echo "No ID in config. Searching for existing project with prefix '${BOT_PROJECT_PREFIX}-*'"
    # If not in config, search for an existing project with the prefix
    EXISTING_ID=$(gcloud projects list --filter="projectId:${BOT_PROJECT_PREFIX}-*" --limit=1 --format="value(projectId)")

    if [[ -n "$EXISTING_ID" ]]; then
        echo "Found existing project: ${EXISTING_ID}"
        BOT_PROJECT_ID=$EXISTING_ID
    else
        echo "No existing project found. Generating new ID."
        # Generate a new random ID (8 hex chars = 16^8 possibilities)
        RANDOM_HEX=$(openssl rand -hex 4)
        BOT_PROJECT_ID="${BOT_PROJECT_PREFIX}-${RANDOM_HEX}"
        echo "New project ID will be: ${BOT_PROJECT_ID}"
    fi

    # Save whatever we found or generated back to the config
    echo "Saving project ID to config key '${CUSTOM_CONFIG_KEY}'"
    gcloud config set "${CUSTOM_CONFIG_KEY}" "${BOT_PROJECT_ID}"
fi

# Now that BOT_PROJECT_ID is set, define the service account email
SA_EMAIL="${BOT_SA_NAME}@${BOT_PROJECT_ID}.iam.gserviceaccount.com"

# --- Get Organization ID ---
echo "Fetching Organization ID..."
CURRENT_PROJECT=$(gcloud config get-value core/project)
if [[ -z "$CURRENT_PROJECT" ]]; then
    echo "Error: The config '${CONFIG_NAME}' has no active project. Please set one."
    exit 1
fi
ORG_ID=$(gcloud projects get-ancestors "${CURRENT_PROJECT}" --format='value(id)' | tail -n 1)
echo "Found Organization ID: ${ORG_ID}"

# --- 1. Create Bot Project (Idempotent) ---
echo "--- Step 1: Project ---"
if gcloud projects describe "${BOT_PROJECT_ID}" --quiet > /dev/null 2>&1; then
    echo "Project ${BOT_PROJECT_ID} already exists. Skipping creation."
else
    echo "Creating project: ${BOT_PROJECT_ID}..."
    gcloud projects create "${BOT_PROJECT_ID}" \
        --name="[Admin] Service Bots" \
        --organization="${ORG_ID}" \
        --no-activate
    echo "Project created."
fi

# --- 2. Link Billing Account (Idempotent) ---
echo "--- Step 2: Billing ---"
CURRENT_BILLING=$(gcloud billing projects describe "${BOT_PROJECT_ID}" --format="value(billingAccountName)")
IS_ENABLED=$(gcloud billing projects describe "${BOT_PROJECT_ID}" --format="value(billingEnabled)")

if [[ "$CURRENT_BILLING" == "$BILLING_ACCOUNT_NAME" && "$IS_ENABLED" == "True" ]]; then
    echo "Project ${BOT_PROJECT_ID} is already linked to billing account ${BILLING_ID}."
else
    echo "Linking project ${BOT_PROJECT_ID} to billing account ${BILLING_ID}..."
    gcloud billing projects link "${BOT_PROJECT_ID}" --billing-account="${BILLING_ID}"
    echo "Billing account linked."
fi

# --- 3. Create Service Account (Idempotent) ---
echo "--- Step 3: Service Account ---"
if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${BOT_PROJECT_ID}" --quiet > /dev/null 2>&1; then
    echo "Service account ${SA_EMAIL} already exists. Skipping creation."
else
    echo "Creating service account: ${BOT_SA_NAME}..."
    gcloud iam service-accounts create "${BOT_SA_NAME}" \
        --project="${BOT_PROJECT_ID}" \
        --display-name="Organization Admin Robot"
    echo "Service account created."
fi

# --- 4. Grant Superuser IAM Roles (Idempotent) ---
echo "--- Step 4: IAM Permissions (at Organization Level) ---"
echo "WARNING: Granting Organization Administrator and Billing Admin roles."

echo "Granting roles/resourcemanager.organizationAdmin..."
gcloud organizations add-iam-policy-binding "${ORG_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/resourcemanager.organizationAdmin" \
    --condition=None > /dev/null # Suppress noisy output

echo "Granting roles/billing.admin..."
gcloud organizations add-iam-policy-binding "${ORG_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/billing.admin" \
    --condition=None > /dev/null # Suppress noisy output

echo "All roles granted."