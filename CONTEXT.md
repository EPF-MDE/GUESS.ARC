# GUESS.ARC

Prédiction du casting du chapitre n+1 de *One Piece* à partir d'un graphe de connaissances temporel construit sur les chapitres 1 à n.

## Apparitions

**Appearance**:
Présence d'un Character *on panel* dans un chapitre. C'est la seule forme de présence que le modèle cherche à prédire.
_Avoid_: tag, présence, apparition (sans précision)

**Recall**:
Présence d'un Character dans un chapitre uniquement en flashback. Signal faible, distinct d'une Appearance.
_Avoid_: flashback appearance

**Cover appearance**:
Présence d'un Character uniquement dans la page de couverture (cover story) d'un chapitre. Signal faible, distinct d'une Appearance.

**Cast**:
Ensemble des Characters ayant une Appearance dans un chapitre donné.
_Avoid_: panier, basket, tags du chapitre

**Scene**:
Paragraphe du Long Summary d'un chapitre. Unité de lieu et d'action dans le texte.
_Avoid_: paragraphe, passage

## Entités

**Entity**:
Être, collectif, lieu ou chose nommé de l'univers, identifié par son Canonical name.

**Canonical name**:
Titre de la page du wiki anglais vers laquelle pointent les liens de l'Entity. Identifiant unique de l'Entity.
_Avoid_: id, nom

**Alias**:
Toute forme de surface par laquelle une Entity est désignée dans un texte (« Whitebeard » pour Edward Newgate).
_Avoid_: surnom, mention

**Registry(t)**:
Ensemble des Entities connues du lecteur au chapitre t, avec leur Entity type et les Aliases déjà utilisés à ce chapitre. Une Entity n'y entre qu'à partir de sa première Mention ou Appearance.
_Avoid_: dictionnaire, gazetteer, liste d'entités

**Entity type**:
Catégorie unique et fixe d'une Entity, choisie selon son rôle principal dans l'histoire : Character, Group, Place, Ship, Devil Fruit, Weapon, Object, ou Unknown faute de mieux.

**Character**:
Personne ou créature dotée d'une volonté propre (Luffy, Laboon, Zeus).

**Group**:
Collectif dont les membres agissent ensemble : équipage, organisation, famille, armée.
_Avoid_: faction, crew, affiliation

**Place**:
Lieu nommé, de la mer au bâtiment (New World, Wano Country, Onigashima).
_Avoid_: location, island

**Ship**:
Navire nommé (Thousand Sunny, Moby Dick).

**Devil Fruit**:
Fruit du démon précis (Gomu Gomu no Mi), jamais le concept générique.

**Weapon**:
Arme nommée pouvant changer de détenteur au fil de l'histoire (Shusui, Enma, Kabuto).
_Avoid_: sword, meito

**Object**:
Chose nommée qui n'est ni un Ship, ni un Devil Fruit, ni une Weapon (Poneglyph, Den Den Mushi).

## Connaissance du lecteur

**Revelation**:
Chapitre à partir duquel le lecteur apprend un fait (un lien de parenté, une identité cachée). Un fait n'existe pour le modèle qu'à partir de sa Revelation, quelle que soit sa date dans l'histoire.
_Avoid_: reveal date, spoiler

**Disguise**:
Alias sous lequel un Character est présenté au lecteur comme une personne distincte, jusqu'à sa Revelation (Kyoshiro pour Denjiro, Miss All Sunday pour Nico Robin). Avant la Revelation, le Disguise est traité comme une Entity à part entière.
_Avoid_: fausse identité, alter ego

**Mention**:
Occurrence d'une Entity dans une Scene, sous l'un de ses Aliases. Une Mention n'implique pas la présence : un Character peut être mentionné sans avoir d'Appearance.
_Avoid_: occurrence, citation

**Title**:
Rang ou statut porté par un Character à un moment donné (Admiral, Warlord, World Noble). Attribut, jamais une Entity.
_Avoid_: rank

**Concept**:
Notion générique de l'univers (Pirate, Haki, le Devil Fruit en général). Jamais une Entity.
