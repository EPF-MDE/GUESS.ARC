"""Diagnostic du serveur LLM, avant le passage d'extraction des événements.

À lancer à la main, depuis le réseau de l'école (ou son VPN), après avoir rempli
le `.env` à la racine du repo (voir .env.example) :

    python scripts/llm/diagnostic_serveur.py

Seules `LLM_BASE_URL` et `LLM_API_KEY` sont nécessaires au départ. Sans
`LLM_MODEL`, le script liste les modèles du serveur et s'arrête : recopier
l'identifiant voulu dans le `.env` et relancer. `LLM_API` et `LLM_CHAT_PATH`
ne sont pas lus : le script essaie chaque route connue et dit laquelle
reporter dans le `.env`.

Il répond à 4 questions :
  1. Quel logiciel sert les modèles (Open WebUI, Ollama, serveur compatible OpenAI) ?
  2. Quels identifiants de modèles le serveur expose-t-il ?
  3. Pour chaque route, la sortie contrainte par schéma JSON est-elle vraiment appliquée ?
  4. Un appel de ~10 000 tokens passe-t-il sans être tronqué ?

Les appels passent par le client du pipeline (guess_arc.events.http_client), avec
ses paramètres fixes : c'est ce que le pipeline enverra. Le client n'a pas
d'autre test contre le serveur réel. Pause de 15 s entre deux appels au modèle ;
résultats écrits dans diagnostic_serveur.json (à la racine du repo, sans la clé API, hors git).
"""

import json
import sys
import time

import requests

from guess_arc import paths
from guess_arc.events.extraction import PAUSE_S
from guess_arc.events.http_client import ConfigError, HttpClient, LLMConfig, read_env_file
from guess_arc.events.response import strip_thinking

REPORT_PATH = paths.REPO_ROOT / "diagnostic_serveur.json"
THINKING_MARKERS = ("<think", "<thought", "<|channel")

ROUTES = [
    {"name": "Open WebUI, compatible OpenAI", "path": "/api/chat/completions", "api": "openai"},
    {"name": "Open WebUI, passerelle Ollama", "path": "/ollama/api/chat", "api": "ollama"},
    {"name": "compatible OpenAI standard", "path": "/v1/chat/completions", "api": "openai"},
    {"name": "Ollama direct", "path": "/api/chat", "api": "ollama"},
]

ENUM_SCHEMA = {
    "type": "object",
    "properties": {"answer": {"type": "string", "enum": ["alpha", "beta"]}},
    "required": ["answer"],
    "additionalProperties": False,
}
CODE_SCHEMA = {
    "type": "object",
    "properties": {"code": {"type": "string"}},
    "required": ["code"],
    "additionalProperties": False,
}
SECRET = "4817"
FILLER = "".join(f"Line {i}: the crew keeps sailing across the calm sea.\n" for i in range(900))
LONG_PROMPT = (f"The secret code is {SECRET}. Remember it.\n\n{FILLER}\n"
               "What is the secret code given at the very beginning? Answer with the number only.")
SYSTEM = "Answer in JSON, following the given schema."


def save(report: dict) -> None:
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    env = read_env_file(paths.ENV_PATH) if paths.ENV_PATH.is_file() else {}
    base, key, model = (env.get("LLM_BASE_URL", "").rstrip("/"), env.get("LLM_API_KEY", ""),
                        env.get("LLM_MODEL", ""))
    if not base or not key:
        sys.exit(f"LLM_BASE_URL et LLM_API_KEY doivent être remplies dans {paths.ENV_PATH} "
                 "(voir .env.example)")
    headers = {"Authorization": f"Bearer {key}"}
    report = {"base_url": base, "model": model or None, "probes": {}, "routes": {}}

    # ------------------------------------------------------------ 1. identification
    print(f"Serveur : {base}")
    for path in ["/", "/api/config", "/api/models", "/ollama/api/tags",
                 "/v1/models", "/api/tags", "/api/version"]:
        try:
            r = requests.get(base + path, headers=headers, timeout=30)
            report["probes"][path] = {"status": r.status_code, "body": r.text[:500]}
        except requests.RequestException as e:
            report["probes"][path] = {"status": None, "body": f"{type(e).__name__}: {e}"[:500]}
        print(f"  GET {path:<18} -> {report['probes'][path]['status']}")

    home = report["probes"]["/"]["body"].lower()
    config = report["probes"]["/api/config"]["body"].lower()
    if "open webui" in home or "webui" in config:
        software = "Open WebUI"
    elif report["probes"]["/api/tags"]["status"] == 200:
        software = "Ollama (accès direct)"
    elif report["probes"]["/v1/models"]["status"] == 200:
        software = "serveur compatible OpenAI (vLLM, LiteLLM, LM Studio…)"
    else:
        software = "indéterminé (voir les codes HTTP ci-dessus)"
    report["software"] = software
    print(f"\nLogiciel probable : {software}")

    # ------------------------------------------------------------ 2. modèles
    model_ids = []
    for path in ["/api/models", "/v1/models", "/ollama/api/tags", "/api/tags"]:
        if report["probes"][path]["status"] != 200:
            continue
        try:
            data = requests.get(base + path, headers=headers, timeout=30).json()
        except (requests.RequestException, ValueError):
            continue
        for item in data.get("data") or data.get("models") or []:
            mid = item.get("id") or item.get("model") or item.get("name")
            if mid and mid not in model_ids:
                model_ids.append(mid)
    report["models_found"] = model_ids
    print(f"Modèles trouvés : {model_ids if model_ids else 'aucun (clé API ?)'}")
    if not model:
        print(f"\nLLM_MODEL est vide dans {paths.ENV_PATH} : y recopier l'identifiant "
              "voulu parmi les modèles ci-dessus, puis relancer.")
        save(report)
        sys.exit(1)
    print(f"Modèle testé    : {model}")

    # ------------------------------------------------------------ 3 et 4. routes
    first_call = True
    for route in ROUTES:
        client = HttpClient(LLMConfig(base_url=base, api_key=key, model=model,
                                      api=route["api"], chat_path=route["path"]))
        res = {"api": route["api"]}
        print(f"\n=== Route {route['path']} ({route['name']}, LLM_API={route['api']}) ===")
        for test, user, schema in [
            ("json_schema", "What colour is the sky on a clear day? Answer in one word.",
             ENUM_SCHEMA),
            ("long_context_10k", LONG_PROMPT, CODE_SCHEMA),
        ]:
            if not first_call:
                time.sleep(PAUSE_S)
            first_call = False
            t0 = time.time()
            try:
                completion = client.complete(SYSTEM, user, schema)
                text, err = completion.text, None
            except Exception as e:  # le diagnostic note toutes les erreurs
                completion, text, err = None, "", f"{type(e).__name__}: {e}"[:300]
            dt = round(time.time() - t0, 1)
            try:
                answer = json.loads(strip_thinking(text))
            except ValueError:
                answer = None
            if test == "json_schema":
                ok = isinstance(answer, dict) and answer.get("answer") in ("alpha", "beta")
            else:
                ok = isinstance(answer, dict) and SECRET in str(answer.get("code"))
            res[test] = {
                "ok": ok, "seconds": dt, "error": err, "reply": text[:200],
                "thinking_block": any(m in text for m in THINKING_MARKERS),
                "prompt_tokens": completion.prompt_tokens if completion else None,
            }
            print(f"  {test:<17}: {'OK' if ok else 'ÉCHEC'} en {dt} s  "
                  f"{(err or repr(text[:60]))}")
            if err and test == "json_schema":
                break  # route absente ou refusée : inutile d'envoyer l'appel long
        report["routes"][route["path"]] = res

    # ------------------------------------------------------------ bilan
    print("\n=== Bilan ===")
    usable = [p for p, r in report["routes"].items()
              if r.get("json_schema", {}).get("ok") and r.get("long_context_10k", {}).get("ok")]
    report["usable_routes"] = usable
    if usable:
        best = usable[0]
        print(f"Route(s) utilisable(s) pour l'extraction : {usable}")
        print(f"À reporter dans le .env :\n  LLM_API={report['routes'][best]['api']}\n"
              f"  LLM_CHAT_PATH={best}")
    else:
        print("Aucune route ne passe les 2 tests : voir le détail ci-dessus "
              f"et {REPORT_PATH}.")
    try:
        configured = LLMConfig.from_env_file(paths.ENV_PATH).chat_path
        print(f"Route actuelle du .env ({configured}) : "
              f"{'utilisable' if configured in usable else 'NON utilisable'}")
    except ConfigError as e:
        print(f".env pas encore complet : {e}")
    for p, r in report["routes"].items():
        if any(t.get("thinking_block") for t in r.values() if isinstance(t, dict)):
            print(f"Attention : la route {p} renvoie un bloc de réflexion malgré le "
                  "mode « thinking » désactivé.")
    save(report)
    print(f"\nRésultats écrits dans {REPORT_PATH} (la clé API n'y figure pas).")


if __name__ == "__main__":
    main()
