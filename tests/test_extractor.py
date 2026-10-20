import json
from pathlib import Path

from radlabel.labelling.extractor import SCHEMA, extract, parse
from radlabel.labels import LABELS
from radlabel.llm import FakeLLM
from radlabel.preprocess.sentences import report_sentences


def answer(**over: tuple[str, list[str]]) -> str:
    d = {lab: {"status": "not_mentioned", "evidence": []} for lab in LABELS}
    for k, (st, ev) in over.items():
        d[k.replace("_", " ")] = {"status": st, "evidence": ev}
    return json.dumps(d)


def test_schema_requires_every_label() -> None:
    assert SCHEMA["required"] == LABELS and SCHEMA["additionalProperties"] is False


def test_parse_valid_and_invalid() -> None:
    r = parse("1", answer(Cardiomegaly=("present", ["F1"])))
    assert r is not None and r.status("Cardiomegaly") == "present" and r.tier == 1
    assert parse("1", "not json") is None
    assert parse("1", json.dumps({"Cardiomegaly": {"status": "present", "evidence": []}})) is None  # missing labels
    bad = json.loads(answer())
    bad["Edema"]["status"] = "maybe"
    assert parse("1", json.dumps(bad)) is None


def test_extract_with_fake_llm_is_cached(tmp_path: Path) -> None:
    llm = FakeLLM(lambda m: answer(Cardiomegaly=("present", ["F1"])), tmp_path)
    s = report_sentences("Mild cardiomegaly.", "No acute disease.")
    a, r1 = extract(llm, "7", s)
    b, r2 = extract(llm, "7", s)
    assert a == b and a is not None and a.status("Cardiomegaly") == "present"
    assert (r1.cached, r2.cached, llm.calls) == (False, True, 1)


def test_tier1_prompt_frozen_and_model_locked() -> None:
    """Frozen after the M4 pilot (owner): a new prompt needs a separate dev slice that is never a test fold."""
    import hashlib
    from pathlib import Path

    from radlabel.config import Settings
    from radlabel.labelling.extractor import SYSTEM, TIER1_DEPLOYMENT

    frozen = "ed1ed19a3791b574f7895e8c01c009d00a46793e2f8a5b2fab7a045459f6c23b"
    assert hashlib.sha256((SYSTEM + json.dumps(SCHEMA, sort_keys=True)).encode()).hexdigest() == frozen
    example = Settings(_env_file=Path(__file__).resolve().parents[1] / ".env.example")  # type: ignore[call-arg]
    assert TIER1_DEPLOYMENT == example.azure_openai_deployment == "gpt-4.1-mini"
