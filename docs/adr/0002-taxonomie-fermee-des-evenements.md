# ADR 0002 — Taxonomie fermée des événements, même extracteur pour les entrées et la vérité terrain

- **Statut :** accepté
- **Date :** 28 octobre 2026 (branche `data_event`)

## Décision

Chaque événement extrait d'un chapitre porte **un type choisi dans une liste fermée et versionnée** (la taxonomie des événements, 20 types en v1, plus `first_appearance` et `return` réservés à l'origine `wiki`) **et une description libre** d'une phrase. **Le même extracteur**, avec le même modèle, le même prompt, le même schéma et la même taxonomie, produit à la fois les événements d'entrée (chapitres 1 à t) et la vérité terrain (chapitre t+1).

## Pourquoi

- **Pas d'événements entièrement libres.** Le classifieur a besoin de classes fixes, et l'évaluation doit comparer des prédictions à des vérités : « Luffy punches Kaido » et « Luffy fights Kaido » ne se comparent pas en texte libre.
- **Pas de taxonomie seule, sans description.** Un passage complet coûte 10 à 25 h sur le serveur de l'école (1 appel par chapitre, 15 s de pause). La description libre permet de reclasser les événements si la taxonomie évolue, **sans rappeler le modèle**.
- **Même extracteur des deux côtés.** Les entrées et la cible vivent dans le même espace, donc le modèle peut apprendre des transitions entre événements. Changer d'outil pour la vérité terrain casserait cet alignement.

Cette taxonomie des événements n'a rien à voir avec l'ancienne taxonomie de tags dérivée de la table des personnages, abandonnée (ADR 0001).

## Conséquences

- **Règle d'or :** si le modèle, le prompt, le schéma ou la taxonomie changent, on relance **tous** les chapitres. Chaque sortie enregistre les versions utilisées.
- **Erreurs corrélées :** les erreurs systématiques de l'extracteur se retrouvent dans les entrées comme dans la cible. Un score élevé mesure l'accord avec l'extracteur, pas avec la réalité. Un jeu or annoté à la main (spec à part) devra mesurer l'écart.
- **Signal d'alerte :** si `other` dépasse 15 % des événements, il manque un type.
- **Événements déterministes en contrepoint :** première apparition, retour et K.O. sont calculés depuis les apparitions du wiki, sans LLM. Ils échappent donc à ce biais, et le K.O. sert de contrôle de l'extracteur.

## Options écartées

- **Texte libre, regroupé après coup** (clustering d'embeddings) : les classes ne sont pas stables d'un passage à l'autre et il est difficile de les définir pour l'évaluation.
- **Un outil différent pour la vérité terrain** (annotation humaine de tous les chapitres) : c'est hors de portée sur 1 196 chapitres, et l'espace des entrées ne serait plus aligné sur celui de la cible.
