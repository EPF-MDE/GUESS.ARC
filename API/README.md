# API — client de tagging taxonomie (issue #5)

Client HTTP unique, compatible OpenAI, qui appelle un LLM pour tagger **un**
chapitre à la fois (fichier `.md` silver entier) et écrit un
`data/taxonomy/chapter_NNNN.json` validé contre `docs/taxonomy-schema.json`.

Un provider n'est qu'une configuration (`base_url`, variable d'env pour la
clé, identifiant de modèle) — voir `providers.py`. Premier provider branché :
Gemini.

## Obtenir une clé Gemini (gratuite)

1. Aller sur [Google AI Studio](https://aistudio.google.com/apikey).
2. Se connecter avec un compte Google, cliquer sur **Create API key**.
3. Copier la clé.

Le niveau gratuit d'AI Studio suffit pour tagger quelques chapitres de test ;
il a ses propres limites de quota (requêtes/minute et /jour), voir la page
elle-même pour les chiffres à jour.

## Où la déposer

Copier `.env` (racine du dépôt) si ce n'est pas déjà fait, puis renseigner :

```
GEMINI_API_KEY=la-clé-copiée-ci-dessus
```

`.env` est dans `.gitignore` — ne jamais commiter de clé.

## Lancer le client

```bash
pip install -r requirements.txt

# un ou plusieurs chapitres précis
python API/taxonomy_client.py --chapters 1 2

# tous les chapitres 1..N
python API/taxonomy_client.py --max-chapter 50
```

- Un chapitre déjà présent dans `data/taxonomy/` est sauté : aucun appel
  réseau, aucune consommation de quota supplémentaire.
- Le bloc `## DÉFINITION TAXONOMIE` du prompt système est chargé depuis
  `docs/taxonomy-schema.md` à chaque lancement — jamais codé en dur.
- Le schéma de sortie (`response_format: json_schema` strict + validation)
  est chargé depuis `docs/taxonomy-schema.json`.

## Variables d'environnement

| Variable | Rôle | Obligatoire |
| --- | --- | --- |
| `GEMINI_API_KEY` | Clé Google AI Studio | Oui, pour `--provider gemini` (défaut) |
| `GEMINI_MODEL` | Surcharge le modèle par défaut (`gemini-2.5-flash`) | Non |
