# Exact synthetic account-selection evidence

Synthetic SQLite identity lookup; assertions assumed authenticated; no Flowise, model, network, real sessions or credentials.

18 chosen fixture pairs / 36 mode rows; 17 pairs satisfy the authenticated-assertion model. The separate forged-exact-binding pair deliberately violates that assumption. Counts are not empirical attack rates.

| Fixture | Family | Email match selects | Identity binding selects |
|---|---|---|---|
| ordinary | legitimate | alice | alice |
| cross_provider_email | unlinked | alice | REFUSED |
| same_provider_other_subject | unlinked | alice | REFUSED |
| same_subject_other_provider | legitimate | bob | bob |
| bound_bob_claims_alice_email | wrong_account | alice | bob |
| email_changed | legitimate_change | REFUSED | alice |
| email_matches_another_user | wrong_account | bob | alice |
| unknown_identity | unknown | REFUSED | REFUSED |
| missing_subject | unlinked | alice | REFUSED |
| unknown_provider | unknown | REFUSED | REFUSED |
| local_only_collision | unlinked | local-user | REFUSED |
| disabled_account | disabled | REFUSED | REFUSED |
| explicit_second_binding | legitimate | alice | alice |
| subject_case_changed | unlinked | alice | REFUSED |
| email_absent | legitimate_change | REFUSED | alice |
| apostrophe_subject | legitimate | carol | carol |
| provider_case_changed | unknown | REFUSED | REFUSED |
| forged_exact_binding | assumption_failure | alice | alice |

## Paired trace

The cross_provider_email assertion is (provider-B, unbound, alice@example.invalid). Both modes accept provider-B as configured. Email match finds users.email and captures user_id=alice. Identity binding finds no (provider-B, unbound) row and captures no session. It does not create a binding or silently move the request to a different account.

The ordinary (provider-A, alice-01) identity captures alice in both modes. Change only its email to bob@example.invalid: email match captures bob; binding still captures alice. The same subject string shared belongs to Alice under provider-A and Bob under provider-B, demonstrating why subject alone is not a key.

## Assumption counterexample

forged_exact_binding is byte-for-byte the same assertion as ordinary, but the narrative assumes it was falsely authenticated. Both methods necessarily select Alice. This component cannot tell the assertions apart. Binding depends on upstream authentication and trusted enrollment; it does not replace either.
