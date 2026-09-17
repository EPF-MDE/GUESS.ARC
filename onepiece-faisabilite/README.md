# One Piece ML — livrable semaine 1

Étude de faisabilité et état de l'art pour la prédiction de tags du chapitre n+1
de *One Piece* par apprentissage automatique.

## Contenu

| Fichier | Rôle |
| --- | --- |
| `faisabilite-etat-de-lart.md` | Le livrable : benchmark des sources, cadrage ML, plan sur 8 semaines |
| `scripts/onepiece_ingest.py` | Ingestion bronze + silver depuis l'API MediaWiki du wiki One Piece anglais |
| `scripts/test_parse.py` | Tests du parseur sur des extraits réels des chapitres 500 et 1193 |

## Lancer l'ingestion

```bash
pip install requests
cd scripts

# run complet : les 1193 chapitres, ~24 requêtes, moins d'une minute
python onepiece_ingest.py --max-chapter 1193

# mise à jour hebdomadaire : ne retraite que les pages dont la révision a changé
python onepiece_ingest.py --max-chapter 1200 --incremental
```

Sorties, relatives au dossier courant :

- `data/bronze/chapters.jsonl` — le wikitexte brut archivé, une ligne par chapitre
- `data/silver/chapter_NNNN.md` — un fichier par chapitre, front-matter YAML + résumé long
- `data/state.json` — les `revid` connus, pour les runs incrémentaux

## Lancer les tests

```bash
cd scripts && python test_parse.py
```

17 assertions, sans accès réseau. Elles couvrent les deux variantes de format
rencontrées sur le wiki : les annotations en parenthèses nues des anciens
chapitres (`*[[Kalifa]] (cover)`) et celles en apostrophes des récents
(`*[[King]] ''(cover)''`).

## Chiffres clés du livrable

- Wiki EN : résumé long sur **1193 / 1193** chapitres, complété **~70 min** après la sortie
- Wiki FR : plus aucun résumé depuis le chapitre 1188 (12 juillet 2026)
- Wiki JA : 369 articles, aucune page de chapitre
- Un modèle qui ne prédit rien obtient **98,57 % d'accuracy** — la métrique doit changer
- Baseline de persistance : **53 % de F1 micro**. Plafond atteignable : **85 %**

## Licence des données

Le contenu du wiki Fandom est sous licence CC BY-SA. Usage académique avec
attribution. Le script envoie un `User-Agent` identifiant le projet et limite
son débit.
