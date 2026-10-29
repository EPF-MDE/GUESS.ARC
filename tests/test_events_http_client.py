"""Client LLM HTTP : configuration lue dans le `.env`, requête et lecture de la réponse.

Sans réseau : seules la lecture du `.env`, la requête construite pour chaque
route et la lecture d'une réponse écrite à l'avance sont testées. L'appel réel
au serveur est vérifié à la main par scripts/llm/diagnostic_serveur.py.
"""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from guess_arc.events.http_client import (
    CONTEXT_TOKENS, MAX_TOKENS, SEED, TIMEOUT_S, ConfigError, HttpClient, LLMConfig,
)

SCHEMA = {"type": "object", "properties": {"chapter": {"type": "integer"}},
          "required": ["chapter"], "additionalProperties": False}

ENV = """\
# serveur de l'école
LLM_BASE_URL=https://llm.example.org/
LLM_API_KEY="sk-test"
LLM_MODEL='test-model:26b'
LLM_API=openai
LLM_CHAT_PATH=/api/chat/completions
"""


def config(api="openai", path="/api/chat/completions"):
    return LLMConfig(base_url="https://llm.example.org", api_key="sk-test",
                     model="test-model", api=api, chat_path=path)


class ConfigTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = Path(self.tmp.name) / ".env"

    def test_reads_every_variable_from_the_env_file(self):
        self.env.write_text(ENV, encoding="utf-8")
        cfg = LLMConfig.from_env_file(self.env)
        self.assertEqual(cfg, LLMConfig(base_url="https://llm.example.org", api_key="sk-test",
                                        model="test-model:26b", api="openai",
                                        chat_path="/api/chat/completions"))

    def test_missing_variables_are_all_named(self):
        self.env.write_text("LLM_BASE_URL=https://llm.example.org\nLLM_MODEL=\n",
                            encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            LLMConfig.from_env_file(self.env)
        message = str(ctx.exception)
        for name in ("LLM_API_KEY", "LLM_MODEL", "LLM_API", "LLM_CHAT_PATH"):
            self.assertIn(name, message)
        self.assertNotIn("LLM_BASE_URL", message)

    def test_missing_env_file_is_a_clear_error(self):
        with self.assertRaises(ConfigError) as ctx:
            LLMConfig.from_env_file(self.env)
        self.assertIn(str(self.env), str(ctx.exception))

    def test_unknown_route_is_rejected(self):
        self.env.write_text(ENV.replace("LLM_API=openai", "LLM_API=anthropic"),
                            encoding="utf-8")
        with self.assertRaises(ConfigError) as ctx:
            LLMConfig.from_env_file(self.env)
        self.assertIn("LLM_API", str(ctx.exception))

    @mock.patch.dict(os.environ, {"LLM_MODEL": "from-shell"})
    def test_process_environment_is_ignored(self):
        self.env.write_text(ENV, encoding="utf-8")
        self.assertEqual(LLMConfig.from_env_file(self.env).model, "test-model:26b")


class RequestTest(unittest.TestCase):
    def test_openai_route(self):
        url, headers, payload = HttpClient(config()).request("sys", "usr", SCHEMA)
        self.assertEqual(url, "https://llm.example.org/api/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer sk-test")
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"], [{"role": "system", "content": "sys"},
                                               {"role": "user", "content": "usr"}])
        self.assertEqual(payload["temperature"], 0)
        self.assertEqual(payload["seed"], SEED)
        self.assertEqual(payload["max_tokens"], MAX_TOKENS)
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(payload["response_format"]["json_schema"]["schema"], SCHEMA)
        self.assertGreaterEqual(payload["num_ctx"], 16000)
        self.assertFalse(payload["think"])

    def test_ollama_route(self):
        client = HttpClient(config("ollama", "/ollama/api/chat"))
        url, _, payload = client.request("sys", "usr", SCHEMA)
        self.assertEqual(url, "https://llm.example.org/ollama/api/chat")
        self.assertEqual(payload["format"], SCHEMA)
        self.assertFalse(payload["think"])
        self.assertFalse(payload["stream"])
        self.assertEqual(payload["options"], {"temperature": 0, "seed": SEED,
                                              "num_ctx": CONTEXT_TOKENS,
                                              "num_predict": MAX_TOKENS})

    def test_fixed_parameters(self):
        self.assertGreaterEqual(CONTEXT_TOKENS, 16000)
        self.assertEqual(MAX_TOKENS, 3000)
        self.assertEqual(TIMEOUT_S, 600)

    def test_model_is_the_configured_one(self):
        self.assertEqual(HttpClient(config()).model, "test-model")


class CompletionTest(unittest.TestCase):
    def test_openai_answer(self):
        body = {"choices": [{"message": {"content": '{"chapter": 1}'}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 30}}
        completion = HttpClient(config()).completion(body)
        self.assertEqual(completion.text, '{"chapter": 1}')
        self.assertEqual((completion.prompt_tokens, completion.completion_tokens), (120, 30))

    def test_ollama_answer(self):
        body = {"message": {"content": '{"chapter": 1}'},
                "prompt_eval_count": 120, "eval_count": 30}
        completion = HttpClient(config("ollama", "/api/chat")).completion(body)
        self.assertEqual(completion.text, '{"chapter": 1}')
        self.assertEqual((completion.prompt_tokens, completion.completion_tokens), (120, 30))

    def test_tokens_are_optional(self):
        body = {"choices": [{"message": {"content": "{}"}}]}
        completion = HttpClient(config()).completion(body)
        self.assertIsNone(completion.prompt_tokens)

    def test_unexpected_body_is_an_error(self):
        with self.assertRaises(ValueError):
            HttpClient(config()).completion({"error": "model not found"})


if __name__ == "__main__":
    unittest.main()
