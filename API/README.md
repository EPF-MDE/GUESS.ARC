# API — client de tagging taxonomie (issues #5, #6, #7, #8, #9, #10, #12)

Client HTTP unique, compatible OpenAI, qui appelle un LLM pour tagger **un**
chapitre à la fois (fichier `.md` silver entier) et écrit un
`data/taxonomy/chapter_NNNN.json` validé contre `docs/taxonomy-schema.json`.

Un provider n'est qu'une configuration (`base_url`, variable d'env pour la
clé, identifiant de modèle) — voir `providers.py`. Les appels passent par une
**chaîne de fallback** (`provider_fallback.py`, issue #6) : le provider
courant est tenté, avec retry en place sur `429`/`5xx`, puis bascule sur le
suivant si l'échec persiste. Chaîne branchée : Gemini (1er), Mistral (2e
relais), Groq (3e relais), puis 3 modèles gratuits fixes servis par
OpenRouter — `openrouter-nemotron`, `openrouter-nex-pro`, `openrouter-dots`
(4e à 6e et derniers relais).

Si les 6 providers de la chaîne échouent sur un chapitre donné, le client ne
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
localement. Les 3 providers OpenRouter (`openrouter-nemotron`,
`openrouter-nex-pro`, `openrouter-dots`) partagent une seule et même clé et
donc un seul budget de 50 req/jour : ils comptent sur la même entrée
`quota_key="openrouter"` dans `API/quota_state.json`, pas 50 chacun.
`API/quota_state.json` est local à la machine et n'est pas commité (voir
`.gitignore`).

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

Sert de 4e, 5e et 6e (derniers) relais, derrière Gemini, Mistral et Groq — un
relais par modèle fixe : `nvidia/nemotron-3-super-120b-a12b:free`,
`nex-agi/nex-n2.5-pro:free`, `dots-studio/dots-3-note-preview:free`. Les
requêtes envoient aussi les en-têtes `HTTP-Referer` et `X-Title` recommandés
par OpenRouter pour identifier l'app appelante.

Les 3 modèles ont été choisis (via `GET /models` du catalogue public) pour
leur support confirmé de `response_format`. Une première version résolvait
le modèle dynamiquement (`GET /models?max_price=0`, premier `:free` trouvé,
issue #8) : en pratique le catalogue gratuit tourne souvent vers des modèles
qui n'acceptent pas `response_format`, ce qu'OpenRouter répond par un `400`
non retenté et non basculé — le run entier plantait. `providers.OPENROUTER`
(résolution dynamique) reste défini pour un usage direct/manuel, mais n'est
plus dans la chaîne par défaut.

## Où les déposer

Copier `.env` (racine du dépôt) si ce n'est pas déjà fait, puis renseigner les
clés (obligatoires pour que la chaîne de fallback complète tourne de bout en
bout — une seule clé `OPENROUTER_API_KEY` sert aux 3 relais OpenRouter). Les
`*_MODEL` sont **obligatoires** aussi : aucun modèle n'est codé en dur dans
`providers.py`, le `.env` est la seule source. Valeurs actuellement retenues
(modèles gratuits) :

```
GEMINI_API_KEY=la-clé-gemini-copiée-ci-dessus
GEMINI_MODEL=gemini-3.6-flash

MISTRAL_API_KEY=la-clé-mistral-copiée-ci-dessus
MISTRAL_MODEL=ministral-14b-latest

GROQ_API_KEY=la-clé-groq-copiée-ci-dessus
GROQ_MODEL=openai/gpt-oss-120b

OPENROUTER_API_KEY=la-clé-openrouter-copiée-ci-dessus
OPENROUTER_NEMOTRON_MODEL=nvidia/nemotron-3-super-120b-a12b:free
OPENROUTER_NEX_PRO_MODEL=google/gemma-4-31b-it:free
OPENROUTER_DOTS_MODEL=dots-studio/dots-3-note-preview:free
```

Une variable `*_MODEL` absente fait échouer `run_benchmark.py` dès le
démarrage, avant tout appel API, avec la liste de ce qui manque.
`OPENROUTER_MODEL` (config dynamique, hors benchmark) est la seule exception :
vide, elle choisit un modèle `:free` dans le catalogue au moment de l'appel.

`.env` est dans `.gitignore` — ne jamais commiter de clé.

## Lancer le client

```bash
pip install -r requirements.txt

# un ou plusieurs chapitres précis (chaîne de fallback par défaut : gemini, mistral, groq,
# openrouter-nemotron, openrouter-nex-pro, openrouter-dots)
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
échec sur un modèle est journalisé comme échec pour ce modèle — jamais
transmis à un autre ; voir la stratégie `429` ci-dessous). C'est volontairement différent de
`taxonomy_client.py` en usage direct, où la chaîne de fallback sert la
fiabilité (le premier qui répond gagne) pour tagger le corpus réel une fois
un modèle choisi à l'issue de ce benchmark.

Chaque provider écrit dans son propre sous-dossier
`data/taxonomy/<provider>/chapter_NNNN.json` (jamais un
`data/taxonomy/chapter_NNNN.json` partagé) : les sorties sur les mêmes
chapitres restent comparables côte à côte, pas seulement leurs statistiques
agrégées. Chaque appel (retries en place inclus) est en plus journalisé dans
un fichier JSONL : provider/modèle utilisé, tokens d'entrée/sortie réels
(`usage.prompt_tokens`/`completion_tokens` de la réponse), succès/échec,
code d'erreur le cas échéant. Un provider sauté pour quota local épuisé
(issue #9) n'est pas journalisé comme un appel : il n'a jamais touché le
réseau. Un envelope reçu en `200` mais rejeté par la validation (schéma,
ou `chapter.number` différent du chapitre demandé) est journalisé en plus
comme échec avec le code `validation_rejected` : le rapport distingue ainsi
« appel OK » de « fichier écrit ».

### Réparation des réponses mal formées (issue #13)

Avant validation, `API/taxonomy_repair.py` rattrape ce qui peut l'être sans
inventer de donnée :

- **Syntaxe** : balises ```` ```json ````, texte autour de l'objet, puis
  `json5` (virgules finales, clés sans guillemets, guillemets simples,
  commentaires). `json5` plutôt que `json_repair` : ce dernier « complète »
  une réponse tronquée, ce qui revient à inventer la fin. Un texte
  irréparable est journalisé avec le code `invalid_json` (tokens + extrait)
  et compté dans le quota.
- **Forme**, pilotée par `docs/taxonomy-schema.json` et seulement sur une
  valeur qui ne respecte pas son type : chaîne → `[chaîne]`, `"null"`/`""` →
  `null` sur un champ nullable, `"82"` → `82`, `"true"` → `true`. Un champ
  requis absent, une valeur hors enum ou hors bornes, une propriété
  inconnue restent rejetés (`validation_rejected`).

Chaque réparation (chemin, type, avant, après) est dans le champ `repairs`
de l'entrée du journal. Le rapport affiche par provider : conformes du
premier coup / réparés / rejetés.

### Stratégie `429` et rythme par provider (issue #12)

Les tiers gratuits se grillent vite si on insiste : le run est organisé pour
consommer le moins de quota possible.

- **Round-robin** : boucle externe sur les chapitres, interne sur les
  providers (ch1 sur tous, puis ch2…), pour que chaque provider « se
  repose » pendant que les autres travaillent.
- **Intervalle minimal par provider** (`ProviderConfig.min_interval_s`),
  respecté avant chaque appel, retries `5xx` compris. Les 3 modèles
  OpenRouter partagent une clé, donc un seul rythme (clé `quota_key`).
- **Pas de retry en place sur `429`** : le couple (provider, chapitre) est
  mis dans une file et le run continue. En fin de lot, chaque couple de la
  file est retenté **une fois** ; un nouveau `429` ⇒ provider marqué
  **épuisé pour la journée** dans `API/quota_state.json`, et tous ses
  chapitres restants sont sautés sans appel réseau — y compris lors d'une
  relance le même jour (date UTC, même mécanisme que le compteur #9).
  L'épuisement est porté par le compte (`quota_key`) : un modèle OpenRouter
  épuisé fait sauter les deux autres, qui partagent la même clé.
- `Retry-After` > 60 s ⇒ quota journalier, pas par minute : provider
  marqué épuisé directement, sans passer par la file.
- `503`/`5xx` : 1 retry rapide en place (surcharge côté provider, pas
  notre quota), puis le couple est compté en échec.
- Un provider dont le compteur local (#9) est à zéro est sauté pour le reste
  du run.

| Provider | Limites publiées (tier gratuit, à revérifier par compte) | `min_interval_s` |
|---|---|---|
| Gemini `gemini-3.6-flash` | ~20 RPD, RPM non publié | 15 s |
| Mistral (Experiment) | 1 req/s, 500k TPM | 2 s |
| Groq `openai/gpt-oss-120b` | 30 RPM, **8k TPM**, 1000 RPD — 1 chapitre ≈ 5–7k tokens | 60 s |
| OpenRouter `:free` (3 modèles) | 20 RPM, 50 RPD partagés (<10 crédits) | 3 s (partagé) |

Sources : [Groq](https://console.groq.com/docs/rate-limits),
[OpenRouter](https://openrouter.ai/docs/api-reference/limits),
[Mistral](https://docs.mistral.ai/admin/user-management-finops/tier),
[Gemini](https://ai.google.dev/gemini-api/docs/rate-limits).

Pour « dé-épuiser » un provider avant minuit UTC (par ex. après avoir réglé
un problème de clé), supprimer son champ `"exhausted"` (entrée `openrouter` pour les 3 modèles
OpenRouter) dans
`API/quota_state.json`.

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
min/moyenne/max, nombre de fichiers réellement écrits vs rejetés par la
validation, et un débit *observé* — appels/min et tokens/min, calculé
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
python -m pytest test/test_run_benchmark.py test/test_benchmark_scheduling.py test/test_benchmark_log.py test/test_taxonomy_client_benchmark_log.py -v

# run réel sur 1-2 chapitres seulement (nécessite .env avec les clés, voir ci-dessus)
python API/run_benchmark.py --chapters 1 2

# ré-afficher le rapport sans refaire d'appel
python API/run_benchmark.py --report-only
```

- `--chapters 1 2` déclenche de vrais appels réseau sur les 6 providers
  (Gemini, Mistral, Groq, openrouter-nemotron, openrouter-nex-pro,
  openrouter-dots, indépendamment) et écrit
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
| `GEMINI_MODEL` | Modèle Gemini (ex. `gemini-3.6-flash`) | Oui, pour `gemini` |
| `MISTRAL_API_KEY` | Clé Mistral AI Studio (tier Experiment) | Oui, pour `mistral` (2e relais par défaut) |
| `MISTRAL_MODEL` | Modèle Mistral (ex. `ministral-14b-latest`) | Oui, pour `mistral` |
| `GROQ_API_KEY` | Clé Groq | Oui, pour `groq` (3e relais par défaut) |
| `GROQ_MODEL` | Modèle Groq (ex. `openai/gpt-oss-120b`) | Oui, pour `groq` |
| `OPENROUTER_API_KEY` | Clé OpenRouter (partagée par les 3 relais OpenRouter) | Oui, pour `openrouter-nemotron`/`openrouter-nex-pro`/`openrouter-dots` (4e à 6e et derniers relais par défaut) |
| `OPENROUTER_NEMOTRON_MODEL` | Modèle du relais nemotron (ex. `nvidia/nemotron-3-super-120b-a12b:free`) | Oui, pour `openrouter-nemotron` |
| `OPENROUTER_NEX_PRO_MODEL` | Modèle du relais nex-pro (ex. `google/gemma-4-31b-it:free`) | Oui, pour `openrouter-nex-pro` |
| `OPENROUTER_DOTS_MODEL` | Modèle du relais dots (ex. `dots-studio/dots-3-note-preview:free`) | Oui, pour `openrouter-dots` |
| `ANTHROPIC_API_KEY` | Clé Anthropic (POC Konrad) | Non — usage séparé, sans lien avec ce banc de test |
