"""Ensure a GitHub prerelease tag matches pyproject.toml and the app."""
import argparse
import re
import tomllib
from pathlib import Path


def validate(tag: str) -> str:
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)-alpha\.(\d+)", tag)
    if not match:
        raise ValueError("Only version tags like v0.2.0-alpha.1 are supported in alpha")
    major, minor, patch, iteration = match.groups()
    expected = f"{major}.{minor}.{patch}a{iteration}"
    pyproject = tomllib.loads(
        (Path(__file__).resolve().parent.parent / "pyproject.toml").read_text()
    )
    actual = pyproject["project"]["version"]
    if actual != expected:
        raise ValueError(f"Tag {tag} requires version={expected}, got {actual}")
    return expected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tag")
    args = parser.parse_args()
    print("Valid release version:", validate(args.tag))


if __name__ == "__main__":
    main()
