"""The confinement rule is the product's central claim, so it is tested.

Any convenience path that puts a raw value into a prompt destroys the claim
silently. These tests are the thing that stops that happening.
"""

from __future__ import annotations

import json

import pytest

from custodian.confinement import ConfinementError, TokenVault, normalize, project
from seed import fixture


@pytest.fixture
def vault() -> TokenVault:
    """A vault seeded the way a real run seeds it — from the erasure request."""
    v = TokenVault(run_id="run-test")
    v.seed_values(fixture.SUBJECT_SEEDS)
    return v


def test_projection_of_every_store_leaks_nothing(vault: TokenVault):
    """The whole fixture, projected and serialized as a prompt would be."""
    prompts = []
    for store in fixture.STORES:
        for record in store.records:
            prompts.append(json.dumps(project(record, store.spec, vault)))

    combined = "\n".join(prompts)
    # Scans for every raw value the vault minted a token for.
    vault.assert_no_raw_values(combined, where="discovery prompt")


def test_leak_is_actually_detected(vault: TokenVault):
    """A guard that never fires is worse than no guard."""
    vault.token_for(fixture.SUBJECT["email"], "email")
    leaky = f"Find records belonging to {fixture.SUBJECT['email']}"

    with pytest.raises(ConfinementError, match="leaked into"):
        vault.assert_no_raw_values(leaky)


def test_same_email_across_stores_yields_one_token(vault: TokenVault):
    """Cross-store identity resolution without exposing the address.

    Cloud SQL stores the address lowercase; Firestore has case and whitespace
    drift. Both must reduce to the same token or the fleet cannot join them.
    """
    canonical = vault.token_for("amara.okafor@example.com", "email")
    drifted = vault.token_for("  Amara.Okafor@Example.com ", "email")
    shouting = vault.token_for("AMARA.OKAFOR@EXAMPLE.COM", "email")

    assert canonical == drifted == shouting


def test_phone_formats_reconcile(vault: TokenVault):
    """+234 801… in Cloud SQL and 0801… in the legacy profile are one number."""
    international = vault.token_for("+234 801 234 5678", "phone")
    national = vault.token_for("0801 234 5678", "phone")

    assert international == national


def test_alias_email_is_not_silently_linked(vault: TokenVault):
    """Normalization must not overreach.

    The orphaned profile uses a genuinely different address. Linking it is a
    reasoning task for the classifier; if normalization did it, the fleet would
    be guessing rather than deciding, and the demo's hardest beat would be fake.
    """
    primary = vault.token_for("amara.okafor@example.com", "email")
    alias = vault.token_for("a.okafor@contractor.example.net", "email")

    assert primary != alias


def test_decoy_subject_gets_distinct_tokens(vault: TokenVault):
    """A similar name must not collapse into the subject."""
    subject = vault.token_for("Amara Okafor", "name")
    decoy = vault.token_for("Amara Okonkwo", "name")

    assert subject != decoy


def test_tokens_do_not_survive_across_runs():
    """Tokens are run-scoped, so they cannot become a durable identifier."""
    a = TokenVault(run_id="run-a").token_for("amara.okafor@example.com", "email")
    b = TokenVault(run_id="run-b").token_for("amara.okafor@example.com", "email")

    assert a != b


def test_non_personal_fields_pass_through(vault: TokenVault):
    """Agents still need totals and retention bases to reason about erasure."""
    invoice = next(
        r for r in fixture.ORDERS.records if r["order_id"] == "INV-2024-0912"
    )
    projected = project(invoice, fixture.ORDERS.spec, vault)

    assert projected["order_id"] == "INV-2024-0912"
    assert projected["total_ngn"] == 1_250_000
    assert projected["retention_basis"] == "tax:statutory-7-years"
    assert projected["billing_email"].startswith("tok_email_")


def test_resolve_returns_the_original_value(vault: TokenVault):
    """Executor-side resolution, the only place raw values reappear."""
    token = vault.token_for("  Amara.Okafor@Example.com ", "email")

    # Resolution returns what was stored, not the normalized form — deletion
    # has to match the value as it exists in that store.
    assert vault.resolve(token) == "  Amara.Okafor@Example.com "


def test_unknown_token_is_rejected(vault: TokenVault):
    with pytest.raises(ConfinementError, match="unknown token"):
        vault.resolve("tok_email_deadbeef1234")


def test_normalize_leaves_unknown_kinds_alone():
    assert normalize(" ORD-88231 ", "order_ref") == "ORD-88231"


def test_free_text_stays_useful_after_redaction(vault: TokenVault):
    """Redaction must remove identity without removing meaning.

    Tokenizing a whole document would pass a leak scan while leaving the agent
    nothing to reason about. The prose has to survive.
    """
    doc = next(
        r for r in fixture.UPLOADS.records if r["object"].endswith("scan-4417-a.txt")
    )
    projected = project(doc, fixture.UPLOADS.spec, vault)
    text = projected["extracted_text"]

    # Identity is gone.
    vault.assert_no_raw_values(text, where="document projection")
    assert "Amara Okafor" not in text

    # Meaning survives: the agent can still tell what kind of document this is.
    assert "PROOF OF ADDRESS" in text
    assert "Account holder:" in text
    assert "tok_name_" in text
    assert "tok_address_" in text


def test_truncated_address_variant_is_redacted(vault: TokenVault):
    """The support ticket records a shorter address than the KYC document.

    Matching only the full form would leave "14 Bourdillon Road" sitting in a
    prompt. This is the case that made variant seeding necessary.
    """
    ticket = next(
        r for r in fixture.TICKETS.records if r["ticket_id"] == "TKT-3390"
    )
    projected = project(ticket, fixture.TICKETS.spec, vault)
    body = projected["body"]

    assert "Bourdillon" not in body
    assert "0801" not in body
    # The order reference is not personal data and the assessor needs it.
    assert "ORD-88231" in body


def test_third_party_names_are_redacted_from_prose(vault: TokenVault):
    """A decoy's name in a support ticket is still someone's personal data.

    The subject's identifiers are seeded from the request; a third party's are
    learned while reading structured stores. Both must be gone from prose.
    """
    for record in fixture.CUSTOMERS.records:  # vault learns every customer name
        project(record, fixture.CUSTOMERS.spec, vault)

    ticket = next(r for r in fixture.TICKETS.records if r["ticket_id"] == "TKT-4102")
    projected = project(ticket, fixture.TICKETS.spec, vault)

    assert "Tunde Bakare" not in projected["body"]
    assert "tok_name_" in projected["body"]
    assert "ORD-90114" in projected["body"]  # not personal data, still readable


def test_third_party_redaction_is_order_dependent(vault: TokenVault):
    """A known limitation, encoded so it cannot be forgotten.

    Redaction of a third party depends on their name having been seen in a
    structured store first. Project prose before that and the name survives.
    The fleet works around this by ordering discovery structured-first, but the
    robust fix is entity extraction over the text itself — Cloud Sensitive Data
    Protection — rather than a vault lookup.
    """
    ticket = next(r for r in fixture.TICKETS.records if r["ticket_id"] == "TKT-4102")
    projected = project(ticket, fixture.TICKETS.spec, vault)

    assert "Tunde Bakare" in projected["body"]
