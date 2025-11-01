import json
from pathlib import Path

import google.cloud.firestore as firestore
from fire_prox import FireProx


def load_firebase_project(environment: str = "default") -> str:
    """Load the Firebase project ID from .firebaserc file.

    Args:
        environment: The environment name to load (defaults to "default")

    Returns:
        The project ID for the specified environment

    Raises:
        FileNotFoundError: If .firebaserc file is not found
        KeyError: If the specified environment is not found in .firebaserc
    """
    firebaserc_path = Path(__file__).parent / ".firebaserc"

    with open(firebaserc_path, "r") as f:
        config = json.load(f)

    return config["projects"][environment]


def firebase_client(database: str = "(default)") -> firestore.Client:
    return firestore.Client(project=load_firebase_project(), database=database)


def main():
    print("Hello from example!")
    print("Firebase project ID:", load_firebase_project())
    db1 = FireProx(firebase_client())
    db2 = FireProx(firebase_client(database="database2"))

    def create_user(db, name: str, year: int):
        user = db.collection("users").new()
        user.name = name
        user.year = year
        user.save()
        print(f"Created user: {name}, Year: {year}")

    create_user(db1, "Alice", 2021)
    create_user(db2, "Bob", 2022)


if __name__ == "__main__":
    main()
