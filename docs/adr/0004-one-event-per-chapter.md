# ADR 0004 — Un Event par chapitre

- **Statut :** accepté
- **Date :** 17 novembre 2026 (branche `events/chapter-context`, issue #116)

Un Event qui s'étend sur plusieurs chapitres (un combat, une poursuite, une fête) est extrait de nouveau dans chaque chapitre qui le montre, comme un Event à part entière, sans identifiant commun d'un chapitre à l'autre. Chaque Event porte une Event phase (`start`, `ongoing` ou `end`) que le LLM déduit du seul texte du chapitre. On fait ce choix parce que l'extracteur ne lit qu'un chapitre à la fois (un appel LLM par Long Summary, #114) et parce qu'un lien entre chapitres obligerait à apparier des Events extraits séparément, un appariement bruité qui deviendrait du bruit d'étiquette pour tout le modèle.

## Options écartées

- **Un Event multi-chapitres avec un identifiant stable** : demande un second passage qui relie les Events de t à ceux de t−1. Ses erreurs fusionneraient deux Events distincts ou en couperaient un, sans qu'on puisse les mesurer simplement.
- **Phase calculée a posteriori** (`start` si l'Event est absent de t−1) : dépend du même appariement, et rate les Events qui reprennent après une pause de plusieurs chapitres.

## Conséquences

- **Scoring** : un Event se compare au sein d'un chapitre (même Event type, mêmes Participants, mêmes Sources et Targets si orienté). Il n'y a pas d'Event à apparier entre chapitres. L'Event phase est notée comme un attribut des Events appariés.
- **Prédiction** : un Event `ongoing` au chapitre t est souvent encore là en t+1, donc facile à prédire. Les scores sont aussi publiés pour les seuls Events `start`, qui mesurent ce que le modèle anticipe vraiment.
- **Phase subjective** : `start` / `ongoing` / `end` repose sur le jugement du LLM. Un combat repris après trois chapitres sans en parler peut être noté `start` ou `ongoing`. Les validateurs jugent la phase, et ce désaccord se lit dans le kappa.
- **Pas d'historique d'Event** : l'état narratif (étape 5) qui veut la durée d'un Event la reconstruit à partir des Events des chapitres ≤ t, par Event type et Participants, sans lire d'identifiant.
- **Coût** : l'extracteur reste un appel par chapitre, sans état ; un chapitre peut être réextrait seul.
