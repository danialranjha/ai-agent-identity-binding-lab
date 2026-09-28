"""Synthetic account mapping only. No authentication protocol or live accounts."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sqlite3

MODES = ("email_only", "bound_identity")
PROVIDERS = frozenset({"provider-A", "provider-B"})
USERS = (
    ("alice", "alice@example.invalid", 1),
    ("bob", "bob@example.invalid", 1),
    ("local-user", "local@example.invalid", 1),
    ("disabled-user", "disabled@example.invalid", 0),
    ("carol", "carol@example.invalid", 1),
)
BINDINGS = (
    ("provider-A", "alice-01", "alice"),
    ("provider-A", "shared", "alice"),
    ("provider-B", "shared", "bob"),
    ("provider-B", "alice-linked", "alice"),
    ("provider-A", "disabled-01", "disabled-user"),
    ("provider-A", "O'Reilly", "carol"),
)

@dataclass(frozen=True)
class Assertion:
    provider: str
    subject: str
    email: str

@dataclass(frozen=True)
class Case:
    name: str
    family: str
    assertion: Assertion
    expected_email: str | None
    expected_bound: str | None
    owner: str | None
    note: str

# Expected outputs and ownership are authored fixtures, not derived from lookup code.
CASES = (
    Case("ordinary", "legitimate", Assertion("provider-A", "alice-01", "alice@example.invalid"), "alice", "alice", "alice", "Ordinary enrolled identity."),
    Case("cross_provider_email", "unlinked", Assertion("provider-B", "unbound", "alice@example.invalid"), "alice", None, None, "Different provider and subject claim Alice email."),
    Case("same_provider_other_subject", "unlinked", Assertion("provider-A", "attacker-01", "alice@example.invalid"), "alice", None, None, "Provider membership alone is insufficient."),
    Case("same_subject_other_provider", "legitimate", Assertion("provider-B", "shared", "bob@example.invalid"), "bob", "bob", "bob", "The same subject string exists under A and B with different owners."),
    Case("bound_bob_claims_alice_email", "wrong_account", Assertion("provider-B", "shared", "alice@example.invalid"), "alice", "bob", "bob", "Binding must select Bob, not simply permit any session."),
    Case("email_changed", "legitimate_change", Assertion("provider-A", "alice-01", "new-alice@example.invalid"), None, "alice", "alice", "Stable enrolled identity with a new email."),
    Case("email_matches_another_user", "wrong_account", Assertion("provider-A", "alice-01", "bob@example.invalid"), "bob", "alice", "alice", "Stable identity must not jump to Bob."),
    Case("unknown_identity", "unknown", Assertion("provider-A", "unseen", "nobody@example.invalid"), None, None, None, "No email or identity match."),
    Case("missing_subject", "unlinked", Assertion("provider-A", "", "alice@example.invalid"), "alice", None, None, "Missing stable identity is not repaired with email."),
    Case("unknown_provider", "unknown", Assertion("provider-C", "alice-01", "alice@example.invalid"), None, None, None, "Common trusted-provider check refuses unknown namespace."),
    Case("local_only_collision", "unlinked", Assertion("provider-B", "local-claim", "local@example.invalid"), "local-user", None, None, "Local-only user has no federated binding."),
    Case("disabled_account", "disabled", Assertion("provider-A", "disabled-01", "disabled@example.invalid"), None, None, None, "Same active-account check in both modes."),
    Case("explicit_second_binding", "legitimate", Assertion("provider-B", "alice-linked", "alice@example.invalid"), "alice", "alice", "alice", "Second identity was explicitly enrolled ahead of time."),
    Case("subject_case_changed", "unlinked", Assertion("provider-A", "ALICE-01", "alice@example.invalid"), "alice", None, None, "Opaque subject comparisons are case-sensitive."),
    Case("email_absent", "legitimate_change", Assertion("provider-A", "alice-01", ""), None, "alice", "alice", "Known binding does not need an email claim for this lookup."),
    Case("apostrophe_subject", "legitimate", Assertion("provider-A", "O'Reilly", "carol@example.invalid"), "carol", "carol", "carol", "Bound parameter preserves an ordinary apostrophe."),
    Case("provider_case_changed", "unknown", Assertion("provider-a", "alice-01", "alice@example.invalid"), None, None, None, "Provider namespace is an exact trusted adapter identifier."),
    Case("forged_exact_binding", "assumption_failure", Assertion("provider-A", "alice-01", "alice@example.invalid"), "alice", "alice", None, "If the trusted adapter falsely asserts Alice's exact identity, both accept. Authentication validation is outside this model."),
)

def database():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript("""
      CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, active INTEGER NOT NULL CHECK(active IN (0,1)));
      CREATE TABLE identities (provider TEXT NOT NULL, subject TEXT NOT NULL CHECK(length(subject)>0),
        user_id TEXT NOT NULL REFERENCES users(id), PRIMARY KEY(provider,subject));
    """)
    db.executemany("INSERT INTO users VALUES (?,?,?)", USERS)
    db.executemany("INSERT INTO identities VALUES (?,?,?)", BINDINGS)
    return db

def lookup(db, assertion, mode):
    if mode not in (*MODES, "email_fallback_mutant", "provider_omitted_mutant"):
        raise ValueError("unknown mode")
    if assertion.provider not in PROVIDERS:
        return None
    if mode == "email_only":
        row = db.execute("SELECT id FROM users WHERE email=? AND active=1", (assertion.email,)).fetchone()
    else:
        if not assertion.subject:
            return None
        if mode == "provider_omitted_mutant":
            row = db.execute("SELECT u.id FROM identities i JOIN users u ON u.id=i.user_id WHERE i.subject=? AND u.active=1 ORDER BY i.provider LIMIT 1", (assertion.subject,)).fetchone()
        else:
            row = db.execute("SELECT u.id FROM identities i JOIN users u ON u.id=i.user_id WHERE i.provider=? AND i.subject=? AND u.active=1", (assertion.provider, assertion.subject)).fetchone()
        if row is None and mode == "email_fallback_mutant":
            row = db.execute("SELECT id FROM users WHERE email=? AND active=1", (assertion.email,)).fetchone()
    return row[0] if row else None

def session(db, assertion, mode):
    user = lookup(db, assertion, mode)
    return [] if user is None else [{"user_id": user}]

def run():
    db = database()
    rows = []
    try:
        for case in CASES:
            for mode, expected in zip(MODES, (case.expected_email, case.expected_bound)):
                captured = session(db, case.assertion, mode)
                actual = captured[0]["user_id"] if captured else None
                rows.append({"case": case.name, "family": case.family, "mode": mode,
                             "assertion": asdict(case.assertion), "owner": case.owner,
                             "expected": expected, "actual": actual, "session_capture": captured,
                             "matches_expected": actual == expected, "note": case.note})
    finally:
        db.close()
    counts = {}
    for mode in MODES:
        scoped = [x for x in rows if x["mode"] == mode and x["family"] != "assumption_failure"]
        counts[mode] = {"in_scope_fixtures": len(scoped),
                       "wrong_account_sessions": sum(x["actual"] is not None and x["actual"] != x["owner"] for x in scoped),
                       "correct_account_sessions": sum(x["actual"] is not None and x["actual"] == x["owner"] for x in scoped),
                       "refused": sum(x["actual"] is None for x in scoped)}
    return {"schema_version": 1, "scope": "Synthetic SQLite identity lookup; assertions assumed authenticated; no Flowise, model, network, real sessions or credentials.",
            "fixture_pairs": len(CASES), "rows": rows, "counts_excluding_assumption_failure": counts,
            "all_expected": all(x["matches_expected"] for x in rows)}

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+"\n")

def evidence(result):
    lines = ["# Exact synthetic account-selection evidence", "", result["scope"], "",
             "18 chosen fixture pairs / 36 mode rows; 17 pairs satisfy the authenticated-assertion model. The separate forged-exact-binding pair deliberately violates that assumption. Counts are not empirical attack rates.", "",
             "| Fixture | Family | Email match selects | Identity binding selects |", "|---|---|---|---|"]
    for case in CASES:
        values = [x["actual"] for x in result["rows"] if x["case"] == case.name]
        lines.append("| "+" | ".join([case.name, case.family, *[v if v else "REFUSED" for v in values]])+" |")
    lines += ["", "## Paired trace", "",
              "The cross_provider_email assertion is (provider-B, unbound, alice@example.invalid). Both modes accept provider-B as configured. Email match finds users.email and captures user_id=alice. Identity binding finds no (provider-B, unbound) row and captures no session. It does not create a binding or silently move the request to a different account.", "",
              "The ordinary (provider-A, alice-01) identity captures alice in both modes. Change only its email to bob@example.invalid: email match captures bob; binding still captures alice. The same subject string shared belongs to Alice under provider-A and Bob under provider-B, demonstrating why subject alone is not a key.", "",
              "## Assumption counterexample", "",
              "forged_exact_binding is byte-for-byte the same assertion as ordinary, but the narrative assumes it was falsely authenticated. Both methods necessarily select Alice. This component cannot tell the assertions apart. Binding depends on upstream authentication and trusted enrollment; it does not replace either.", ""]
    return "\n".join(lines)

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    result = run()
    if not result["all_expected"]:
        raise SystemExit("fixture mismatch; evidence not written")
    write_json(root/"artifacts/run.json", result)
    (root/"evidence.md").write_text(evidence(result))
    print(json.dumps({"fixture_pairs": result["fixture_pairs"], "rows": len(result["rows"]), "all_expected": result["all_expected"], "counts": result["counts_excluding_assumption_failure"]}, sort_keys=True))
