"""Backend LLM partagé par la découverte des Event types et l'extraction des Events (#117).

Aucun test ne touche le réseau : FakeBackend renvoie des réponses écrites d'avance et compte
les appels ; l'adaptateur Anthropic reçoit un faux client SDK.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from guess_arc.events.llm import (
    AnthropicBackend,
    FakeBackend,
    LlmClient,
    LlmRequest,
    StructuredOutputError,
    backend_from_config,
)

SCHEMA = {
    "type": "object",
    "properties": {"events": {"type": "array", "items": {"type": "string"}}},
    "required": ["events"],
    "additionalProperties": False,
}


def request(**overrides) -> LlmRequest:
    fields = dict(
        prompt="Scene 1: Luffy punches Arlong.",
        schema=SCHEMA,
        prompt_version="extraction-v1",
        taxonomy_version="v1",
        chapter=93,
    )
    fields.update(overrides)
    return LlmRequest(**fields)


def test_call_returns_the_backend_structured_output(tmp_path):
    backend = FakeBackend({"events": ["fight"]})
    client = LlmClient(backend, cache_dir=tmp_path)

    assert client.call(request()) == {"events": ["fight"]}


@pytest.mark.parametrize("bad_output", [
    {"events": "fight"},                      # mauvais type
    {"events": ["fight"], "extra": 1},        # champ hors schéma
    {},                                       # champ requis absent
    "not json at all",                        # pas du JSON
])
def test_output_that_does_not_match_the_schema_is_an_error(tmp_path, bad_output):
    client = LlmClient(FakeBackend(bad_output), cache_dir=tmp_path)

    with pytest.raises(StructuredOutputError, match="chapitre 93"):
        client.call(request())


def test_rerunning_the_same_call_is_served_from_the_cache(tmp_path):
    backend = FakeBackend({"events": ["fight"]})

    first = LlmClient(backend, cache_dir=tmp_path).call(request())
    # Un nouveau client sur le même dossier : un second run du pipeline.
    second = LlmClient(backend, cache_dir=tmp_path).call(request())

    assert first == second == {"events": ["fight"]}
    assert backend.calls == 1


@pytest.mark.parametrize("change", [
    {"model": "fake:other-model"},
    {"prompt_version": "extraction-v2"},
    {"taxonomy_version": "v2"},
    {"chapter": 94},
])
def test_changing_any_cache_key_part_causes_a_fresh_call(tmp_path, change):
    first = FakeBackend({"events": ["fight"]})
    LlmClient(first, cache_dir=tmp_path).call(request())

    second = FakeBackend({"events": ["alliance"]}, model=change.pop("model", first.model))
    output = LlmClient(second, cache_dir=tmp_path).call(request(**change))

    assert second.calls == 1
    assert output == {"events": ["alliance"]}


def test_an_invalid_response_is_not_cached(tmp_path):
    with pytest.raises(StructuredOutputError):
        LlmClient(FakeBackend({}), cache_dir=tmp_path).call(request())

    backend = FakeBackend({"events": ["fight"]})
    assert LlmClient(backend, cache_dir=tmp_path).call(request()) == {"events": ["fight"]}
    assert backend.calls == 1


@pytest.mark.parametrize("unsafe", [
    {"prompt_version": "../escape"},
    {"taxonomy_version": "v1/../../x"},
    {"prompt_version": ""},
])
def test_cache_key_parts_must_be_safe_folder_names(tmp_path, unsafe):
    with pytest.raises(ValueError, match="clé du cache"):
        LlmClient(FakeBackend({"events": []}), cache_dir=tmp_path).call(request(**unsafe))


def write_config(tmp_path, **models):
    path = tmp_path / "events.json"
    path.write_text(json.dumps(models), encoding="utf-8")
    return path


def test_switching_model_is_a_config_change_only(tmp_path):
    config = write_config(tmp_path, extraction_model="anthropic:claude-opus-5-5")
    assert backend_from_config("extraction", config).model == "anthropic:claude-opus-5-5"

    config = write_config(tmp_path, extraction_model="anthropic:claude-sonnet-5-5")
    backend = backend_from_config("extraction", config)

    assert isinstance(backend, AnthropicBackend)
    assert backend.model == "anthropic:claude-sonnet-5-5"


def test_each_task_reads_its_own_model(tmp_path):
    config = write_config(tmp_path, discovery_model="anthropic:claude-opus-5-5",
                          extraction_model="anthropic:claude-haiku-5-5")

    assert backend_from_config("discovery", config).model == "anthropic:claude-opus-5-5"
    assert backend_from_config("extraction", config).model == "anthropic:claude-haiku-5-5"


def test_an_unknown_provider_is_reported_with_the_known_ones(tmp_path):
    config = write_config(tmp_path, extraction_model="nowhere:some-model")

    with pytest.raises(ValueError, match="nowhere.*anthropic"):
        backend_from_config("extraction", config)


def test_an_empty_model_is_reported_with_where_to_set_it(tmp_path):
    config = write_config(tmp_path, extraction_model="")

    with pytest.raises(ValueError, match=r"extraction_model est vide.*events\.json"):
        backend_from_config("extraction", config)


def test_the_committed_config_leaves_the_extraction_model_to_choose():
    assert backend_from_config("discovery").model.startswith("anthropic:")
    # Pas de défaut : le modèle d'extraction se choisit sur l'échantillon de validation (#114).
    with pytest.raises(ValueError, match="extraction_model est vide"):
        backend_from_config("extraction")


class FakeAnthropicSdk:
    """Imite `anthropic.Anthropic().messages.create` : garde les arguments, renvoie un message."""

    def __init__(self, text='{"events": ["fight"]}', stop_reason="end_turn"):
        self.requests = []
        self._message = SimpleNamespace(
            stop_reason=stop_reason,
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        )
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return self._message


def test_anthropic_backend_asks_for_schema_constrained_json(tmp_path):
    sdk = FakeAnthropicSdk()
    client = LlmClient(AnthropicBackend("claude-opus-5-5", client=sdk), cache_dir=tmp_path)

    assert client.call(request()) == {"events": ["fight"]}

    [sent] = sdk.requests
    assert sent["model"] == "claude-opus-5-5"
    assert sent["messages"] == [{"role": "user", "content": "Scene 1: Luffy punches Arlong."}]
    assert sent["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    # L'API Anthropic actuelle refuse les paramètres d'échantillonnage (400) : rien n'est envoyé.
    assert "temperature" not in sent


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_an_unfinished_anthropic_answer_is_an_error(tmp_path, stop_reason):
    sdk = FakeAnthropicSdk(text='{"events": [', stop_reason=stop_reason)
    client = LlmClient(AnthropicBackend("claude-opus-5-5", client=sdk), cache_dir=tmp_path)

    with pytest.raises(StructuredOutputError, match=f"chapitre 93.*{stop_reason}"):
        client.call(request())


def test_an_anthropic_answer_without_text_is_an_error(tmp_path):
    sdk = FakeAnthropicSdk()
    sdk._message.content = [SimpleNamespace(type="thinking", thinking="")]
    client = LlmClient(AnthropicBackend("claude-opus-5-5", client=sdk), cache_dir=tmp_path)

    with pytest.raises(StructuredOutputError, match="aucun bloc de texte"):
        client.call(request())


@pytest.mark.parametrize("change", [
    {"prompt": "Scene 1: Luffy and Nami ally against Arlong."},
    {"schema": {**SCHEMA, "required": []}},
])
def test_a_cached_answer_for_another_prompt_or_schema_is_refused(tmp_path, change):
    LlmClient(FakeBackend({"events": ["fight"]}), cache_dir=tmp_path).call(request())
    # Prompt ou schéma modifié sans changer la version du prompt : l'ancienne réponse ne doit pas
    # être servie, et on ne paie pas non plus un nouvel appel en silence.
    backend = FakeBackend({"events": ["alliance"]})

    with pytest.raises(StructuredOutputError, match="ne correspond pas.*version du prompt"):
        LlmClient(backend, cache_dir=tmp_path).call(request(**change))
    assert backend.calls == 0


def test_an_unknown_task_is_reported(tmp_path):
    config = write_config(tmp_path, extraction_model="anthropic:claude-opus-5-5")

    with pytest.raises(ValueError, match="extrction_model"):
        backend_from_config("extrction", config)
