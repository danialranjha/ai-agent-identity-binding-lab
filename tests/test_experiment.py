import sqlite3
import unittest
from experiment import Assertion, CASES, MODES, database, lookup, run, session

class IdentityTests(unittest.TestCase):
    def setUp(self): self.db = database()
    def tearDown(self): self.db.close()

    def test_all_exact_account_outputs(self):
        for case in CASES:
            for mode, expected in zip(MODES, (case.expected_email, case.expected_bound)):
                with self.subTest(case=case.name, mode=mode):
                    self.assertEqual(lookup(self.db, case.assertion, mode), expected)
                    self.assertEqual(session(self.db, case.assertion, mode), [] if expected is None else [{"user_id": expected}])

    def test_same_subject_different_providers_select_different_owners(self):
        for provider, expected in (("provider-A", "alice"), ("provider-B", "bob")):
            self.assertEqual(lookup(self.db, Assertion(provider,"shared","irrelevant@example.invalid"), "bound_identity"), expected)

    def test_binding_uniqueness_prevents_silent_reassignment(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("INSERT INTO identities VALUES (?,?,?)", ("provider-A", "alice-01", "bob"))
        self.assertEqual(lookup(self.db, CASES[0].assertion, "bound_identity"), "alice")

    def test_binding_requires_existing_user_and_nonempty_subject(self):
        for record in (("provider-B","missing-user","unknown"),("provider-B","","alice")):
            with self.subTest(record=record), self.assertRaises(sqlite3.IntegrityError):
                self.db.execute("INSERT INTO identities VALUES (?,?,?)", record)

    def test_assertions_do_not_create_or_mutate_bindings(self):
        before = self.db.execute("SELECT * FROM identities ORDER BY provider,subject").fetchall()
        for case in CASES:
            for mode in MODES: session(self.db,case.assertion,mode)
        self.assertEqual(before,self.db.execute("SELECT * FROM identities ORDER BY provider,subject").fetchall())

    def test_parameter_binding_preserves_apostrophe_and_literal_values(self):
        self.assertEqual(lookup(self.db, Assertion("provider-A","O'Reilly",""),"bound_identity"),"carol")
        self.assertIsNone(lookup(self.db, Assertion("provider-A","O'Reilly extra",""),"bound_identity"))
        self.assertIsNone(lookup(self.db, Assertion("provider-A","alice-01","alice%@example.invalid"),"email_only"))

    def test_disabled_and_unknown_provider_rejected_consistently(self):
        for mode in MODES:
            self.assertIsNone(lookup(self.db, Assertion("provider-A","disabled-01","disabled@example.invalid"),mode))
            self.assertIsNone(lookup(self.db, Assertion("provider-C","alice-01","alice@example.invalid"),mode))

    def test_exact_forged_assertion_is_indistinguishable(self):
        self.assertEqual(CASES[0].assertion, next(c.assertion for c in CASES if c.name=="forged_exact_binding"))
        for mode in MODES: self.assertEqual(lookup(self.db,CASES[0].assertion,mode),"alice")

    def test_unknown_mode_fails_closed(self):
        with self.assertRaises(ValueError): lookup(self.db,CASES[0].assertion,"typo")

    def test_repeatability_and_row_coverage(self):
        a=run();self.assertEqual(a,run());self.assertEqual(len(a["rows"]),36)
        self.assertTrue(a["all_expected"])
        self.assertEqual({(x["case"],x["mode"]) for x in a["rows"]},{(c.name,m) for c in CASES for m in MODES})

if __name__ == "__main__": unittest.main()
