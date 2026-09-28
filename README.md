# AI-agent platform identity-binding lab

An offline, synthetic test of how an agent platform maps a login identity to a local account. Python standard library and SQLite only. No Flowise code, AI model, authentication protocol, network request, real account, session cookie, or credential is used.

## Hypothesis

Email-only lookup can select someone else's account when a different authenticated identity supplies the same email. An exact, pre-enrolled provider-and-subject binding refuses unknown identities and keeps a known identity on the same account when its email changes.

## Source motivation

[Flowise's email-only SSO advisory](https://github.com/FlowiseAI/Flowise/security/advisories/GHSA-cffm-583c-vffr) describes account matching by email and recommends stored provider/subject bindings rather than automatic email merging. It was published September 10, 2026; this is not a new disclosure or a claim to reproduce a released patch. The lab independently models the proposed lookup distinction. It does not reproduce the product or its separate invitation-token issue.

## Setup and exact commands

Requires Python 3.10+ with SQLite support. No package installation or credentials needed.

```sh
python3 experiment.py
python3 -m unittest discover -s tests -v
python3 run_checks.py
```

The first command generates [run.json](artifacts/run.json) and [evidence.md](evidence.md). The last generates [tests.json](artifacts/tests.json) and [mutations.json](artifacts/mutations.json). Output is deterministic, without dates or random IDs.

## Threat model

Assume a different identity at a configured provider can claim Alice's email. Obtaining that claim is not tested. The authentication adapter is trusted to have validated the assertion and to supply the correct issuer/tenant namespace and exact stable subject. The database, pre-enrollment process and application remain trusted. Provider-A and provider-B represent distinct complete trust namespaces, not provider brand names. No arbitrary raw token or network input is accepted.

The attacker-controlled email may collide with an existing account. The result sink is an in-memory record containing only a fictional account ID. There is no connector access or real session issuance.

## Technical walkthrough

The two methods use the same synthetic users, configured-provider check and active-account check:

* **Email match:** parameterized lookup of the user by exact email.
* **Stored identity binding:** parameterized lookup of an existing `(provider, subject)` pair joined to an active user. No email fallback and no automatic linking.

Email comparison is intentionally exact and case-sensitive in this lab, unlike any product-specific normalization. That difference does not affect the chosen exact-email collision. Subjects and provider namespace identifiers are opaque and case-sensitive. SQLite enforces a unique composite identity key and a foreign key to the user table. Database enrollment is fixture setup, not a tested account-linking workflow.

### Results

See the complete [fixture table and paired trace](evidence.md). All 18 pairs / 36 mode rows match their independently authored expected account IDs. Seventeen pairs satisfy the authenticated-assertion assumptions; the last pair deliberately violates them to expose the limit.

`cross_provider_email` supplies provider-B / unbound / alice@example.invalid. Email match captures Alice's account. Stored identity binding finds no row and refuses. An ordinary provider-A / alice-01 login captures Alice in both methods.

Changing Alice's claimed email to Bob's email makes Email match select Bob. Stored identity binding still selects Alice. The shared subject value under two different providers maps to different owners; comparing subject alone therefore fails.

The exact counts, including legitimate email-change refusals and wrong-account sessions, are in run.json. They are counts of hand-selected cases, not attack rates. The tests inspect the selected ID as well as refusal, so choosing the wrong existing account cannot hide behind an allowed boolean.

Ten tests pass. Deliberately restoring email fallback or dropping provider from the binding lookup produces mismatches caught by the same expected-ID oracle; exact cases are in mutations.json.

### Important counterexample

`forged_exact_binding` supplies the exact same values as Alice's ordinary login while assuming the adapter wrongly authenticated them. Both methods select Alice. A lookup cannot distinguish identical trusted assertions. Provider/subject binding depends on authenticating those values and protecting enrollment; it cannot repair a forged trusted assertion.

## Limitations

This is a design model, not a Flowise exploit reproduction, deployment test, or proof of a vendor fix. It does not test token signature, issuer/audience verification, OAuth state, session creation, account linking, recovery, migration, invitation activation, local passwords, tenant authorization or connector-key exposure. It assumes the configured provider namespace is correct and the binding database is trusted. Email-less lookup success in this model says nothing about other application requirements. An incorrectly enrolled or compromised binding still selects the wrong owner. Assertions and counts say nothing about live-model behavior.

## Supported engineering check

After validating a provider's authentication response, resolve the account using an explicitly enrolled identity namespace and subject. Require a separately authenticated linking process for a new binding rather than silently linking by email. Regression tests should compare exact account IDs across same-email/different-identity, same-subject/different-provider, and changed-email cases, while checking an ordinary login still works.

## Contents

Only code, focused tests, reproducible technical evidence and this technical write-up are included. All fixtures use fictional account IDs and reserved `.invalid` email domains.
