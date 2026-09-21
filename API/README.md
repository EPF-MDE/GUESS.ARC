# API — client de tagging taxonomie (issues #5, #6, #7, #8, #9, #10)

Client HTTP unique, compatible OpenAI, qui appelle un LLM pour tagger **un**
chapitre à la fois (fichier `.md` silver entier) et écrit un
`data/taxonomy/chapter_NNNN.json` validé contre `docs/taxonomy-schema.json`.

Un provider n'est qu'une configuration (`base_url`, variable d'env pour la
clé, identifiant de modèle) — voir `providers.py`. Les appels passent par une
**chaîne de fallback** (`provider_fallback.py`, issue #6) : le provider
courant est tenté, avec retry en place sur `429`/`5xx`, puis bascule sur le
suivant si l'échec persiste. Chaîne branchée : Gemini (1er), Mistral (2e
relais), Groq (3e relais), OpenRouter (4e et dernier relais).

Si les 4 providers de la chaîne échouent sur un chapitre donné, le client ne
saute jamais silencieusement le chapitre : une erreur `AllProvidersFailedError`
est levée (avec un message explicite sur stderr) et remonte à l'appelant.

## Compteur de quota journalier (`API/quota_state.json`, issue #9)

Avant d'appeler un provider, le client vérifie son budget journalier local
dans `API/quota_state.json` (`{provider: {date, count}}`) et bascule
directement sur le suivant de la chaîne si le budget est épuisé — **sans
effectuer l'appel réseau**. Le compteur est mis à jour à chaque appel
*réussi* et persiste entre deux exécutions (redémarrage à froid) ; il n'est
remis à zéro que lorsque la date stockée n'est plus celle du jour.

Seuls Groq (1000 req/jour, tier gratuit `openai/gpt-oss-120b`) et OpenRouter
(50 req/jour sans crédit acheté) ont une limite locale configurée
(`ProviderConfig.daily_limit`) : Gemini et Mistral exposent déjà leur RPD
restant dans les en-têtes de réponse, donc ne sont pas (encore) suivis
localement. `API/quota_state.json` est local à la machine et n'est pas
commité (voir `.gitignore`).

## Obtenir une clé Gemini (gratuite)

1. Aller sur [Google AI Studio](https://aistudio.google.com/apikey).
2. Se connecter avec un compte Google, cliquer sur **Create API key**.
3. Copier la clé.

Le niveau gratuit d'AI Studio suffit pour tagger quelques chapitres de test ;
il a ses propres limites de quota (requêtes/minute et /jour), voir la page
elle-même pour les chiffres à jour.

## Obtenir une clé Mistral (gratuite, tier « Experiment »)

1. Aller sur [console.mistral.ai](https://console.mistral.ai).
2. Créer un compte (vérification par numéro de téléphone, pas de carte
   bancaire) et activer le tier gratuit **Experiment**.
3. Dans la console, générer une clé API et la copier.

Le tier Experiment a un débit (TPM) élevé mais un RPM faible — c'est pour ça
qu'il sert de relais derrière Gemini plutôt que de moteur principal.

## Obtenir une clé Groq (gratuite)

1. Aller sur [console.groq.com/keys](https://console.groq.com/keys).
2. Se connecter (ou créer un compte), cliquer sur **Create API Key**.
3. Copier la clé.

Sert de 3e relais (`openai/gpt-oss-120b`) derrière Gemini et Mistral. Le
modèle précédent (`llama-3.3-70b-versatile`) a été déprécié sur le tier
gratuit le 2026-06-17.

> **Note quota** : contrairement à Gemini/Mistral, Groq ne renvoie pas le
> RPD (requêtes/jour) restant dans les en-têtes de sa réponse. Le futur
> compteur de quota (ticket suivant) ne pourra pas le lire depuis les
> réponses Groq et devra suivre l'usage autrement (ex. comptage local des
> appels).

## Obtenir une clé OpenRouter (gratuite)

1. Aller sur [openrouter.ai/keys](https://openrouter.ai/keys).
2. Se connecter (ou créer un compte), cliquer sur **Create Key**.
3. Copier la clé.

Sert de 4e et dernier relais, derrière Gemini, Mistral et Groq. Contrairement
aux autres providers, le modèle n'est **jamais codé en dur** : le client
interroge `GET /models?max_price=0` au moment de l'appel pour choisir un
modèle `:free` disponible dans le catalogue gratuit d'OpenRouter (qui tourne
en permanence). Les requêtes envoient aussi les en-têtes `HTTP-Referer` et
`X-Title` recommandés par OpenRouter pour identifier l'app appelante.

## Où les déposer

Copier `.env` (racine du dépôt) si ce n'est pas déjà fait, puis renseigner les 4
clés (obligatoires pour que la chaîne de fallback complète tourne de bout en
bout). Les `*_MODEL` sont pré-remplies avec le modèle gratuit retenu pour
chaque provider — à ne changer que pour tester un autre modèle :

```
GEMINI_API_KEY=la-clé-gemini-copiée-ci-dessus
GEMINI_MODEL=gemini-3.6-flash

MISTRAL_API_KEY=la-clé-mistral-copiée-ci-dessus
MISTRAL_MODEL=mistral-small-latest

GROQ_API_KEY=la-clé-groq-copiée-ci-dessus
GROQ_MODEL=openai/gpt-oss-120b

OPENROUTER_API_KEY=la-clé-openrouter-copiée-ci-dessus
OPENROUTER_MODEL=
```

`OPENROUTER_MODEL` reste volontairement vide : contrairement aux 3 autres, le
modèle OpenRouter n'est jamais codé en dur (issue #8) — le client résout un
modèle `:free` disponible via `GET /models?max_price=0` à chaque appel, parce
que le catalogue gratuit change dans le temps. Ne renseigner cette ligne que
pour forcer un modèle précis à la place de la résolution automatique.

`.env` est dans `.gitignore` — ne jamais commiter de clé.

## Lancer le client

```bash
pip install -r requirements.txt

# un ou plusieurs chapitres précis (chaîne de fallback par défaut : gemini, mistral, groq, openrouter)
python API/taxonomy_client.py --chapters 1 2

# tous les chapitres 1..N
python API/taxonomy_client.py --max-chapter 50

# forcer un ordre ou un sous-ensemble de providers
python API/taxonomy_client.py --chapters 1 --providers mistral
```

- Un chapitre déjà présent dans `data/taxonomy/` est sauté : aucun appel
  réseau, aucune consommation de quota supplémentaire.
- Le bloc `## DÉFINITION TAXONOMIE` du prompt système est chargé depuis
  `docs/taxonomy-schema.md` à chaque lancement — jamais codé en dur.
- Le schéma de sortie est chargé depuis `docs/taxonomy-schema.json` et sert
  deux usages (spec section 4.3) : `response_format: {"type": "json_schema",
  "strict": true, ...}` pour les providers confirmés le supporter (Gemini
  seul pour l'instant, `ProviderConfig.supports_strict_json_schema`) ; pour
  les autres (Mistral, Groq, OpenRouter), `response_format: {"type":
  "json_object"}` en repli, avec la même validation applicative de
  l'enveloppe contre ce schéma après coup, quel que soit le provider utilisé.
- Sur `429` : le client respecte `Retry-After` si présent, sinon attend un
  backoff exponentiel plafonné à ~120 s, avant de réessayer le même
  provider ; sur `5xx` : une nouvelle tentative, puis bascule sur le
  provider suivant si l'échec persiste.
- `max_completion_tokens` est fixé à 8192 sur chaque appel : sans ça, un
  provider (observé sur Groq) peut tronquer le JSON avant la fin de l'objet
  (schéma non respecté) et répondre `400` plutôt qu'un code retryable — ce
  qui fait échouer le chapitre au lieu de basculer sur le relais suivant.

## Run de benchmark + journalisation (`API/run_benchmark.py`, issue #10)

Le but du banc de test (spec section 1) est de comparer les modèles **entre
eux** sur le même lot de chapitres — pas d'obtenir une seule taxonomie par
chapitre. `run_benchmark.py` appelle donc chaque provider **indépendamment**
sur le **même lot configurable de chapitres** (20 par défaut, tirés de
`data/silver/`) : pas de bascule d'un provider à l'autre ici (un chapitre en
échec sur un modèle est journalisé comme échec pour ce modèle, avec retry en
place sur `429`/`5xx`, puis le run passe au chapitre suivant *pour ce même
modèle* — jamais transmis à un autre). C'est volontairement différent de
`taxonomy_client.py` en usage direct, où la chaîne de fallback sert la
fiabilité (le premier qui répond gagne) pour tagger le corpus réel une fois
un modèle choisi à l'issue de ce benchmark.

Chaque provider écrit dans son propre sous-dossier
`data/taxonomy/<provider>/chapter_NNNN.json` (jamais un
`data/taxonomy/chapter_NNNN.json` partagé) : les 4 sorties sur les mêmes
chapitres restent comparables côte à côte, pas seulement leurs statistiques
agrégées. Chaque appel (retries en place inclus) est en plus journalisé dans
un fichier JSONL : provider/modèle utilisé, tokens d'entrée/sortie réels
(`usage.prompt_tokens`/`completion_tokens` de la réponse), succès/échec,
code d'erreur le cas échéant. Un provider sauté pour quota local épuisé
(issue #9) n'est pas journalisé comme un appel : il n'a jamais touché le
réseau.

```bash
# lot par défaut (20 premiers chapitres de data/silver/)
python API/run_benchmark.py

# lot configurable
python API/run_benchmark.py --batch-size 50

# chapitres précis plutôt que le lot par défaut
python API/run_benchmark.py --chapters 1 2 3

# comparer seulement un sous-ensemble de modèles
python API/run_benchmark.py --providers gemini mistral

# ré-afficher le rapport d'un run précédent sans refaire d'appel réseau
python API/run_benchmark.py --report-only
```

À la fin du run, un rapport par provider est affiché (nombre d'appels,
succès/échecs, répartition des codes d'erreur, tokens d'entrée/sortie
min/moyenne/max, et un débit *observé* — appels/min et tokens/min, calculé
depuis l'horodatage de chaque appel journalisé pour ce provider) — à
comparer aux limites publiées (RPM/RPD/TPM/contexte) de chaque provider pour
décider quel(s) modèle(s) tiennent à l'échelle des 1193 chapitres du corpus
complet.

Le run est **reprenable par modèle** : il réutilise la logique de skip de
`tag_chapter` (issue #5), maintenant scopée au sous-dossier de chaque
provider — un chapitre déjà présent dans `data/taxonomy/<provider>/` n'est
pas retaggé *pour ce provider*, donc relancer le même lot après une coupure
ne re-consomme ni appel ni quota pour les couples (provider, chapitre) déjà
traités, indépendamment les uns des autres.

Journal écrit par défaut dans `API/benchmark_log.jsonl` (append, jamais
commité — voir `.gitignore`) ; surchargeable via `--log-file`.

### `data/taxonomy/fights_index.json` par modèle

Chaque sous-dossier `data/taxonomy/<provider>/` a son propre
`fights_index.json`, maintenu au fil du tagging (issue #11) — les
`fight_id` produits par un modèle n'ont aucune raison de coïncider avec ceux
d'un autre. Un chapitre taggé **avant** que cette maintenance existe (ou
copié hors bande) ne peuple pas rétroactivement l'index ; pour le
reconstruire à partir des `chapter_NNNN.json` déjà présents dans un
dossier :

```bash
python API/rebuild_fights_index.py --taxonomy-dir data/taxonomy/gemini
```

### Smoke test

Pour vérifier rapidement que la chaîne de fallback, le compteur de quota et
la journalisation fonctionnent de bout en bout sans lancer le lot complet
(20 chapitres) :

```bash
# tests unitaires — aucun appel réseau, aucune clé requise
python -m pytest test/test_run_benchmark.py test/test_benchmark_log.py test/test_taxonomy_client_benchmark_log.py -v

# run réel sur 1-2 chapitres seulement (nécessite .env avec les clés, voir ci-dessus)
python API/run_benchmark.py --chapters 1 2

# ré-afficher le rapport sans refaire d'appel
python API/run_benchmark.py --report-only
```

- `--chapters 1 2` déclenche de vrais appels réseau sur les 4 providers
  (Gemini, Mistral, Groq, OpenRouter, indépendamment) et écrit
  `data/taxonomy/<provider>/chapter_0001.json` / `chapter_0002.json` pour
  chacun — à supprimer ensuite si ces fichiers ne sont pas censés rester (ou
  choisir des numéros de chapitre déjà attendus dans le lot final).
- `API/benchmark_log.jsonl` et `API/quota_state.json` sont dans `.gitignore` :
  un smoke test ne salit jamais `git status`.
- Si un chapitre est déjà présent dans `data/taxonomy/<provider>/`, le
  relancer ne refait aucun appel pour ce provider (logique de skip, issue
  #5) — utile pour re-tester sans reconsommer de quota.

## Variables d'environnement

| Variable | Rôle | Obligatoire |
| --- | --- | --- |
| `GEMINI_API_KEY` | Clé Google AI Studio | Oui, pour `gemini` (1er de la chaîne par défaut) |
| `GEMINI_MODEL` | Surcharge le modèle par défaut (`gemini-3.6-flash`) | Non |
| `MISTRAL_API_KEY` | Clé Mistral AI Studio (tier Experiment) | Oui, pour `mistral` (2e relais par défaut) |
| `MISTRAL_MODEL` | Surcharge le modèle par défaut (`mistral-small-latest`) | Non |
| `GROQ_API_KEY` | Clé Groq | Oui, pour `groq` (3e relais par défaut) |
| `GROQ_MODEL` | Surcharge le modèle par défaut (`openai/gpt-oss-120b`) | Non |
| `OPENROUTER_API_KEY` | Clé OpenRouter | Oui, pour `openrouter` (4e et dernier relais par défaut) |
| `OPENROUTER_MODEL` | Fixe un modèle au lieu de la résolution runtime (`GET /models?max_price=0`) | Non |
| `ANTHROPIC_API_KEY` | Clé Anthropic (POC Konrad) | Non — usage séparé, sans lien avec ce banc de test |
