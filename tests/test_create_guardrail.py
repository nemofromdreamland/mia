"""Offline tests for scripts/create_guardrail.py (fake Bedrock client, no network)."""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_guardrail.py"
spec = importlib.util.spec_from_file_location("create_guardrail", SCRIPT)
assert spec and spec.loader
cg = importlib.util.module_from_spec(spec)
sys.modules["create_guardrail"] = cg
spec.loader.exec_module(cg)


class FakeBedrock:
    """Records calls; `existing` is what list_guardrails returns."""

    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing or []
        self.calls: list[str] = []

    def list_guardrails(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("list_guardrails")
        return {"guardrails": self.existing}

    def create_guardrail(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("create_guardrail")
        return {"guardrailId": "new123"}

    def create_guardrail_version(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append("create_guardrail_version")
        return {"version": "1"}


def test_request_has_prompt_attack_high_on_input() -> None:
    filters = cg.guardrail_request()["contentPolicyConfig"]["filtersConfig"]
    attack = next(f for f in filters if f["type"] == "PROMPT_ATTACK")
    assert attack["inputStrength"] == "HIGH"
    assert attack["outputStrength"] == "NONE"


def test_request_denies_off_topic_on_input_and_output() -> None:
    topics = cg.guardrail_request()["topicPolicyConfig"]["topicsConfig"]
    topic = next(t for t in topics if t["name"] == "fora_da_entrevista")
    assert topic["type"] == "DENY"
    assert topic["inputEnabled"] and topic["outputEnabled"]
    assert len(topic["definition"]) <= 200
    assert all(len(e) <= 100 for e in topic["examples"])


def test_request_pii_and_cpf_regex() -> None:
    pii = cg.guardrail_request()["sensitiveInformationPolicyConfig"]
    actions = {e["type"]: e["action"] for e in pii["piiEntitiesConfig"]}
    for kind in ("EMAIL", "PHONE", "NAME", "ADDRESS"):
        assert actions[kind] == "ANONYMIZE"
    for kind in ("CREDIT_DEBIT_CARD_NUMBER", "PASSWORD"):
        assert actions[kind] == "BLOCK"
    cpf = pii["regexesConfig"][0]
    assert cpf["action"] == "ANONYMIZE"
    import re

    assert re.search(cpf["pattern"], "meu cpf é 123.456.789-09")


def test_request_word_markers_and_messages() -> None:
    request = cg.guardrail_request()
    words = {w["text"] for w in request["wordPolicyConfig"]["wordsConfig"]}
    assert {"ignore previous instructions", "system prompt"} <= words
    assert request["name"] == cg.GUARDRAIL_NAME == "mia-robustness"
    assert "foco na entrevista" in request["blockedInputMessaging"]
    assert "foco na entrevista" in request["blockedOutputsMessaging"]


def test_ensure_creates_guardrail_and_version() -> None:
    client = FakeBedrock()
    assert cg.ensure_guardrail(client) == ("new123", "1")
    assert client.calls == ["list_guardrails", "create_guardrail", "create_guardrail_version"]


def test_ensure_reuses_existing_by_name() -> None:
    client = FakeBedrock([{"id": "old9", "name": "mia-robustness", "version": "DRAFT"}])
    assert cg.ensure_guardrail(client) == ("old9", "1")
    assert "create_guardrail" not in client.calls


def test_main_aborts_without_confirmation(tmp_path: Path) -> None:
    out = tmp_path / "guardrails.yaml"
    client = FakeBedrock()
    code = cg.main(["--output", str(out)], client=client, ask=lambda _: "n")
    assert code == 1
    assert client.calls == []
    assert not out.exists()


def test_main_writes_config_after_confirmation(tmp_path: Path) -> None:
    out = tmp_path / "guardrails.yaml"
    code = cg.main(["--output", str(out)], client=FakeBedrock(), ask=lambda _: "s")
    assert code == 0
    saved = yaml.safe_load(out.read_text(encoding="utf-8"))["robustness"]
    assert saved["id"] == "new123" and saved["version"] == "1" and saved["created"]
