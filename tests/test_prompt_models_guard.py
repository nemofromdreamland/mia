"""Guard: the model each real prompt runs on must be explicit and honest.

Agents create a new prompt version by copying the previous YAML, which silently carried
`model: "gemini:..."` forward after development moved to Claude Haiku on Bedrock (task 1.9).
These tests make that mistake fail instead of depending on memory.
"""

from pathlib import Path

from mia.llm import load_models_config
from mia.prompts import available_versions, load_prompt, resolve_prompt_model

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Versions written before this guard. They were used in experiments, so they are never edited
# (versioning rule); their `model` field is stale and config/models.yaml overrides it.
LEGACY_STALE_MODEL: frozenset[tuple[str, int]] = frozenset(
    {
        ("candidate_summary", 1),
        ("follow_up", 1),
        ("interviewer", 1),
        ("judge", 1),
        ("planner", 1),
        ("planner", 2),
        ("report", 1),
        ("screening", 1),
        ("screening", 2),
        ("screening", 3),
        ("synthetic_candidate", 1),
        ("synthetic_candidate", 2),
        ("synthetic_candidate", 3),
    }
)


def _prompt_names() -> list[str]:
    return sorted(p.name for p in PROMPTS_DIR.iterdir() if p.is_dir())


def test_every_prompt_is_routed_in_models_config() -> None:
    routes = load_models_config().prompt_models
    missing = [name for name in _prompt_names() if name not in routes]
    assert not missing, f"add these prompts to prompt_models in config/models.yaml: {missing}"


def test_no_prompt_runs_on_gemini_by_default() -> None:
    real = load_models_config()
    on_gemini = []
    for name in _prompt_names():
        prompt = load_prompt(name, max(available_versions(name)), models=real)
        if resolve_prompt_model(prompt, real).ref.startswith("gemini:"):
            on_gemini.append(name)
    assert not on_gemini, f"Gemini is only for the provider comparison (task 6.1): {on_gemini}"


def test_latest_synthetic_candidate_declares_the_model_it_runs_on() -> None:
    real = load_models_config()
    name = "synthetic_candidate"
    version = max(available_versions(name))
    prompt = load_prompt(name, version, models=real)
    assert prompt.model == resolve_prompt_model(prompt, real).ref


def test_new_prompt_versions_declare_the_model_they_run_on() -> None:
    real = load_models_config()
    stale = []
    for name in _prompt_names():
        for version in available_versions(name):
            if (name, version) in LEGACY_STALE_MODEL:
                continue
            prompt = load_prompt(name, version, models=real)
            if prompt.model != resolve_prompt_model(prompt, real).ref:
                stale.append(f"{name}/v{version}.yaml")
    assert not stale, (
        f"`model` must equal the route in config/models.yaml, not be copied "
        f"from the previous version: {stale}"
    )
