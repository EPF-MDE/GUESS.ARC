# GUESS.ARC

Prédire ce qui se passe dans le chapitre t+1 de *One Piece* à partir des chapitres 1 à t, lus via les résumés du wiki Fandom anglais.

## Langage

### Corpus

**Chapitre** :
Une page de chapitre du wiki, identifiée par son numéro, avec son titre, son arc, ses résumés court et long, ses notes et sa table des personnages.
_À éviter_ : épisode, page

**Arc** :
Le label d'arc narratif que le wiki attribue à un chapitre (par exemple « Loguetown Arc »).

**Apparition** :
La présence d'un personnage dans la table des personnages d'un chapitre, accompagnée des annotations du wiki (`cover`, `flashback`, `mentioned`, `dream`, `K.O.`…).
_À éviter_ : mode

**Présent à l'image** :
Une apparition sans annotation qui l'exclut du présent du récit (ni `cover`, ni `flashback`, ni `mentioned`, ni `dream`). Un personnage présent uniquement en couverture ne participe pas au chapitre.
_À éviter_ : présent, on panel

### Événements

**Événement** :
Un fait narratif qui se produit dans un chapitre donné, rattaché à un type d'événement et appuyé par le texte de ce chapitre. Il y a au plus un événement par couple (type, ensemble de participants) et par chapitre : trois coups de Luffy sur Kaido font un seul `combat`.
_À éviter_ : tag, label

**Participant** :
Un personnage impliqué dans un événement, avec son rôle (agent, cible, autre).

**Origine** :
La provenance d'un événement : `llm` s'il est extrait du texte par le modèle, `wiki` s'il est déduit de façon déterministe des apparitions (première apparition, retour, K.O.).
_À éviter_ : source (le mot désigne déjà la section du chapitre d'où vient la preuve)

**Présenté** :
Un personnage est présenté au lecteur quand il est présent à l'image ou montré en flashback. Une simple mention ou une apparition en couverture ne compte pas.

**Première apparition** :
Le premier chapitre où un personnage est présenté, y compris si c'est en flashback.
_À éviter_ : introduction, debut

**Retour** :
Le premier chapitre d'un arc où un personnage est présent à l'image, s'il était absent de l'arc précédent et a déjà été présenté auparavant.
_À éviter_ : réapparition

**Événement en flashback** :
Un événement raconté au chapitre t mais situé dans le passé du récit. Il est conservé et marqué comme tel, et il ne compte pas comme un fait du présent.

**Cover story** :
Une mini-histoire racontée en page de couverture, sur une chronologie parallèle au récit. Ses faits ne sont pas des événements en v1.

**Type d'événement** :
La classe d'un événement, choisie dans la taxonomie des événements (par exemple `combat`, `revelation`).
_À éviter_ : catégorie, tag

**Taxonomie des événements** :
La liste fermée et versionnée des types d'événements. À ne pas confondre avec l'ancienne taxonomie de tags dérivée de la table des personnages, qui a été abandonnée (ADR 0001).

**Extraction des événements** :
L'étape qui transforme un chapitre en sa liste d'événements. Le même outil sert d'entrée au modèle (chapitres 1 à t) et produit la vérité terrain (chapitre t+1).
_À éviter_ : annotation, tagging

**Vérité terrain** :
Les événements extraits du chapitre t+1, auxquels on compare les prédictions.
_À éviter_ : label, cible
