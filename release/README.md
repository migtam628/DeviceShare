# GitHub Actions release workflow

DeviceShare releases are built and published **inside GitHub Actions**. No local tagging, packaging, or installer uploading is necessary.

1. Merge the next version's source, packaging versions, tests and documentation into `main`.
2. Update `release/RELEASE_NOTES.md` with the matching release's accurate features and known limitations.
3. Change `release/REQUEST.txt` to the matching tag (for example, `v0.2.0-alpha.7`) and commit that file to `main` **last**. This commit triggers `.github/workflows/release.yml`.
4. The workflow validates the tag against `pyproject.toml`, runs unit tests, packages macOS/Windows/Linux installers, checks the manifest, generates SHA-256 hashes, and publishes the prerelease. GitHub CLI creates the missing git tag at the validated workflow commit.
5. Review the GitHub Release asset list and six cross-platform tests. The workflow never installs a package on customer machines or claims physical print verification.

The workflow also supports manual **Actions → Build GitHub Release → Run workflow** with an explicit release tag, and traditional tag pushes. A release that already exists is not overwritten.

Important: the request file is a release trigger, not a place for credentials or configuration secrets. Each new version must still update platform package versions and real-world acceptance evidence before shipping.
