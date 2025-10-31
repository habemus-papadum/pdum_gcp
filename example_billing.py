#!/usr/bin/env python3
"""Example script demonstrating billing account retrieval.

This script shows how to retrieve billing information for GCP projects.

Usage:
    python example_billing.py

Note: This requires the Cloud Billing API to be enabled and appropriate permissions.
"""

from pdum.gcp import list_organizations


def main():
    """Check billing accounts for all projects."""
    print("Fetching organizations and their projects...\n")

    organizations = list_organizations()

    for org in organizations:
        print(f"\n{'='*70}")
        print(f"{org.display_name} ({org.resource_name})")
        print('='*70)

        projects = org.projects()

        for project in projects:
            print(f"\n  Project: {project.id}")
            print(f"  Name: {project.name}")
            print(f"  State: {project.lifecycle_state}")

            # Get billing information
            billing = project.billing_account()

            if billing:
                print(f"  💰 Billing: {billing.display_name} ({billing.id})")
            else:
                print("  ⚠️  Billing: No billing account (billing disabled)")

        print()


if __name__ == "__main__":
    main()
