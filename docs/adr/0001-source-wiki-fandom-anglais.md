# ADR 0001 — Source de données : le wiki Fandom anglais

- **Statut :** accepté
- **Date de la mesure :** 16 septembre 2026 · **Révision :** 26 octobre 2026 (branche `architecture`)
- **Remplace :** `onepiece-faisabilite/faisabilite-etat-de-lart.md` (étude de faisabilité de la semaine 1)

## Décision

**Le corpus du projet provient exclusivement du wiki One Piece anglais**, lu via son API MediaWiki publique (`https://onepiece.fandom.com/api.php`). Les sources françaises et japonaises sont écartées, pas reléguées au rang de complément : aucune d'elles n'apporte de donnée que le wiki anglais n'a pas déjà, plus tôt et plus complète.

C'est cette source qui alimente les couches bronze (wikitexte brut archivé) et silver (un `.md` par chapitre) produites par `guess_arc.ingestion`.

## Contexte

Le projet a besoin, pour chaque chapitre publié, d'un texte décrivant ce qui s'y passe et des entités présentes, sans trou dans la série et disponible rapidement après la sortie hebdomadaire. Trois candidats naturels : les wikis Fandom anglais, français et japonais, plus l'écosystème japonais hors Fandom.

L'étude de faisabilité initiale tirait aussi d'autres conclusions (taxonomie de tags dérivée de la table des personnages, métriques, baselines, plan sur 8 semaines). La taxonomie simple est abandonnée au profit d'une architecture séquentielle à venir. Ces sections ne sont donc pas reprises ici et restent consultables dans l'historique Git. Seule la décision sur la source reste valable, et elle est indépendante du modèle qui consommera la donnée.

## Benchmark des sources

Mesures faites le 16 septembre 2026 sur les 1193 chapitres alors parus, via les API MediaWiki des trois wikis.

| Source | Chapitres couverts | Résumé long exploitable | Liste de personnages | Latence après sortie | Contributeurs actifs |
| --- | --- | --- | --- | --- | --- |
| [Wiki EN](https://onepiece.fandom.com/wiki/Chapter_1193) | 1193 / 1193 | **1193 (100 %)** | 1193 (100 %) | **\~70 min** | 226 |
| [Wiki FR](https://onepiece.fandom.com/fr/wiki/Chapitre_1193) | 1193 / 1193 | 1176 (98,6 %) | partielle | 2 à 4 jours, puis plus rien | 23 |
| [Wiki JA](https://onepiece.fandom.com/ja/) | 0 / 1193 | 0 | 0 | — | 1 |

## Pourquoi le wiki anglais

**Couverture totale, sans trou.** Les 1193 chapitres ont un résumé long complet, une table des personnages et un label d'arc. Exemple : le chapitre 1190, vide côté français, fait 6 531 octets côté anglais, dont un résumé de 3 742 caractères.

**Structure stable, parsable sans scraping HTML.** Chaque page suit un gabarit fixe en wikitexte, lu de façon déterministe par `guess_arc.ingestion.parser` :

| Champ wiki | Disponibilité | Contenu |
| --- | --- | --- |
| `{{Chapter Box}}` | 1193 / 1193 | Titre, titre japonais, romanisation |
| `==Long Summary==` | **1193 / 1193** | 3 664 caractères en moyenne |
| `==Short Summary==` | 1151 / 1193 (96,5 %) | Résumé court, dense en entités |
| `===Characters===` | **1193 / 1193** | 22,7 personnages par chapitre en moyenne, groupés par faction, annotés `(cover)` / `(flashback)` |
| `===Chapter Notes===` | 1193 / 1193 | Puces d'événements factuels |
| `{{<Nom> Arc}}` | **1193 / 1193** | 33 arcs |

**La source structurée la plus rapide au monde.** Le chapitre 1193 est sorti le dimanche 13 septembre 2026 à 15 h 00 UTC. Sa page est passée de 585 à 8 013 octets entre 15 h 22 et 16 h 09 le même jour : résumé long, notes et table des personnages complets **69 minutes après la sortie**. Même schéma sur le 1192 (rempli en 3 h 30). Le wiki se comporte comme un flux structuré quasi temps réel, ce qui permet un cron hebdomadaire le dimanche soir.

**Communauté active, donc source pérenne.** 226 contributeurs actifs, 2 128 098 modifications, 8 134 articles, des révisions continues depuis le 29 novembre 2006.

**Juridiquement propre.** Contenu sous licence CC BY-SA : usage académique autorisé avec attribution. API publique sans clé ; le client envoie un `User-Agent` identifiant le projet et limite son débit (50 titres par requête, soit environ 24 appels pour tout l'historique).

## Pourquoi pas le wiki français

**Le wiki français n'est pas globalement mauvais : il a été abandonné récemment, et précisément là où le projet a besoin de lui.**

- Sur tout l'historique, seuls 17 chapitres sont des ébauches, mais **9 d'entre eux sont dans les 20 derniers**.
- **Plus aucun résumé depuis le chapitre 1188** (12 juillet 2026). Les pages 1189 à 1193 font 1 075 à 1 593 octets : l'infobox seule.
- Même avant cet arrêt, la latence était de **2 à 4 jours** après la sortie, contre environ 70 minutes en anglais.
- La liste des personnages n'y est que partielle.
- 23 contributeurs actifs contre 226 : l'écart de maintenance va continuer à se creuser.

Un modèle qui prédit le chapitre n+1 dépend avant tout des chapitres les plus récents. Une source dont les derniers chapitres sont vides ne peut pas servir de socle, et en complément elle n'apporterait que des résumés déjà présents, en mieux, dans la version anglaise. Elle est donc écartée, pas conservée comme champ secondaire.

## Pourquoi pas les sources japonaises

### Le wiki Fandom japonais n'existe pas en pratique

| Indicateur | Wiki EN | Wiki FR | Wiki JA |
| --- | --- | --- | --- |
| Articles | 8 134 | 7 928 | **369** |
| Modifications totales | 2 128 098 | 1 464 726 | **4 932** |
| Contributeurs actifs | 226 | 23 | **1** |
| Plus ancienne révision observée | 29 nov. 2006 | 21 mai 2009 | 26 nov. 2010 |

- **Aucune page de chapitre n'a jamais été créée** : il n'y a rien à récupérer, même partiellement. Les articles existants sont des dates du calendrier (`11月23日`, `12月25日`) et des personnages secondaires (`Mr.5`, `Dr.くれは`).
- **C'est un wiki abandonné, pas un wiki jeune.** Il existe depuis près de seize ans, compte 430 fois moins de modifications que la version anglaise et n'a reçu que cinq modifications entre février et août 2026.
- Sur les quatre comptes actifs en 2026, un seul porte un pseudonyme japonais.

Ce vide mesure l'absence des fans japonais sur Fandom, qui est une plateforme anglophone, et non l'absence d'activité japonaise. Le fandom japonais écrit ailleurs (atwiki, Seesaa Wiki, ニコニコ大百科, ピクシブ百科事典, blogs de 考察). Ces sources ont donc été évaluées elles aussi.

### Les sources japonaises hors Fandom ne sont pas exploitables

Mesures du 16 septembre 2026, chapitre 1193 sorti le 13 septembre à 15 h 00 UTC :

| Source | Nature | Publication du 1193 | Écart à la sortie |
| --- | --- | --- | --- |
| [Wiki Fandom EN](https://onepiece.fandom.com/wiki/Chapter_1193) | Wiki structuré | 13/09, 16 h 09 UTC | **+1 h 09** |
| [onepiece-log.com](https://onepiece-log.com/blog-entry-3000.html) | Blog 感想/考察 | 07/09 05 h 30 JST *(ch. 1192)* | +5 h 30 |
| [hellominju.com](https://www.hellominju.com/2026/09/ONEPIECE1193.html) | Blog あらすじ + ネタバレ | 14/09 | +1 jour |
| [yasaoblog.fun](https://yasaoblog.fun/onepiece/netabare/1193-netabare/) | Blog ネタバレ | 12/09, maj 14/09 | −1 jour |
| [dic.pixiv.net](https://dic.pixiv.net/) | Encyclopédie | page 第1193話 inexistante | — |
| [Wiki Fandom JA](https://onepiece.fandom.com/ja/) | Wiki | inexistant | — |

- **Pas de format structuré.** Ce sont des billets d'impressions et d'analyse, sans résumé canonique ni liste de personnages. Il faudrait réannoter à la main ce que le wiki anglais fournit déjà.
- **Ingestion fragile.** Les URL ne se déduisent pas du numéro de chapitre (`blog-entry-3000.html` pour le 1192, `onepiece991` en 2021 contre `ONEPIECE1178` en 2026, `/netabare/1193-netabare/`). Il faudrait un index maintenu à la main.
- **Aucune avance de parution officielle.** *One Piece* est publié en *simulpub* : le *Weekly Shōnen Jump* et Manga Plus sortent le chapitre **le même jour**, dimanche 15 h 00 UTC. L'hypothèse « les scans sortent d'abord au Japon » ne vaut plus depuis l'ère Manga Plus. Tous les blogs mesurés arrivent après le wiki anglais, sauf un.
- **La seule avance vient des fuites, pas de la langue.** Le seul blog en avance (d'un jour) reprend des spoilers, qui circulent 2 à 5 jours avant la sortie, en anglais comme en japonais. Ces sources rediffusent des scans piratés, ce qui est difficile à assumer dans un livrable académique, alors que le contenu Fandom est sous CC BY-SA et citable.
- **Cette avance n'a de toute façon pas de valeur pour la prédiction.** Le modèle prédit n+1 à partir des chapitres 1 à n. Connaître n deux jours plus tôt ne change pas la prédiction de n+1, qui sort sept jours après : cela avance seulement le moment où l'on peut évaluer une prédiction déjà faite.

## Conséquences

- **Une seule source, un seul parseur.** `guess_arc.ingestion` ne gère que le gabarit du wiki anglais. Il n'y a pas d'abstraction multi-source à maintenir.
- **Le bronze archive le wikitexte brut** : si le gabarit change ou si le parseur évolue, on régénère la silver sans re-scraper (`python -m guess_arc.ingestion --rebuild-silver`).
- **Cron hebdomadaire le dimanche soir**, après la sortie de 15 h UTC et le remplissage du wiki (1 à 3 h). En mode `--incremental`, seules les pages dont la révision a changé sont retraitées. Un chapitre dont le résumé long fait moins de 300 caractères est marqué incomplet et repassé la semaine suivante, ce qui couvre aussi les semaines de pause.
- **Attribution CC BY-SA** à mentionner dans tout livrable qui exploite le corpus.
- **Risque accepté :** dépendance à une seule communauté. Il est atténué par la taille de cette communauté (226 contributeurs actifs, 20 ans d'historique) et par l'archive bronze locale.
- **Option non retenue, laissée ouverte :** si le client veut exploiter un signal précoce issu des spoilers, celui-ci ne pourra servir **qu'à l'inférence, jamais à l'entraînement**, pour ne pas contaminer le corpus.

## Sources

- [API MediaWiki du wiki One Piece anglais](https://onepiece.fandom.com/api.php) — couverture, latences et tables de personnages, relevées le 16 septembre 2026
- [API MediaWiki du wiki One Piece français](https://onepiece.fandom.com/fr/api.php)
- [Wiki One Piece japonais](https://onepiece.fandom.com/ja/) — 369 articles, sans page de chapitre
- [Calendrier de parution One Piece, Popverse](https://www.thepopverse.com/comics-one-piece-manga-release-date-upcoming-chapters-new-shonen-jump-viz-time-next-issue) — dates de sortie des chapitres 1192 à 1194
- [One Piece Manga Release Schedule Explained, AnimeNagi](https://animenagi.com/one-piece-manga-release-schedule-explained-how-chapters-are-released/) — simulpub japonais/anglais, fenêtre de fuite mercredi–jeudi
- [When will One Piece Chapter 1191 spoilers arrive, Business Upturn](https://businessupturn.com/entertainment/when-will-one-piece-chapter-1191-spoilers-arrive-expected-leak-timeline-explained-2/) — chronologie des fuites
- [ワンピース.Log](https://onepiece-log.com/blog-entry-3000.html) — blog japonais, couverture depuis 2015
- [hellominju.com, chapitre 1193](https://www.hellominju.com/2026/09/ONEPIECE1193.html) — blog japonais あらすじ + ネタバレ
- [yasaoblog.fun, chapitre 1193](https://yasaoblog.fun/onepiece/netabare/1193-netabare/) — blog japonais de spoilers
