# GUESS.ARC

This repository is dedicated to the GUESS.ARC Semester's project.

## One Piece ML — livrable semaine 1

Étude de faisabilité et état de l'art pour la prédiction de tags du chapitre n+1
de *One Piece* par apprentissage automatique.

### Contenu

| Fichier | Rôle |
| --- | --- |
| `onepiece-faisabilite/faisabilite-etat-de-lart.md` | Le livrable : benchmark des sources, cadrage ML, plan sur 8 semaines |
| `onepiece-faisabilite/scripts/onepiece_ingest.py` | Ingestion bronze + silver depuis l'API MediaWiki du wiki One Piece anglais |
| `onepiece-faisabilite/scripts/0N_*.py` | Pipeline de taxonomie de tags — voir [section dédiée](#pipeline-de-taxonomie-de-tags) |

### Environnement

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### Lancer l'ingestion

```bash
cd onepiece-faisabilite/scripts

# run complet : les 1193 chapitres, ~24 requêtes, moins d'une minute
python onepiece_ingest.py --max-chapter 1193

# mise à jour hebdomadaire : ne retraite que les pages dont la révision a changé
python onepiece_ingest.py --max-chapter 1200 --incremental
```

Sorties, relatives au dossier courant :

- `data/bronze/chapters.jsonl` — le wikitexte brut archivé, une ligne par chapitre
- `data/silver/chapter_NNNN.md` — un fichier par chapitre, front-matter YAML + résumé long
- `data/state.json` — les `revid` connus, pour les runs incrémentaux

### Pipeline de taxonomie de tags

Construit une taxonomie de tags canoniques (perso, lieu, objet, event, rel) à
partir des résumés silver, puis réduit n'importe quel texte libre — résumé
source ou prédiction écrite à la main — à ces tags. Les scripts s'exécutent
dans l'ordre depuis `onepiece-faisabilite/scripts/` et chaque étape lit les
sorties de la précédente dans `onepiece-faisabilite/output/` :

```bash
cd onepiece-faisabilite/scripts

# 1. Extrait les candidats de tags (NER spaCy + front-matter) depuis data/silver/*.md
python 01_extract_candidates.py
# -> output/candidates.csv

# 2. Encode chaque terme candidat unique en vecteur (sentence-transformers multilingue)
python 02_embed_candidates.py
# -> output/embeddings.npy, output/terms.json, output/embedder_meta.json

# 3. Clusterise les termes proches en taxonomie canonique (HDBSCAN)
python 03_cluster_taxonomy.py
# -> output/taxonomy.json (labels retenus), output/taxonomy_noise.json (bruit probable)

# 4. Tague un texte libre à partir de la taxonomie construite
python 04_tag_text.py --file mon_resume.md
python 04_tag_text.py --text "Luffy et Zoro affrontent un nouvel ennemi..."
# -> JSON sur stdout (ou --out fichier.json) : [{"category": "event", "tag": "combat", "confidence": 0.87}, ...]

# 5. Compare deux ensembles de tags (ex. prédiction vs résumé réel du chapitre n+1)
python 05_compare_tags.py prediction.json realite.json
# -> tableau de score de Jaccard pondéré par catégorie (poids dans ../weights.json)
```

spaCy nécessite un modèle téléchargé séparément (`python -m spacy download
en_core_web_sm`) ; à défaut, `01_extract_candidates.py` et `04_tag_text.py`
retombent sur un extracteur regex plus grossier (voir `taxonomy/extraction.py`).
De même, si `sentence-transformers` ne peut pas télécharger son modèle,
`02_embed_candidates.py` retombe sur un TF-IDF de n-grams de caractères
(voir `taxonomy/embedding.py`) — dans les deux cas le pipeline reste
utilisable, avec une qualité de tags dégradée.

Pour ajouter un nouveau résumé à taguer : écrire le texte dans un fichier
(ou le passer en `--text`), lancer l'étape 4 dessus. Aucune réextraction ni
recalcul de la taxonomie (étapes 1-3) n'est nécessaire tant que la taxonomie
existante reste pertinente ; ne relancer 1-3 que si le corpus source évolue
sensiblement (nouveaux chapitres, nouveaux personnages).

### Chiffres clés du livrable

- Wiki EN : résumé long sur **1193 / 1193** chapitres, complété **~70 min** après la sortie
- Wiki FR : plus aucun résumé depuis le chapitre 1188 (12 juillet 2026)
- Wiki JA : 369 articles, aucune page de chapitre
- Un modèle qui ne prédit rien obtient **98,57 % d'accuracy** — la métrique doit changer
- Baseline de persistance : **53 % de F1 micro**. Plafond atteignable : **85 %**

### Licence des données

Le contenu du wiki Fandom est sous licence CC BY-SA. Usage académique avec
attribution. Le script envoie un `User-Agent` identifiant le projet et limite
son débit.
