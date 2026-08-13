"""The demo dataset — fixed, deliberately messy, and rehearsable.

DEMO.md requires discovery to be non-trivial: the same person recorded
differently across stores, an orphaned record with no foreign key, unstructured
data, and one record that must survive the deletion under a retention
obligation. Each difficulty below exists to make one beat of the demo land.

It is a *fixture*, not a generator. A run that varies between takes costs hours
of re-recording, so nothing here is random.
"""

from __future__ import annotations

from dataclasses import dataclass

from custodian.confinement import FREETEXT, FieldSpec

# The data subject making the erasure request.
SUBJECT = {
    "name": "Amara Okafor",
    "email": "amara.okafor@example.com",
    "phone": "+234 801 234 5678",
    "address": "14 Bourdillon Road, Ikoyi, Lagos",
    "customer_id": "CUST-4417",
}

# What gets redacted out of free text, and how each value is typed.
#
# The truncated address is listed deliberately: the support ticket records
# "14 Bourdillon Road" while the KYC document has the full form, and matching
# only the long version would leave the short one sitting in a prompt. This is
# the seam where a real deployment would use an entity extractor instead of a
# hand-maintained list.
SUBJECT_SEEDS: tuple[tuple[str, str], ...] = (
    (SUBJECT["name"], "name"),
    (SUBJECT["email"], "email"),
    (SUBJECT["phone"], "phone"),
    (SUBJECT["address"], "address"),
    ("14 Bourdillon Road", "address"),
)


@dataclass(frozen=True)
class Store:
    """One searchable datastore and how its fields should be projected."""

    scope: str
    description: str
    spec: tuple[FieldSpec, ...]
    records: tuple[dict, ...]


# --- cloudsql:customers -----------------------------------------------------
# The canonical record. Contains decoys so discovery cannot succeed by
# returning everything — deleting another customer would be a catastrophic
# false positive.
CUSTOMERS = Store(
    scope="cloudsql:customers",
    description="Canonical customer master record.",
    spec=(
        FieldSpec("customer_id", None),
        FieldSpec("full_name", "name"),
        FieldSpec("email", "email"),
        FieldSpec("phone", "phone"),
        FieldSpec("address", "address"),
        FieldSpec("created_at", None),
    ),
    records=(
        {
            "customer_id": "CUST-4417",
            "full_name": "Amara Okafor",
            "email": "amara.okafor@example.com",
            "phone": "+234 801 234 5678",
            "address": "14 Bourdillon Road, Ikoyi, Lagos",
            "created_at": "2023-02-11",
        },
        {
            "customer_id": "CUST-4418",
            "full_name": "Amara Okonkwo",  # decoy: similar name, different person
            "email": "a.okonkwo@example.com",
            "phone": "+234 802 998 1200",
            "address": "3 Glover Road, Ikoyi, Lagos",
            "created_at": "2023-02-12",
        },
        {
            "customer_id": "CUST-5001",
            "full_name": "Tunde Bakare",
            "email": "tunde.bakare@example.com",
            "phone": "+234 803 555 0199",
            "address": "22 Admiralty Way, Lekki, Lagos",
            "created_at": "2024-06-30",
        },
    ),
)

# --- cloudsql:orders --------------------------------------------------------
# Beat 5 depends on INV-2024-0912: a tax invoice under a statutory retention
# period. The assessor must flag it as retain, against the erasure request.
ORDERS = Store(
    scope="cloudsql:orders",
    description="Order and invoice history; some records carry retention duties.",
    spec=(
        FieldSpec("order_id", None),
        FieldSpec("customer_id", None),
        FieldSpec("billing_email", "email"),
        FieldSpec("total_ngn", None),
        FieldSpec("placed_at", None),
        FieldSpec("retention_basis", None),
    ),
    records=(
        {
            "order_id": "ORD-88231",
            "customer_id": "CUST-4417",
            "billing_email": "amara.okafor@example.com",
            "total_ngn": 45_000,
            "placed_at": "2023-03-04",
            "retention_basis": None,
        },
        {
            "order_id": "INV-2024-0912",
            "customer_id": "CUST-4417",
            "billing_email": "amara.okafor@example.com",
            "total_ngn": 1_250_000,
            "placed_at": "2024-09-12",
            # The conflict. Erasure must not remove this.
            "retention_basis": "tax:statutory-7-years",
        },
        {
            "order_id": "ORD-90114",
            "customer_id": "CUST-5001",
            "billing_email": "tunde.bakare@example.com",
            "total_ngn": 12_500,
            "placed_at": "2024-11-02",
            "retention_basis": None,
        },
    ),
)

# --- firestore:events -------------------------------------------------------
# Same address, different formatting. Normalization links this automatically,
# which demonstrates the tokenizer doing real work.
EVENTS = Store(
    scope="firestore:events",
    description="Application analytics events keyed by user email.",
    spec=(
        FieldSpec("event_id", None),
        FieldSpec("user_email", "email"),
        FieldSpec("event", None),
        FieldSpec("occurred_at", None),
    ),
    records=(
        {
            "event_id": "evt-7712",
            "user_email": "  Amara.Okafor@Example.com ",  # case + whitespace drift
            "event": "checkout.completed",
            "occurred_at": "2024-09-12T10:04:00Z",
        },
        {
            "event_id": "evt-7713",
            "user_email": "AMARA.OKAFOR@EXAMPLE.COM",
            "event": "profile.updated",
            "occurred_at": "2024-09-14T18:22:00Z",
        },
        {
            "event_id": "evt-9001",
            "user_email": "tunde.bakare@example.com",
            "event": "login",
            "occurred_at": "2025-01-08T07:15:00Z",
        },
    ),
)

# --- firestore:profiles -----------------------------------------------------
# The orphan. No customer_id, and a genuinely different address the tokenizer
# cannot link — the classifier has to reason from name and phone that this is
# the same person.
PROFILES = Store(
    scope="firestore:profiles",
    description="Legacy profile documents migrated without foreign keys.",
    spec=(
        FieldSpec("profile_id", None),
        FieldSpec("display_name", "name"),
        FieldSpec("contact_email", "email"),
        FieldSpec("recovery_phone", "phone"),
        FieldSpec("migrated_from", None),
    ),
    records=(
        {
            "profile_id": "prof-0031",
            "display_name": "Amara Okafor",
            "contact_email": "a.okafor@contractor.example.net",  # alias, not linkable
            "recovery_phone": "0801 234 5678",  # same number, national format
            "migrated_from": "legacy-crm-2021",
        },
        {
            "profile_id": "prof-0042",
            "display_name": "Tunde Bakare",
            "contact_email": "tunde.bakare@example.com",
            "recovery_phone": "0803 555 0199",
            "migrated_from": "legacy-crm-2021",
        },
    ),
)

# --- gcs:uploads ------------------------------------------------------------
# Unstructured. Discovery here is hardest and is where Gemini earns its place.
UPLOADS = Store(
    scope="gcs:uploads",
    description="Uploaded identity and address documents.",
    spec=(
        FieldSpec("object", None),
        FieldSpec("content_type", None),
        FieldSpec("extracted_text", FREETEXT),
        FieldSpec("uploaded_at", None),
    ),
    records=(
        {
            "object": "kyc/2023/scan-4417-a.txt",
            "content_type": "text/plain",
            "extracted_text": (
                "PROOF OF ADDRESS — Account holder: Amara Okafor. "
                "Residence: 14 Bourdillon Road, Ikoyi, Lagos. "
                "Contact number on file: +234 801 234 5678."
            ),
            "uploaded_at": "2023-02-11",
        },
        {
            "object": "kyc/2024/scan-5001-a.txt",
            "content_type": "text/plain",
            "extracted_text": (
                "PROOF OF ADDRESS — Account holder: Tunde Bakare. "
                "Residence: 22 Admiralty Way, Lekki, Lagos."
            ),
            "uploaded_at": "2024-07-01",
        },
    ),
)

# --- supportdesk:tickets ----------------------------------------------------
# Personal data buried in free text written by an agent, with no structured
# field to key off.
TICKETS = Store(
    scope="supportdesk:tickets",
    description="Support tickets and agent notes.",
    spec=(
        FieldSpec("ticket_id", None),
        FieldSpec("subject", None),
        FieldSpec("body", FREETEXT),
        FieldSpec("opened_at", None),
    ),
    records=(
        {
            "ticket_id": "TKT-3390",
            "subject": "Delivery not received",
            "body": (
                "Caller reached me on 0801 234 5678, says the package for "
                "order ORD-88231 never arrived at 14 Bourdillon Road."
            ),
            "opened_at": "2023-03-09",
        },
        {
            "ticket_id": "TKT-4102",
            "subject": "Refund query",
            "body": "Customer Tunde Bakare asking about ORD-90114 refund timing.",
            "opened_at": "2024-11-06",
        },
    ),
)

STORES: tuple[Store, ...] = (
    CUSTOMERS,
    ORDERS,
    EVENTS,
    PROFILES,
    UPLOADS,
    TICKETS,
)

# What a correct run must find. Tests assert against this so a regression in
# discovery is caught before it reaches a recording session.
EXPECTED_MATCHES: dict[str, tuple[str, ...]] = {
    "cloudsql:customers": ("CUST-4417",),
    "cloudsql:orders": ("ORD-88231", "INV-2024-0912"),
    "firestore:events": ("evt-7712", "evt-7713"),
    "firestore:profiles": ("prof-0031",),
    "gcs:uploads": ("kyc/2023/scan-4417-a.txt",),
    "supportdesk:tickets": ("TKT-3390",),
}

# The record that must survive, and why.
EXPECTED_RETENTIONS: dict[str, str] = {
    "INV-2024-0912": "tax:statutory-7-years",
}
