"""Guard against inadvertently shipping a mismatched prerelease."""
import pytest

from scripts.verify_release_version import validate


def test_alpha_release_tag():
    assert validate("v0.2.0-alpha.5") == "0.2.0a5"


@pytest.mark.parametrize("bad", [
    "v0.2.0", "v0.2.0-beta.1", "v9.1.0-alpha.1",
    "v0.2.0-alpha.2", "0.2.0-alpha.1", "not-a-tag",
])
def test_reject_incorrect_release_tag(bad):
    with pytest.raises(ValueError):
        validate(bad)
