# V_client — POC de Konrad (Koagne), projet "Pop Gamble"

Ce document résume ce que contient ce dossier, tel que livré par le client
(auteur du notebook : **Koagne**, Master Ingénierie IA & Data, juillet 2026),
avant qu'on ne s'en inspire pour notre propre pipeline MD → JSON.

## Contenu du dossier

| Fichier | Rôle | État réel constaté |
| --- | --- | --- |
| `PopGamble_Notebook_Etudiant.ipynb` | Le POC complet, documenté, en 28 cellules | Code fonctionnel mais les cellules de run (scraping, tagging, validation) sont **commentées** — jamais exécutées telles quelles en une fois |
| `chapters_raw.json` | Sortie du scraper (module 1) | **1100 chapitres**, non taggés (`tagged: false`, `taxonomy: null` partout) |
| `chapters_tagged.json` | Sortie du tagger LLM (module 3) | **766 chapitres tagués** sur les 1100 (~70%), chapitres 1 à 1100, avec des trous irréguliers (146 gaps — chapitres jamais retentés après échec) |
| `pop_gamble_analysis.png` | Figure générée par le module 5 (base rates, cliffhangers, confidence) | Présente |
| `.env` | Clé API Anthropic | ⚠️ **Contient une vraie clé API en clair** (`ANTHROPIC_API_KEY`). Ajoutée au `.gitignore` du repo pour ne jamais être commitée. À faire régénérer côté client dès que possible puisqu'elle a circulé dans un dossier partagé. |

`base_rates.json`, mentionné dans le notebook comme sortie du module 5, n'est **pas présent** — jamais sauvegardé sur disque.

## Objectif produit visé par Konrad

**Pop Gamble** : une plateforme communautaire où les utilisateurs prédisent les
événements du prochain chapitre One Piece et reçoivent un **score
d'improbabilité** (`score = 1 / P(événement) × 100`) — prédire un événement
rare rapporte plus de points qu'un événement fréquent.

## Pipeline en 5 modules

1. **Scraping** (`scrape_chapter`, `run_scraper`) — API MediaWiki de Fandom (pas de BeautifulSoup, pas de HTML direct → 403 sinon). Parsing regex de `title`, `arc`, `summary` (Short Summary → Long Summary → Synopsis, premier qui dépasse 50 caractères), `characters_mentioned`. Sauvegarde incrémentale tous les 10 chapitres, reprise par checkpoint (`resume=True`).
2. **Taxonomie + Prompt Engineering** — voir détail ci-dessous.
3. **LLM Tagger** (`tag_chapter`, `run_tagger`) — appelle Claude (`claude-sonnet-4-6`) en zero-shot par chapitre, parse le JSON retourné, valide la présence des deux niveaux de tags, calcule le coût (`input×0.003 + output×0.015 / 1000`), sauvegarde tous les 20 succès.
4. **Modèle prédictif hybride** — prédit les tags du chapitre N+1 à partir d'un contexte multi-échelle (taux sur les 3/10/50 derniers chapitres + global + "momentum" = taux_3ch − taux_10ch, pour corriger le biais de sur-pondération de l'actualité récente) + les 5 derniers résumés complets. Validation incrémentale sans fuite de données sur 12 checkpoints (N = 10, 20, 30, 50, 75, 100, 150, 200, 300, 500, 750, 1000).
5. **Interface de scoring** — app Streamlit générée par le notebook (`app.py`, non présent dans ce dossier — généré au runtime) : explorateur de chapitres, page de prédiction, dashboard des base rates.

## La taxonomie (le cœur du sujet pour la suite)

Double niveau, **statique et fixe** (pas de génération dynamique de tags selon le contenu — tous les chapitres reçoivent les mêmes champs, avec `null`/`false`/liste vide si non pertinent).

### Niveau 1 — 52 tags globaux par chapitre

Catégories : Personnages (9), Pouvoirs & Combat (11), Narration (8), Lieux (3),
Factions (6), Lore (5), Gags récurrents Oda (6), Meta (2 : `confidence_score`,
`tagger_notes`).

Exemples de champs : `luffy_present`, `fight_occurs`, `devil_fruit_used`,
`gear5_activated`, `haki_types`, `flashback_present`, `revelation_major`,
`cliffhanger_type`, `tension_level` (1-10), `sea_region`, `yonko_present`,
`road_poneglyph_found`, `luffy_eats`, `sanji_nosebleed`.

Liste complète des 52 clés (cf. `TAXONOMY_SCHEMA` dans le notebook, cellule 11) :
`characters_present`, `main_character`, `luffy_present`, `straw_hats_count`,
`new_character_introduced`, `new_character_name`, `character_return`,
`character_death_present`, `character_death_flashback`,
`character_death_offscreen`, `character_death_name`, `fight_occurs`,
`fight_participants`, `fight_ends`, `fight_winner`, `devil_fruit_used`,
`devil_fruit_names`, `devil_fruit_awakening`, `gear5_activated`,
`new_technique_revealed`, `new_technique_name`, `haki_used`, `haki_types`,
`flashback_present`, `flashback_character`, `revelation_major`,
`revelation_description`, `new_arc_starts`, `arc_ends`, `new_alliance_formed`,
`cliffhanger_type`, `chapter_mood`, `tension_level`, `locations`,
`location_change`, `sea_region`, `marines_present`, `yonko_present`,
`yonko_name`, `shichibukai_present`, `world_government_present`,
`revolutionary_army_present`, `road_poneglyph_found`,
`ancient_weapon_mentioned`, `bounty_revealed`, `bounty_character`,
`will_of_d_mentioned`, `luffy_eats`, `usopp_lies_or_runs`, `sanji_nosebleed`,
`nami_hits_someone`, `robin_dark_humor`, `chopper_called_tanuki`,
`color_spread`, `confidence_score`, `tagger_notes`, `characters_detailed`
(liste — voir niveau 2).

### Niveau 2 — 15 tags par personnage présent (`characters_detailed`)

`name`, `role` (protagonist/antagonist/villain/ally/neutral), `affiliation`,
`fight_participant`, `fight_winner`, `health_state`
(healthy/injured/critical/defeated/dead), `technique_revealed`, `power_used`,
`haki_used`, `has_flashback`, `emotional_state`
(determined/enraged/sad/scared/joyful/calm/neutral), `major_decision`,
`dies`, `death_type` (present/flashback/offscreen), `arc_goal_progress`
(none/progressing/achieved/failed).

### Génération des tags

Un seul appel LLM par chapitre (`tag_chapter`), zero-shot, sans few-shot
examples. Le prompt système impose : JSON strict sans markdown autour, ne
jamais inventer une info absente du résumé, utiliser un `confidence_score`
pour indiquer le niveau d'incertitude (100 = résumé complet et non ambigu,
70-99 = quelques inférences, <70 = résumé court/ambigu). Le modèle reçoit
uniquement le **résumé du chapitre** (Short/Long Summary du wiki) + la liste
de personnages détectés par le scraper — pas le texte intégral du chapitre.

## Résultats et limites déclarés par Konrad

- 94% de précision sur les champs booléens en validation manuelle (chapitre 111, 17/18 corrects)
- Confidence score moyen : 76/100 sur les 220 premiers chapitres
- Coût réel : ~$0.034/chapitre (**$31.35 dépensés au total pour les 766 chapitres tagués**, modèle `claude-sonnet-4-6-v3`)
- Limites qu'il identifie lui-même : résumés wiki parfois trop courts → confidence basse ; biais de momentum narratif (corrigé partiellement par le vecteur multi-échelle) ; taxonomie statique qui ne capture pas de nouveaux patterns narratifs sans revue manuelle ; distinction mort présente/flashback/hors-champ nécessaire (ex. Gol D. Roger chapitre 1, mort en flashback mal classée en v1/v2)

## Ce qui manque / à améliorer pour notre pipeline ML

- **Couverture incomplète** : 766/1100 tagués, 146 trous jamais retentés, rien après le chapitre 1100 (notre propre pipeline `onepiece-faisabilite` couvre déjà 1193 chapitres avec retry automatique sur incomplet — cf. `onepiece_ingest.py`).
- **Taxonomie figée et manuelle** : les 52+15 champs sont écrits en dur par Konrad ; aucun mécanisme pour ajouter/retirer un tag sans réécrire le prompt et retagger tout le corpus. À "dynamiser" comme demandé : rendre le schéma versionné/extensible plutôt que codé en dur dans un prompt.
- **Tagging depuis le résumé seul**, pas depuis le texte complet du chapitre ni la liste de personnages structurée (faction/on_panel) que notre propre scraper produit déjà dans le front-matter des `.md` silver — on a une base plus riche à exploiter.
- **Pas de schéma de validation formel** (JSON Schema, pydantic...) : la validation actuelle se limite à deux `assert` (`luffy_present` et `characters_detailed` présents).
- **Clé API en clair dans le repo partagé** — sécurité à corriger avant toute réutilisation du `.env`.
- **Aucune donnée réellement utilisable pour du ML supervisé en l'état** : le POC reste exploratoire (cellules de run commentées, `base_rates.json` jamais généré, `app.py` jamais committé).
