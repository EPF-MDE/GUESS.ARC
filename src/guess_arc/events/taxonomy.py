"""Taxonomie des événements v1 (ADR 0002).

Les 20 types que le modèle peut émettre, avec la définition donnée dans le
prompt système. `first_appearance` et `return` sont réservés à l'origine `wiki`
et n'en font pas partie : le modèle ne doit pas les produire.
"""

LLM_EVENT_TYPES = {
    "combat": "characters fight or clash physically; one event per fight, however many blows",
    "defeat": "a character is beaten, knocked out or forced to give up a fight",
    "death": "a character dies in the chapter",
    "injury": "a character is seriously wounded without being defeated",
    "capture": "a character is captured, imprisoned or taken hostage",
    "escape_rescue": "a character escapes from captivity or danger, or is rescued",
    "recruitment": "a character joins a crew or group, or is asked to and accepts",
    "departure": "a character or group leaves a place, a crew or a group",
    "arrival": "a character or group reaches a new place",
    "alliance": "characters or groups agree to work together",
    "betrayal": "a character turns against an ally or their own group",
    "revelation": "hidden information comes to light: an identity, a past, a secret, a plan",
    "power_reveal": "an ability, technique, Devil Fruit power or transformation is shown "
                    "or explained",
    "reunion": "characters who were separated meet again",
    "status_change": "a character's rank, title, bounty, role or affiliation changes",
    "declaration": "a character states a vow, goal, dream, challenge or decision",
    "acquisition": "an object, treasure or key piece of information is obtained or lost",
    "celebration": "a party, feast or banquet",
    "world_reaction": "the outside world learns of or reacts to events: newspaper, "
                      "broadcast, World Government",
    "other": "an important narrative fact that fits no other type",
}
