"""Quality ledger (quality/ folder): validation, replay, rendering, regeneration.

Every test goes through guess_arc.quality.ledger only, on fixture folders built
in a temp directory. The last class checks the real, committed quality/ folder:
that is the CI guard.
"""
import datetime as dt
import tempfile
import unittest
from pathlib import Path

import yaml

from guess_arc.paths import QUALITY_DIR
from guess_arc.quality import ledger

D = dt.date


def proposed(**overrides):
    entry = {
        "date": D(2026, 10, 19),
        "by": "team",
        "type": "proposed",
        "channel": "sprint planning",
        "text": "Proposed at sprint planning.",
        "title": "Schema with ADRs",
        "statement": "The taxonomy is defined in a documented schema.",
        "characteristic": "Maintainability",
        "metric": "100 % of the structural choices have an ADR.",
        "why": "The client must be able to extend the taxonomy.",
        "verification": "Check the schema document and the ADRs.",
        "when": "Before delivery",
        "owner": "Team",
        "delivery": D(2026, 10, 23),
        "recurring": False,
    }
    entry.update(overrides)
    return entry


def client(type_, **fields):
    entry = {"date": D(2026, 10, 23), "by": "client", "type": type_,
             "channel": "client meeting", "text": "Konrad agreed."}
    entry.update(fields)
    return entry


def verified(result="✅", **fields):
    entry = {"date": D(2026, 10, 22), "by": "team", "type": "verified",
             "channel": "sprint", "text": "Checked.", "result": result,
             "evidence": "Commit `abc1234`."}
    entry.update(fields)
    return entry


def thread(number, *entries):
    return {"id": f"REQ-{number}", "entries": list(entries)}


DELIVERIES = {
    "deliveries": [
        {
            "date": D(2026, 10, 23),
            "theme": "Taxonomy POC",
            "thread": [{"date": D(2026, 10, 23), "by": "client", "text": "Satisfied."}],
        }
    ]
}


class LedgerTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "quality"
        (self.folder / "requirements").mkdir(parents=True)

    def write(self, *threads, deliveries=DELIVERIES, canonical=True):
        """Write a fixture folder; by default rewritten in canonical form first."""
        for data in threads:
            path = self.folder / "requirements" / f"{data['id']}.yaml"
            path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                            encoding="utf-8")
        (self.folder / "deliveries.yaml").write_text(
            yaml.safe_dump(deliveries, sort_keys=False, allow_unicode=True), encoding="utf-8")
        if canonical:
            ledger.canonicalise(self.folder)

    def assertReports(self, errors, *fragments):
        for fragment in fragments:
            self.assertTrue(any(fragment in e for e in errors),
                            f"no error mentions {fragment!r}: {errors}")


class TestValidate(LedgerTestCase):
    def test_well_formed_folder_has_no_errors(self):
        self.write(thread(1, proposed(), verified(), client("accepted"),
                          client("signed-off", result="✅")))
        self.assertEqual(ledger.validate(self.folder), [])

    def test_non_canonical_formatting_is_reported_and_canonicalise_fixes_it(self):
        self.write(thread(1, proposed()))
        path = self.folder / "requirements" / "REQ-1.yaml"
        # Hand edit: a comment, and a key moved out of its canonical place.
        text = path.read_text(encoding="utf-8")
        text = "# hand edit\n" + text.replace("  title: Schema with ADRs\n", "") \
            .replace("  recurring: false\n", "  recurring: false\n  title: Schema with ADRs\n")
        path.write_text(text, encoding="utf-8")

        self.assertReports(ledger.validate(self.folder), "REQ-1.yaml", "canonical")
        self.assertEqual(ledger.canonicalise(self.folder), [path])
        self.assertEqual(ledger.validate(self.folder), [])
        self.assertNotIn("#", path.read_text(encoding="utf-8"))

    def test_unknown_entry_type_is_reported(self):
        self.write(thread(1, proposed(), client("approved")))
        self.assertReports(ledger.validate(self.folder), "REQ-1", "unknown entry type 'approved'")

    def test_missing_required_field_for_a_type_is_reported(self):
        no_evidence = verified()
        del no_evidence["evidence"]
        no_metric = proposed()
        del no_metric["metric"]
        self.write(thread(1, no_metric, no_evidence, client("signed-off")))
        self.assertReports(ledger.validate(self.folder),
                           "proposed: missing field 'metric'",
                           "verified: missing field 'evidence'",
                           "signed-off: missing field 'result'")

    def test_field_not_allowed_for_a_type_is_reported(self):
        self.write(thread(1, proposed(), client("accepted", result="✅")))
        self.assertReports(ledger.validate(self.folder), "accepted: unexpected field 'result'")

    def test_invalid_result_is_reported(self):
        self.write(thread(1, proposed(), verified(result="OK")))
        self.assertReports(ledger.validate(self.folder), "result 'OK'")

    def test_wrong_author_for_a_type_is_reported(self):
        self.write(thread(1, proposed(), client("accepted", by="team")))
        self.assertReports(ledger.validate(self.folder), "accepted: must be by client")

    def test_proposed_not_first_is_reported(self):
        self.write(thread(1, client("accepted", date=D(2026, 10, 18)), proposed()))
        self.assertReports(ledger.validate(self.folder), "first entry must be 'proposed'")

    def test_repeated_proposed_is_reported(self):
        self.write(thread(1, proposed(), proposed(date=D(2026, 10, 20))))
        self.assertReports(ledger.validate(self.folder), "'proposed' appears more than once")

    def test_dates_out_of_order_are_reported(self):
        self.write(thread(1, proposed(), client("accepted"), verified(date=D(2026, 10, 20))))
        self.assertReports(ledger.validate(self.folder), "entry 3", "before the previous entry")

    def test_duplicate_ids_are_reported(self):
        self.write(thread(1, proposed()))
        twin = self.folder / "requirements" / "REQ-2.yaml"
        twin.write_text((self.folder / "requirements" / "REQ-1.yaml").read_text(encoding="utf-8"),
                        encoding="utf-8")
        self.assertReports(ledger.validate(self.folder), "duplicate id REQ-1")

    def test_invalid_characteristic_is_reported(self):
        self.write(thread(1, proposed(characteristic="Performance")))
        self.assertReports(ledger.validate(self.folder), "characteristic 'Performance'")

    def test_invalid_date_is_reported(self):
        self.write(thread(1, proposed(date="23/10")))
        self.assertReports(ledger.validate(self.folder), "date")

    def test_invalid_meeting_in_deliveries_is_reported(self):
        self.write(thread(1, proposed()),
                   deliveries={"deliveries": [{"date": D(2026, 10, 23), "thread": []}]})
        self.assertReports(ledger.validate(self.folder), "deliveries.yaml", "missing field 'theme'")

    def test_canonical_form_has_no_anchors_and_one_line_per_long_value(self):
        same_day = D(2026, 10, 23)
        long_metric = " ".join(["A metric long enough to be folded by a YAML dumper."] * 4)
        self.write(thread(1, proposed(date=same_day, delivery=same_day, metric=long_metric)))
        text = (self.folder / "requirements" / "REQ-1.yaml").read_text(encoding="utf-8")
        self.assertNotIn("&id", text)
        self.assertIn(f"metric: {long_metric}\n", text)

    def test_multi_line_text_is_canonical_as_a_block(self):
        self.write(thread(1, proposed(text="Line one.\nLine two.\n")))
        text = (self.folder / "requirements" / "REQ-1.yaml").read_text(encoding="utf-8")
        self.assertIn("text: |\n", text)


class TestReplay(LedgerTestCase):
    def replayed(self, *entries, **proposed_overrides):
        self.write(thread(1, proposed(**proposed_overrides), *entries))
        self.assertEqual(ledger.validate(self.folder), [])
        [requirement] = ledger.replay(self.folder)
        return requirement

    def test_proposed_only_is_awaiting_client_and_open(self):
        req = self.replayed()
        self.assertEqual(req.id, "REQ-1")
        self.assertEqual(req.spec["metric"], "100 % of the structural choices have an ADR.")
        self.assertEqual(req.client_status, "awaiting client")
        self.assertEqual(req.latest_result, "⏳")
        self.assertTrue(req.open)
        self.assertTrue(req.current)

    def test_accepted_is_open_until_signed_off(self):
        req = self.replayed(client("accepted"))
        self.assertEqual(req.client_status, "accepted")
        self.assertTrue(req.open)

    def test_signed_off_ok_is_closed(self):
        req = self.replayed(verified(), client("accepted"), client("signed-off", result="✅"))
        self.assertEqual(req.client_status, "signed off ✅")
        self.assertEqual(req.latest_result, "✅")
        self.assertFalse(req.open)
        self.assertFalse(req.current)

    def test_signed_off_partial_stays_open(self):
        req = self.replayed(verified(result="⚠️"), client("accepted"),
                            client("signed-off", result="⚠️"))
        self.assertEqual(req.client_status, "signed off ⚠️")
        self.assertEqual(req.latest_result, "⚠️")
        self.assertTrue(req.open)

    def test_rejected_is_closed(self):
        req = self.replayed(client("rejected"))
        self.assertEqual(req.client_status, "rejected")
        self.assertFalse(req.open)
        self.assertFalse(req.current)

    def test_dropped_after_partial_sign_off_is_closed(self):
        req = self.replayed(verified(result="⚠️"), client("accepted"),
                            client("signed-off", result="⚠️"),
                            {"date": D(2026, 10, 23), "by": "team", "type": "dropped",
                             "channel": "client meeting", "text": "Route abandoned."})
        self.assertEqual(req.client_status, "dropped")
        self.assertEqual(req.latest_result, "⚠️")
        self.assertFalse(req.open)
        self.assertFalse(req.current)

    def test_dropped_carries_no_field(self):
        self.write(thread(1, proposed(), client("dropped", result="❌")))
        self.assertReports(ledger.validate(self.folder), "dropped: unexpected field 'result'")

    def test_latest_verification_wins(self):
        req = self.replayed(verified(result="❌", date=D(2026, 10, 20)), verified(result="✅"))
        self.assertEqual(req.latest_result, "✅")

    def test_recurring_signed_off_ok_stays_current(self):
        req = self.replayed(verified(), client("accepted"), client("signed-off", result="✅"),
                            recurring=True)
        self.assertFalse(req.open)
        self.assertTrue(req.current)

    def test_requirements_come_back_in_id_order(self):
        self.write(thread(10, proposed()), thread(2, proposed()))
        self.assertEqual([r.id for r in ledger.replay(self.folder)], ["REQ-2", "REQ-10"])


class TestRender(LedgerTestCase):
    def setUp(self):
        super().setUp()
        signed_ok = (verified(), client("accepted"), client("signed-off", result="✅"))
        self.write(
            thread(1, proposed(title="Closed one"), *signed_ok),
            thread(2, proposed(title="Partial one"), verified(result="⚠️"),
                   client("accepted"), client("signed-off", result="⚠️")),
            thread(3, proposed(title="Recurring one", recurring=True), *signed_ok),
            thread(4, proposed(title="Rejected one"), client("rejected")),
            thread(5, proposed(title="Awaiting one")),
        )
        self.requirements = ledger.replay(self.folder)

    def test_current_opens_with_generated_header_and_grading_grid(self):
        text = ledger.render_current(self.requirements)
        head = text.split("\n## ")[0]
        self.assertIn("do not edit", head)
        for row in ("| **Q1** |", "| **Q2** |", "| **Q3** |"):
            self.assertIn(row, head)

    def test_current_lists_exactly_the_current_requirements(self):
        text = ledger.render_current(self.requirements)
        listed = [line.split()[1] for line in text.splitlines() if line.startswith("## REQ-")]
        self.assertEqual(listed, ["REQ-2", "REQ-3", "REQ-5"])
        self.assertIn("100 % of the structural choices have an ADR.", text)
        self.assertIn("(requirements/REQ-2.yaml)", text)

    def test_overview_has_one_line_per_requirement_with_a_link_to_its_thread(self):
        text = ledger.render_overview(self.requirements)
        self.assertIn("do not edit", text.split("|")[0])
        rows = [line for line in text.splitlines() if line.startswith("| REQ-")]
        self.assertEqual(len(rows), 5)
        for number, row in enumerate(rows, start=1):
            self.assertIn(f"](requirements/REQ-{number}.yaml)", row)
        self.assertIn("Partial one", rows[1])
        self.assertIn("signed off ⚠️", rows[1])
        self.assertIn("2026-10-23", rows[1])


class TestRegenerate(LedgerTestCase):
    def test_canonicalises_hand_edits_and_writes_both_views(self):
        self.write(thread(1, proposed(), verified()), canonical=False)
        path = self.folder / "requirements" / "REQ-1.yaml"
        path.write_text("# hand edit\n" + path.read_text(encoding="utf-8"), encoding="utf-8")

        self.assertEqual(ledger.regenerate(self.folder), [])

        self.assertEqual(ledger.validate(self.folder), [])
        requirements = ledger.replay(self.folder)
        self.assertEqual((self.folder / "CURRENT.md").read_text(encoding="utf-8"),
                         ledger.render_current(requirements))
        self.assertEqual((self.folder / "OVERVIEW.md").read_text(encoding="utf-8"),
                         ledger.render_overview(requirements))

    def test_refuses_to_write_views_when_the_folder_is_invalid(self):
        self.write(thread(1, proposed(characteristic="Speed")))
        errors = ledger.regenerate(self.folder)
        self.assertReports(errors, "characteristic 'Speed'")
        self.assertFalse((self.folder / "CURRENT.md").exists())
        self.assertFalse((self.folder / "OVERVIEW.md").exists())


class TestRealQualityFolder(unittest.TestCase):
    """CI guard: the committed quality/ folder is valid and its views are up to date."""

    def test_is_valid(self):
        self.assertEqual(ledger.validate(QUALITY_DIR), [])

    def test_committed_views_equal_a_fresh_render(self):
        requirements = ledger.replay(QUALITY_DIR)
        hint = "run `python scripts/quality/regenerate.py` and commit the result"
        self.assertEqual((QUALITY_DIR / "CURRENT.md").read_text(encoding="utf-8"),
                         ledger.render_current(requirements), hint)
        self.assertEqual((QUALITY_DIR / "OVERVIEW.md").read_text(encoding="utf-8"),
                         ledger.render_overview(requirements), hint)


if __name__ == "__main__":
    unittest.main()
