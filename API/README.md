# API — client de tagging taxonomie (issues #5, #6, #7)

Client HTTP unique, compatible OpenAI, qui appelle un LLM pour tagger **un**
chapitre à la fois (fichier `.md` silver entier) et écrit un
`data/taxonomy/chapter_NNNN.json` validé contre `docs/taxonomy-schema.json`.

Un provider n'est qu'une configuration (`base_url`, variable d'env pour la
clé, identifiant de modèle) — voir `providers.py`. Les appels passent par une
**chaîne de fallback** (`provider_fallback.py`, issue #6) : le provider
courant est tenté, avec retry en place sur `429`/`5xx`, puis bascule sur le
suivant si l'échec persiste. Chaîne branchée : Gemini (1er), Mistral (2e
relais), Groq (3e relais).

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

## Où les déposer

Copier `.env` (racine du dépôt) si ce n'est pas déjà fait, puis renseigner :

```
GEMINI_API_KEY=la-clé-gemini-copiée-ci-dessus
MISTRAL_API_KEY=la-clé-mistral-copiée-ci-dessus
GROQ_API_KEY=la-clé-groq-copiée-ci-dessus
```

`.env` est dans `.gitignore` — ne jamais commiter de clé.

## Lancer le client

```bash
pip install -r requirements.txt

# un ou plusieurs chapitres précis (chaîne de fallback par défaut : gemini, mistral, groq)
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
- Le schéma de sortie (`response_format: json_schema` strict + validation)
  est chargé depuis `docs/taxonomy-schema.json`.
- Sur `429` : le client respecte `Retry-After` si présent, sinon attend un
  backoff exponentiel plafonné à ~120 s, avant de réessayer le même
  provider ; sur `5xx` : une nouvelle tentative, puis bascule sur le
  provider suivant si l'échec persiste.

## Variables d'environnement

| Variable | Rôle | Obligatoire |
| --- | --- | --- |
| `GEMINI_API_KEY` | Clé Google AI Studio | Oui, pour `gemini` (1er de la chaîne par défaut) |
| `GEMINI_MODEL` | Surcharge le modèle par défaut (`gemini-2.5-flash`) | Non |
| `MISTRAL_API_KEY` | Clé Mistral AI Studio (tier Experiment) | Oui, pour `mistral` (2e relais par défaut) |
| `MISTRAL_MODEL` | Surcharge le modèle par défaut (`mistral-small-latest`) | Non |
| `GROQ_API_KEY` | Clé Groq | Oui, pour `groq` (3e relais par défaut) |
| `GROQ_MODEL` | Surcharge le modèle par défaut (`openai/gpt-oss-120b`) | Non |
