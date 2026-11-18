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


def team(type_, **fields):
    entry = {"date": D(2026, 10, 23), "by": "team", "type": type_,
             "channel": "client meeting", "text": "Decided at the meeting."}
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

    def test_revised_or_amended_without_fields_is_reported(self):
        self.write(thread(1, proposed(), team("revised"), client("amended")))
        self.assertReports(ledger.validate(self.folder),
                           "revised: must change at least one requirement field",
                           "amended: must change at least one requirement field")

    def test_revised_or_amended_with_unknown_field_is_reported(self):
        self.write(thread(1, proposed(), team("revised", threshold="0.95"),
                          client("amended", metric="≥ 0.95.", result="✅")))
        self.assertReports(ledger.validate(self.folder),
                           "revised: unexpected field 'threshold'",
                           "amended: unexpected field 'result'")

    def test_revised_by_client_or_amended_by_team_is_reported(self):
        self.write(thread(1, proposed(), client("revised", metric="≥ 0.95."),
                          team("amended", metric="≥ 0.90.")))
        self.assertReports(ledger.validate(self.folder),
                           "revised: must be by team", "amended: must be by client")

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

    def test_carried_over_requires_a_delivery(self):
        self.write(thread(1, proposed(), team("carried-over")))
        self.assertReports(ledger.validate(self.folder), "carried-over: missing field 'delivery'")

    def test_carried_over_delivery_must_be_a_date(self):
        self.write(thread(1, proposed(), team("carried-over", delivery="12/11")))
        self.assertReports(ledger.validate(self.folder), "delivery '12/11'")

    def test_carried_over_stays_open_with_its_new_delivery(self):
        req = self.replayed(verified(result="⚠️"),
                            team("carried-over", delivery=D(2026, 11, 12)))
        self.assertEqual(req.spec["delivery"], D(2026, 11, 12))
        self.assertEqual(req.client_status, "awaiting client")
        self.assertEqual(req.latest_result, "⚠️")
        self.assertTrue(req.open)
        self.assertTrue(req.current)

    def test_carried_over_after_partial_sign_off_keeps_the_client_verdict(self):
        req = self.replayed(verified(result="⚠️"), client("accepted"),
                            client("signed-off", result="⚠️"),
                            team("carried-over", delivery=D(2026, 11, 12)))
        self.assertEqual(req.client_status, "signed off ⚠️")
        self.assertEqual(req.spec["delivery"], D(2026, 11, 12))
        self.assertTrue(req.open)

    def test_amendments_and_revisions_apply_in_order(self):
        req = self.replayed(team("revised", metric="≥ 0.80.", owner="Léo"),
                            client("amended", metric="≥ 0.95."),
                            team("revised", when="CI", date=D(2026, 10, 26)))
        self.assertEqual(req.spec["metric"], "≥ 0.95.")
        self.assertEqual(req.spec["owner"], "Léo")
        self.assertEqual(req.spec["when"], "CI")
        self.assertEqual(req.spec["title"], "Schema with ADRs")

    def test_amended_is_the_client_status_until_the_next_decision(self):
        req = self.replayed(client("amended", metric="≥ 0.95."))
        self.assertEqual(req.client_status, "amended")
        self.assertTrue(req.open)
        req = self.replayed(client("amended", metric="≥ 0.95."),
                            client("signed-off", result="⚠️"))
        self.assertEqual(req.client_status, "signed off ⚠️")

    def test_revised_after_acceptance_returns_to_awaiting_client(self):
        req = self.replayed(client("accepted"),
                            team("revised", metric="≥ 0.95.", date=D(2026, 11, 2)))
        self.assertEqual(req.client_status, "awaiting client")
        self.assertEqual(req.spec["metric"], "≥ 0.95.")
        self.assertTrue(req.open)

    def test_revised_after_sign_off_reopens_the_requirement(self):
        req = self.replayed(verified(), client("accepted"), client("signed-off", result="✅"),
                            team("revised", metric="≥ 0.95.", date=D(2026, 11, 2)))
        self.assertEqual(req.client_status, "awaiting client")
        self.assertTrue(req.open)
        self.assertTrue(req.current)

    def test_revised_after_drop_stays_dropped(self):
        req = self.replayed(team("dropped"),
                            team("revised", metric="≥ 0.95.", date=D(2026, 11, 2)))
        self.assertEqual(req.client_status, "dropped")
        self.assertEqual(req.spec["metric"], "≥ 0.95.")
        self.assertFalse(req.open)

    def test_latest_verification_wins(self):
        req = self.replayed(verified(result="❌", date=D(2026, 10, 20)), verified(result="✅"))
        self.assertEqual(req.latest_result, "✅")

    def test_recurring_signed_off_ok_stays_current(self):
        req = self.replayed(verified(), client("accepted"), client("signed-off", result="✅"),
                            recurring=True)
        self.assertFalse(req.open)
        self.assertTrue(req.current)

    def test_recurring_regression_after_sign_off_shows_as_latest_result(self):
        req = self.replayed(verified(), client("accepted"), client("signed-off", result="✅"),
                            verified(result="❌", date=D(2026, 11, 5)), recurring=True)
        self.assertEqual(req.client_status, "signed off ✅")
        self.assertEqual(req.latest_result, "❌")
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


def backlog(**overrides):
    """A `proposed` entry with no delivery commitment: only a title and a statement."""
    entry = {"date": D(2026, 11, 2), "by": "team", "type": "proposed",
             "channel": "sprint planning", "text": "Kept in the backlog.",
             "title": "Identical vectors", "statement": "Re-running gives identical vectors."}
    entry.update(overrides)
    return entry


COMMITMENT = {k: v for k, v in proposed().items()
              if k in ledger.REQUIREMENT_FIELDS and k not in ("title", "statement")}


class TestBacklog(LedgerTestCase):
    """A requirement proposed without a delivery is in the backlog until a sprint commits to it."""

    def test_backlog_proposal_needs_only_title_and_statement(self):
        self.write(thread(1, backlog()))
        self.assertEqual(ledger.validate(self.folder), [])

    def test_backlog_proposal_without_statement_is_reported(self):
        entry = backlog()
        del entry["statement"]
        self.write(thread(1, entry))
        self.assertReports(ledger.validate(self.folder), "proposed: missing field 'statement'")

    def test_committing_without_the_full_spec_is_reported(self):
        self.write(thread(1, backlog(), team("revised", delivery=D(2026, 11, 12),
                                             date=D(2026, 11, 9))))
        self.assertReports(ledger.validate(self.folder),
                           "REQ-1.yaml: committed to a delivery but missing 'metric'")

    def test_backlog_is_open_but_not_current(self):
        self.write(thread(1, backlog()))
        [req] = ledger.replay(self.folder)
        self.assertTrue(req.open)
        self.assertFalse(req.current)
        self.assertNotIn("REQ-1", ledger.render_current([req]))
        [row] = [line for line in ledger.render_overview([req]).splitlines()
                 if line.startswith("| REQ-1 |")]
        self.assertIn("| Identical vectors | backlog |", row)

    def test_revision_with_the_full_spec_commits_it(self):
        self.write(thread(1, backlog(), team("revised", date=D(2026, 11, 9), **COMMITMENT)))
        self.assertEqual(ledger.validate(self.folder), [])
        [req] = ledger.replay(self.folder)
        self.assertTrue(req.current)
        self.assertIn("## REQ-1 · Identical vectors", ledger.render_current([req]))


class TestRenderHistory(LedgerTestCase):
    """How carry-overs, drops and regressions show in the views."""

    def test_dropped_leaves_current_but_stays_in_overview(self):
        self.write(thread(1, proposed(title="Kept one")),
                   thread(2, proposed(title="Dropped one"), team("dropped")))
        requirements = ledger.replay(self.folder)
        self.assertNotIn("Dropped one", ledger.render_current(requirements))
        overview = ledger.render_overview(requirements)
        [row] = [line for line in overview.splitlines() if line.startswith("| REQ-2 |")]
        self.assertIn("Dropped one", row)
        self.assertIn("dropped", row)

    def test_carried_over_shows_its_new_delivery(self):
        self.write(thread(1, proposed(), verified(result="⚠️"),
                          team("carried-over", delivery=D(2026, 11, 12))))
        requirements = ledger.replay(self.folder)
        self.assertIn("**Delivery:** 2026-11-12", ledger.render_current(requirements))
        self.assertIn("| 2026-11-12 |", ledger.render_overview(requirements))

    def test_recurring_regression_shows_in_current(self):
        self.write(thread(1, proposed(title="Recurring one", recurring=True), verified(),
                          client("accepted"), client("signed-off", result="✅"),
                          verified(result="❌", date=D(2026, 11, 5), evidence="Run of 05/11.")))
        text = ledger.render_current(ledger.replay(self.folder))
        self.assertIn("## REQ-1 · Recurring one", text)
        self.assertIn("**Latest result:** ❌ (2026-11-05)", text)
        self.assertIn("Run of 05/11.", text)


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


class TestReadThread(LedgerTestCase):
    def test_spec_changes_show_each_changed_field_before_and_after(self):
        self.write(thread(1, proposed(metric="Threshold 0.90."),
                          client("amended", metric="Threshold 0.95."),
                          team("carried-over", delivery=D(2026, 10, 30))))

        read = ledger.read_thread(self.folder, "REQ-1")

        self.assertEqual(read.requirement.spec["metric"], "Threshold 0.95.")
        self.assertEqual([e.entry["type"] for e in read.entries],
                         ["proposed", "amended", "carried-over"])
        self.assertEqual(read.entries[0].changes, [])
        self.assertEqual(read.entries[1].changes,
                         [ledger.Change("metric", "Threshold 0.90.", "Threshold 0.95.")])
        self.assertEqual(read.entries[2].changes,
                         [ledger.Change("delivery", D(2026, 10, 23), D(2026, 10, 30))])

    def test_unknown_or_malformed_id_is_not_found(self):
        self.write(thread(1, proposed()))
        for req_id in ("REQ-2", "../deliveries", "REQ-0"):
            with self.subTest(req_id=req_id), self.assertRaises(FileNotFoundError):
                ledger.read_thread(self.folder, req_id)


class TestMeetings(LedgerTestCase):
    def test_each_meeting_has_its_free_thread_and_the_entries_dated_on_it(self):
        deliveries = {"deliveries": [
            {"date": D(2026, 10, 23), "theme": "Taxonomy POC",
             "thread": [{"date": D(2026, 10, 23), "by": "client", "text": "Satisfied."}]},
            {"date": D(2026, 10, 30), "theme": "Entities", "thread": []},
        ]}
        self.write(thread(1, proposed(), verified(), client("accepted")),
                   thread(2, proposed(), client("accepted"),
                          client("signed-off", date=D(2026, 10, 30), result="⚠️")),
                   deliveries=deliveries)

        first, second = ledger.meetings(self.folder)

        self.assertEqual((first.date, first.theme), (D(2026, 10, 23), "Taxonomy POC"))
        self.assertEqual([n["text"] for n in first.notes], ["Satisfied."])
        self.assertEqual([(e.req_id, e.entry["type"]) for e in first.entries],
                         [("REQ-1", "accepted"), ("REQ-2", "accepted")])
        self.assertEqual(second.notes, [])
        self.assertEqual([(e.req_id, e.entry["type"]) for e in second.entries],
                         [("REQ-2", "signed-off")])

    def test_a_spec_change_dated_on_a_meeting_shows_before_and_after(self):
        self.write(thread(1, proposed(metric="Threshold 0.90."),
                          client("amended", metric="Threshold 0.95.")))

        (meeting,) = ledger.meetings(self.folder)

        self.assertEqual(meeting.entries[0].changes,
                         [ledger.Change("metric", "Threshold 0.90.", "Threshold 0.95.")])


class TestAppend(LedgerTestCase):
    """Recording from the local tool: appends only, validated, views regenerated."""

    def path(self, req_id):
        return self.folder / "requirements" / f"{req_id}.yaml"

    def test_add_entry_keeps_earlier_entries_byte_identical_and_regenerates_the_views(self):
        self.write(thread(1, proposed(), verified()))
        before = self.path("REQ-1").read_bytes()

        ledger.add_entry(self.folder, "REQ-1", client("accepted"))

        after = self.path("REQ-1").read_bytes()
        self.assertTrue(after.startswith(before), "earlier entries were rewritten")
        self.assertIn(b"type: accepted", after[len(before):])
        self.assertEqual(ledger.validate(self.folder), [])
        self.assertIn("| REQ-1 | Schema with ADRs | 2026-10-23 | accepted | ✅ |",
                      (self.folder / "OVERVIEW.md").read_text(encoding="utf-8"))

    def test_crlf_checkout_keeps_earlier_entries_byte_identical(self):
        self.write(thread(1, proposed()))
        path = self.path("REQ-1")
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        before = path.read_bytes()

        ledger.add_entry(self.folder, "REQ-1", client("accepted"))

        self.assertTrue(path.read_bytes().startswith(before))

    def snapshot(self):
        return {p.name: p.read_bytes() for p in self.folder.rglob("*") if p.is_file()}

    def test_invalid_entry_is_refused_with_the_errors_and_nothing_is_written(self):
        self.write(thread(1, proposed(), verified()))
        ledger.regenerate(self.folder)
        before = self.snapshot()
        invalid = {
            "unknown type": client("approved"),
            "missing field": client("signed-off"),
            "date going back": client("accepted", date=D(2026, 10, 1)),
            "second proposed": proposed(date=D(2026, 10, 23)),
        }
        for case, entry in invalid.items():
            with self.subTest(case), self.assertRaises(ledger.AppendRefused) as refused:
                ledger.add_entry(self.folder, "REQ-1", entry)
            self.assertTrue(refused.exception.errors)
            self.assertEqual(self.snapshot(), before)

    def test_entry_to_an_unknown_requirement_is_refused(self):
        self.write(thread(1, proposed()))
        for req_id in ("REQ-2", "../deliveries"):
            with self.subTest(req_id=req_id), self.assertRaises(ledger.AppendRefused):
                ledger.add_entry(self.folder, req_id, client("accepted"))

    def test_entry_recorded_live_cannot_be_flagged_migrated(self):
        self.write(thread(1, proposed()))
        with self.assertRaises(ledger.AppendRefused) as refused:
            ledger.add_entry(self.folder, "REQ-1", client("accepted", migrated=True))
        self.assertReports(refused.exception.errors, "migrated")

    def test_append_to_an_already_invalid_folder_is_refused(self):
        self.write(thread(1, proposed()), thread(2, proposed(), client("approved")))
        with self.assertRaises(ledger.AppendRefused) as refused:
            ledger.add_entry(self.folder, "REQ-1", client("accepted"))
        self.assertReports(refused.exception.errors, "unknown entry type 'approved'")
        self.assertNotIn("accepted", self.path("REQ-1").read_text(encoding="utf-8"))

    def test_create_requirement_takes_the_next_id_and_regenerates_the_views(self):
        self.write(thread(1, proposed()), thread(2, proposed()))

        req_id = ledger.create_requirement(self.folder, proposed(title="Fast parser"))

        self.assertEqual(req_id, "REQ-3")
        self.assertEqual(ledger.validate(self.folder), [])
        (created,) = [r for r in ledger.replay(self.folder) if r.id == "REQ-3"]
        self.assertEqual((created.spec["title"], created.client_status),
                         ("Fast parser", "awaiting client"))
        self.assertIn("| REQ-3 | Fast parser |",
                      (self.folder / "OVERVIEW.md").read_text(encoding="utf-8"))

    def test_ids_of_dropped_or_rejected_requirements_are_never_reused(self):
        self.write(thread(1, proposed()),
                   thread(2, proposed(), client("rejected")),
                   thread(3, proposed(), team("dropped")))
        self.assertEqual(ledger.create_requirement(self.folder, proposed()), "REQ-4")

    def test_ids_follow_the_highest_number_not_the_file_count(self):
        self.write(thread(1, proposed()), thread(9, proposed()), thread(10, proposed()))
        self.assertEqual(ledger.create_requirement(self.folder, proposed()), "REQ-11")

    def test_create_requirement_accepts_iso_dates_as_sent_by_the_tool(self):
        self.write(thread(1, proposed()))
        req_id = ledger.create_requirement(
            self.folder, proposed(date="2026-11-23", delivery="2026-11-26"))
        (created,) = [r for r in ledger.replay(self.folder) if r.id == req_id]
        self.assertEqual(created.spec["delivery"], D(2026, 11, 26))

    def test_invalid_proposal_is_refused_and_no_file_is_created(self):
        self.write(thread(1, proposed()))
        incomplete = proposed()
        del incomplete["metric"]
        for case, entry in {"incomplete spec": incomplete,
                            "not a proposal": client("accepted"),
                            "bad date": proposed(delivery="next Thursday")}.items():
            with self.subTest(case), self.assertRaises(ledger.AppendRefused):
                ledger.create_requirement(self.folder, entry)
            self.assertEqual(sorted(p.name for p in (self.folder / "requirements").iterdir()),
                             ["REQ-1.yaml"])

    def test_add_meeting_appends_it_with_an_empty_thread(self):
        self.write(thread(1, proposed()))
        deliveries = self.folder / "deliveries.yaml"
        before = deliveries.read_bytes()

        ledger.add_meeting(self.folder, {"date": "2026-10-30", "theme": "Entities"})

        self.assertTrue(deliveries.read_bytes().startswith(before))
        last = ledger.meetings(self.folder)[-1]
        self.assertEqual((last.date, last.theme, last.notes),
                         (D(2026, 10, 30), "Entities", []))

    def test_meeting_not_after_the_last_one_is_refused(self):
        self.write(thread(1, proposed()))
        before = (self.folder / "deliveries.yaml").read_bytes()
        for case, meeting in {"same date": {"date": "2026-10-23", "theme": "Again"},
                              "no theme": {"date": "2026-10-30"}}.items():
            with self.subTest(case), self.assertRaises(ledger.AppendRefused):
                ledger.add_meeting(self.folder, meeting)
            self.assertEqual((self.folder / "deliveries.yaml").read_bytes(), before)

    def test_add_meeting_note_appends_to_that_meetings_thread_only(self):
        deliveries = {"deliveries": [
            {"date": D(2026, 10, 23), "theme": "Taxonomy POC", "thread": []},
            {"date": D(2026, 10, 30), "theme": "Entities",
             "thread": [{"date": D(2026, 10, 30), "by": "client", "text": "Satisfied."}]},
        ]}
        self.write(thread(1, proposed()), deliveries=deliveries)
        before = (self.folder / "deliveries.yaml").read_bytes()

        ledger.add_meeting_note(self.folder, "2026-10-30", {
            "date": "2026-10-30", "by": "team", "channel": "client meeting",
            "text": "Decision: move on to the GRU."})

        self.assertTrue((self.folder / "deliveries.yaml").read_bytes().startswith(before))
        first, second = ledger.meetings(self.folder)
        self.assertEqual(first.notes, [])
        self.assertEqual([n["text"] for n in second.notes],
                         ["Satisfied.", "Decision: move on to the GRU."])

    def test_note_to_an_unknown_meeting_or_invalid_note_is_refused(self):
        self.write(thread(1, proposed()))
        before = (self.folder / "deliveries.yaml").read_bytes()
        note = {"date": "2026-10-23", "by": "client", "text": "Fine."}
        cases = {"unknown meeting": ("2026-10-30", note),
                 "bad author": ("2026-10-23", {**note, "by": "Konrad"}),
                 "no text": ("2026-10-23", {"date": "2026-10-23", "by": "client"})}
        for case, (meeting_date, bad) in cases.items():
            with self.subTest(case), self.assertRaises(ledger.AppendRefused):
                ledger.add_meeting_note(self.folder, meeting_date, bad)
            self.assertEqual((self.folder / "deliveries.yaml").read_bytes(), before)


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
