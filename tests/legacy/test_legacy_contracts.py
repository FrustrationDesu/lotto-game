import pytest

pytestmark = pytest.mark.skip(reason="legacy contract tests; kept temporarily during API contract migration")


def test_legacy_games_endpoints_contract() -> None:
    """Legacy contract placeholder: /games/{id}/line, /games/{id}/card, /games/{id}/players."""


def test_legacy_transcribe_contract() -> None:
    """Legacy contract placeholder: /speech/transcribe endpoint."""
