"""Agent registry — the cross-departmental catalog.

The Fortified Enterprise Fleet track asks for "agent cataloging for
cross-departmental discovery". That means a catalog other teams find agents
through, so an entry has to carry what a consumer in another department needs
before invoking something: what it can do, what data it is permitted to touch,
and whether a human must approve its actions.

Entries live in Firestore so the catalog survives revisions and can be read by
the console without going through an agent.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass

from google.cloud import firestore

COLLECTION = "agent_registry"

_db: firestore.Client | None = None


def _client() -> firestore.Client:
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


@dataclass(frozen=True)
class AgentCard:
    """What one agent publishes about itself to the rest of the organization."""

    name: str
    version: str
    department: str
    summary: str
    capabilities: tuple[str, ...]
    # Data scopes this agent may touch. The executor enforces these; the card
    # exists so a consumer can see the blast radius before invoking.
    data_scopes: tuple[str, ...]
    # True when the agent can take an irreversible action and therefore may not
    # run without a human decision recorded first.
    requires_approval: bool

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["capabilities"] = list(self.capabilities)
        d["data_scopes"] = list(self.data_scopes)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "AgentCard":
        return cls(
            name=d["name"],
            version=d["version"],
            department=d["department"],
            summary=d["summary"],
            capabilities=tuple(d.get("capabilities", ())),
            data_scopes=tuple(d.get("data_scopes", ())),
            requires_approval=bool(d.get("requires_approval", False)),
        )


# The catalog. Four departments own agents, which is what makes discovery
# across the registry meaningful rather than a list of one team's scripts.
FLEET: tuple[AgentCard, ...] = (
    AgentCard(
        name="discovery.cloudsql",
        version="0.1.0",
        department="Data Engineering",
        summary="Locates subject records in the relational customer store.",
        capabilities=("discover", "profile-schema"),
        data_scopes=("cloudsql:customers", "cloudsql:orders"),
        requires_approval=False,
    ),
    AgentCard(
        name="discovery.firestore",
        version="0.1.0",
        department="Data Engineering",
        summary="Locates subject records in application event collections.",
        capabilities=("discover",),
        data_scopes=("firestore:events", "firestore:profiles"),
        requires_approval=False,
    ),
    AgentCard(
        name="discovery.storage",
        version="0.1.0",
        department="Data Engineering",
        summary="Locates subject data inside unstructured uploaded documents.",
        capabilities=("discover", "extract-document"),
        data_scopes=("gcs:uploads",),
        requires_approval=False,
    ),
    AgentCard(
        name="discovery.supportdesk",
        version="0.1.0",
        department="Support",
        summary="Locates subject data in support tickets and transcripts.",
        capabilities=("discover",),
        data_scopes=("supportdesk:tickets",),
        requires_approval=False,
    ),
    AgentCard(
        name="classifier.pii",
        version="0.1.0",
        department="Security",
        summary="Types discovered fields as personal data and scores confidence.",
        capabilities=("classify",),
        data_scopes=(),  # operates on metadata and tokens only
        requires_approval=False,
    ),
    AgentCard(
        name="assessor.lawful-basis",
        version="0.1.0",
        department="Legal",
        summary=(
            "Decides erase or retain per record and cites the obligation behind "
            "any retention."
        ),
        capabilities=("assess", "cite"),
        data_scopes=(),
        requires_approval=False,
    ),
    AgentCard(
        name="executor.erasure",
        version="0.1.0",
        department="Data Engineering",
        summary="Performs approved deletions and returns per-store receipts.",
        capabilities=("execute-erasure",),
        data_scopes=(
            "cloudsql:customers",
            "cloudsql:orders",
            "firestore:events",
            "firestore:profiles",
            "gcs:uploads",
            "supportdesk:tickets",
        ),
        requires_approval=True,  # irreversible
    ),
    AgentCard(
        name="verifier.residue",
        version="0.1.0",
        department="Security",
        summary="Re-runs discovery after execution and reports remaining matches.",
        capabilities=("discover", "verify"),
        data_scopes=("*:read-only",),
        requires_approval=False,
    ),
)


def publish_fleet() -> int:
    """Write the catalog to Firestore. Idempotent; safe to run on every deploy."""
    batch = _client().batch()
    for card in FLEET:
        batch.set(_client().collection(COLLECTION).document(card.name), card.to_dict())
    batch.commit()
    return len(FLEET)


def discover(
    capability: str | None = None, department: str | None = None
) -> list[AgentCard]:
    """Find agents by what they do or who owns them.

    Args:
        capability: Only return agents publishing this capability.
        department: Only return agents owned by this department.

    Returns:
        Matching agent cards, ordered by name.
    """
    query = _client().collection(COLLECTION)
    if capability:
        query = query.where("capabilities", "array_contains", capability)
    if department:
        query = query.where("department", "==", department)
    return sorted(
        (AgentCard.from_dict(d.to_dict()) for d in query.stream()),
        key=lambda c: c.name,
    )


def get(name: str) -> AgentCard | None:
    """Look up a single agent card by name."""
    doc = _client().collection(COLLECTION).document(name).get()
    return AgentCard.from_dict(doc.to_dict()) if doc.exists else None
