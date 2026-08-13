"""Day-1 spike agent.

Exists to prove one thing end to end: a Gemini 3.5 call running on Cloud Run
that writes durable state to Firestore. No product logic lives here yet.

The one tool it carries — an append-only run event log — is the primitive the
Fortified Enterprise Fleet track calls an audit trail, so it survives into the
real build even though the rest of this package does not.
"""

import os
import uuid
from datetime import datetime, timezone

from google.adk import Agent
from google.cloud import firestore

# The hackathon requires Gemini 3.5 or newer. The ADK README still shows
# gemini-2.5-flash in its quickstart; using that example verbatim would fail
# the stack screen.
MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

RUNS_COLLECTION = "runs"

_db: firestore.Client | None = None


def _client() -> firestore.Client:
    """Lazily create the Firestore client so imports stay cheap and testable."""
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def record_run_event(run_id: str, stage: str, detail: str) -> dict:
    """Append an event to a run's audit trail in Firestore.

    Use this to log every meaningful step taken during a run so the trail can
    be replayed and cited later.

    Args:
        run_id: Identifier for the run this event belongs to.
        stage: Short label for the step, such as "collect" or "verify".
        detail: Human-readable description of what happened.

    Returns:
        A dict containing the stored event_id and the run_id it was filed under.
    """
    event_id = uuid.uuid4().hex
    event = {
        "event_id": event_id,
        "run_id": run_id,
        "stage": stage,
        "detail": detail,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    _client().collection(RUNS_COLLECTION).document(run_id).collection(
        "events"
    ).document(event_id).set(event)
    return {"event_id": event_id, "run_id": run_id}


def read_run_events(run_id: str) -> dict:
    """Read back the full audit trail for a run, oldest event first.

    Args:
        run_id: Identifier for the run to read.

    Returns:
        A dict with the run_id and a list of its recorded events.
    """
    docs = (
        _client()
        .collection(RUNS_COLLECTION)
        .document(run_id)
        .collection("events")
        .order_by("recorded_at")
        .stream()
    )
    return {"run_id": run_id, "events": [d.to_dict() for d in docs]}


root_agent = Agent(
    name="spike_agent",
    model=MODEL,
    instruction=(
        "You are an operations agent proving out a deployment path. "
        "When the user describes work that was performed, record it with "
        "record_run_event, inventing a short run_id if none was given. "
        "When asked what happened during a run, read it back with "
        "read_run_events and summarise the trail in order. "
        "Always state the run_id you used so it can be looked up again."
    ),
    tools=[record_run_event, read_run_events],
)
