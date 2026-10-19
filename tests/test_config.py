from pathlib import Path

import pytest

from radlabel.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def example_keys() -> set[str]:
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    return {ln.split("=", 1)[0].strip() for ln in lines if "=" in ln and not ln.lstrip().startswith("#")}


def test_config_matches_env_example() -> None:
    fields = {f.upper() for f in Settings.model_fields}
    assert example_keys() == fields


def test_example_loads_and_offline_fails_fast() -> None:
    s = Settings(_env_file=ROOT / ".env.example")  # type: ignore[call-arg]
    assert s.llm_provider == "azure"
    assert s.pilot_list == ["gpt-4.1-mini", "gpt-5.4-mini", "gpt-5.4-nano"]
    assert "AZURE_OPENAI_API_KEY" in s.missing_llm_settings()
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        s.require_llm()
