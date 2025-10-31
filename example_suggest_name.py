#!/usr/bin/env python3
"""Example script demonstrating the Project.suggest_name() method.

This script shows various ways to generate GCP project names.

Usage:
    python example_suggest_name.py
"""

from pdum.gcp import Project


def main():
    """Demonstrate different ways to suggest project names."""
    print("=" * 60)
    print("Project Name Suggestions")
    print("=" * 60)

    # Generate with coolname (default)
    print("\n1. Using coolname (no prefix):")
    for i in range(5):
        name = Project.suggest_name()
        print(f"   {i+1}. {name}")

    # Generate with custom prefix
    print("\n2. Using custom prefix 'myapp':")
    for i in range(5):
        name = Project.suggest_name(prefix="myapp")
        print(f"   {i+1}. {name}")

    # Generate with no random digits
    print("\n3. Using prefix without random digits:")
    name = Project.suggest_name(prefix="production", random_digits=0)
    print(f"   {name}")

    # Generate with custom digit count
    print("\n4. Using custom digit count (8 digits):")
    for i in range(3):
        name = Project.suggest_name(prefix="dev", random_digits=8)
        print(f"   {i+1}. {name}")

    # Generate short random suffix
    print("\n5. Using coolname with short suffix (3 digits):")
    for i in range(3):
        name = Project.suggest_name(random_digits=3)
        print(f"   {i+1}. {name}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
