import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from onepiece_ingest import parse_characters, parse_chapter, strip_markup

# Extrait réel du chapitre 500 (style ancien : annotations en parenthèses nues)
ch500 = """
{| class="CharTable"
! colspan="2"|[[Pirates]]
! [[World Government]]
! colspan="2"|Others
|-
|
;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Nami]]
*[[Usopp]]
|
;[[Heart Pirates]]
*[[Trafalgar D. Water Law|Trafalgar Law]]
*[[Bepo]]
----
;Other
*[[Stansen]]
|
;[[CP9]]
*[[Kalifa]] (cover)
|}
"""

# Extrait réel du chapitre 1193 (style récent : ''(cover)'' / ''(flashback)'')
ch1193 = """
{|class="CharTable"
!colspan="2"|[[Pirate]]s
|-
|
;[[Straw Hat Pirates]]
*[[Monkey D. Luffy]]
*[[Roronoa Zoro]]
|
;[[Beasts Pirates]]
*[[King]] ''(cover)''
|
;[[Elbaph]]
*[[Harald]] ''(flashback)''
*[[Loki]]
|}
"""

a = parse_characters(ch500)
b = parse_characters(ch1193)
print("ch500 :", json.dumps(a, ensure_ascii=False, indent=None))
print()
print("ch1193:", json.dumps(b, ensure_ascii=False, indent=None))
print()

def check(label, cond):
    print(("PASS " if cond else "FAIL ") + label)

check("ch500 : 7 personnages", len(a) == 7)
check("ch500 : lien avec pipe resolu en 'Trafalgar D. Water Law'",
      any(c["name"] == "Trafalgar D. Water Law" for c in a))
check("ch500 : Kalifa (cover) marquee hors-panel",
      next(c for c in a if c["name"] == "Kalifa")["on_panel"] is False)
check("ch500 : Luffy on_panel",
      next(c for c in a if c["name"] == "Monkey D. Luffy")["on_panel"] is True)
check("ch500 : faction Straw Hat Pirates sur Nami",
      next(c for c in a if c["name"] == "Nami")["faction"] == "Straw Hat Pirates")
check("ch500 : groupe sans lien ';Other' capture",
      next(c for c in a if c["name"] == "Stansen")["faction"] == "Other")
check("ch1193 : King ''(cover)'' hors-panel",
      next(c for c in b if c["name"] == "King")["on_panel"] is False)
check("ch1193 : Harald ''(flashback)'' hors-panel",
      next(c for c in b if c["name"] == "Harald")["on_panel"] is False)
check("ch1193 : Loki on_panel",
      next(c for c in b if c["name"] == "Loki")["on_panel"] is True)
check("ch1193 : 5 personnages", len(b) == 5)

# parse_chapter de bout en bout
page = """{{Chapter Box
| title = Still Practicing
| jname = 練習中
}}
'''Chapter 1193''' is titled "Still Practicing".

==Short Summary==
[[Monkey D. Luffy|Luffy]] and [[Loki]] attack [[Nerona Imu|Imu]].

==Long Summary==
""" + ("Luffy and [[Loki|Loki's]] combined attack blasts Imu into the tree. " * 8) + """

==Quick References==
===Chapter Notes===
*[[Roronoa Zoro|Zoro]] resumes his battle.
**Sommers is injured.
===Characters===
""" + ch1193 + """
==Arc Navigation==
{{Elbaph Arc}}
"""
c = parse_chapter(1193, page, 123, "2026-09-13T16:09:21Z")
print()
check("parse_chapter : arc = Elbaph Arc", c.arc == "Elbaph Arc")
check("parse_chapter : titre", c.title == "Still Practicing")
check("parse_chapter : complete=True", c.complete is True)
check("parse_chapter : 2 notes", len(c.notes) == 2)
check("parse_chapter : liens retires du resume", "[[" not in c.long_summary)
check("parse_chapter : 5 personnages", len(c.characters) == 5)
check("parse_chapter : short summary lisible",
      c.short_summary == "Luffy and Loki attack Imu.")
