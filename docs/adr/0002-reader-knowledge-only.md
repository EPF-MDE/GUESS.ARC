# ADR 0002 — KG(t) ne contient que ce que le lecteur sait au chapitre t

- **Statut :** accepté
- **Date :** 28 octobre 2026 (branche `exctraction/entities`)

Le graphe de connaissances au chapitre t ne contient que des faits issus des chapitres ≤ t, chacun daté de sa Revelation (le chapitre où le lecteur l'apprend), et non de sa date dans l'histoire. Les seuls faits considérés comme invariants sont l'Entity type et la hiérarchie des Places (île ⊂ mer). On applique cette règle parce que le système doit fonctionner en conditions réelles, sur des chapitres dont il ignore la suite : un modèle entraîné sur des données omniscientes serait évalué de façon trop optimiste et se comporterait différemment une fois en production.

## Conséquences

- `characters.json`, `islands.json` et `devil_fruits.json` ne servent qu'aux Entity types, aux Aliases et à la hiérarchie des Places. Leurs attributs d'état (affiliation, status, bounty, current_ruler, relationships) n'entrent pas dans KG(t), parce qu'ils décrivent l'état de l'histoire au dernier chapitre.
- Les liens de parenté ne sont pas invariants : Luffy n'est le fils de Dragon qu'à partir du chapitre 432.
- Les liens du wiki résolvent les Disguises dès le premier chapitre (`[[Denjiro|Kyoshiro]]`). Pour l'historique, une liste de Disguises vérifiée à la main sépare l'Alias et le Canonical name jusqu'à la Revelation. Pour les nouveaux chapitres, une réassignation d'Alias détectée automatiquement propose une Revelation, qu'un humain valide.
- La bronze devient append-only. KG(t) est construit à partir de la première révision complète de chaque chapitre (environ 1 h après sa sortie), pour que les éditions ultérieures du wiki ne réécrivent pas le passé. Pour les 1193 chapitres déjà ingérés, on utilise la révision actuelle : le texte peut contenir des formulations rétrospectives, ce qui est une limite acceptée et documentée.
- Les Disguises ne concernent que les Characters en v1. Pour les autres Entity types, la fuite est acceptée.
