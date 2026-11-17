# GUESS.ARC

Prédiction des Events du chapitre n+1 de *One Piece* à partir des chapitres 1 à n (texte, Events, graphe de connaissances temporel).

## Récit

**Arc**:
Collection de chapitres connectés entre eux, qui racontent une histoire complète avec une intrigue, des enjeux et un dénouement propres (Arlong Park Arc, Wano Country Arc). Chaque chapitre appartient à un seul Arc, lu dans le front-matter silver.
_Avoid_: saga, partie

## Apparitions

**Appearance**:
Présence d'un Character *on panel* dans un chapitre.
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

## Représentation du texte

**Chapter embedding**:
Vecteur de taille fixe qui représente le sens du Long Summary d'un chapitre, produit par un encodeur pré-entraîné gelé. Il ne dépend que du texte du chapitre t, jamais d'un autre chapitre.
_Avoid_: vecteur (comme synonyme de Chapter embedding ; le mot reste correct pour la notion mathématique), encoding, représentation

**Chunk**:
Texte encodé en un seul vecteur pour former le Chapter embedding : une Scene entière, ou, si elle dépasse la fenêtre de l'encodeur, l'une des fenêtres qui se chevauchent et la découpent.
_Avoid_: morceau, segment, passage

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

## Événements

**Event**:
Fait narratif survenu dans un chapitre, décrit par un Event type et ses Participants. C'est ce que le modèle cherche à prédire pour le chapitre n+1.
_Avoid_: événement nommé (Buster Call, Levely : ce sont des Entities), action, fait

**Event type**:
Catégorie d'un Event (combat, alliance…), prise dans une liste fermée. Chaque Event type est soit orienté (des Sources vers des Targets), soit non orienté, une fois pour toutes.

**Participant**:
Entity de Registry(t) impliquée dans un Event, désignée par les Aliases connus au chapitre t (un Disguise reste un Participant distinct jusqu'à sa Revelation). Un Event a de 1 à n Participants. Dans un Event orienté, chaque Participant est soit Source, soit Target.
_Avoid_: acteur, argument

**Source** / **Target**:
Les deux rôles des Participants d'un Event orienté : celui qui agit et celui qui subit (vainqueur → vaincu, traître → trahi). 1 à n de chaque côté.

**Event phase**:
Moment d'un Event qui s'étend sur plusieurs chapitres, tel que le chapitre le montre : start, ongoing ou end.

**Flashback event**:
Event raconté au chapitre t mais situé dans le passé de l'histoire. Signal pour l'état de l'histoire, jamais une cible de prédiction ni une vérité terrain.
