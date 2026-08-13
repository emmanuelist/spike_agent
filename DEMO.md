# Custodian — the four-minute demo

This file is the scope contract. It was written before the build, and it wins
every argument about what to add. **If a capability does not appear in a beat
below, it is out of scope.** Cut features to protect these four minutes, never
the reverse.

Target: ~4:00. Judges score "Demo & Production Readiness" at 30%, and the same
weight again on architecture that this demo has to make visible.

---

## Beat 1 — The problem, stated once (0:00–0:30)

On screen: an intake queue with a new request. *"Delete everything you hold
about me."* A statutory clock reads 30 days.

Spoken: an enterprise receives these constantly. Today a human emails four
system owners, waits, chases, and assembles a spreadsheet. It takes weeks, it
is error-prone, and missing one store is a regulatory finding.

No product tour. No architecture talk. Thirty seconds, then move.

## Beat 2 — The fleet, not a chatbot (0:30–1:00)

On screen: the agent registry. Four departments own agents — Data Engineering,
Security, Legal, Support — each entry showing version, declared capabilities,
the data scopes it may touch, and whether it requires human approval.

Spoken: this is a catalog other teams discover agents through, not a script.

**Requires:** registry populated and rendered; scopes and approval flags real,
not decorative.

## Beat 3 — Autonomous fan-out (1:00–2:00)

The operator accepts the request. One click, then nothing to do but watch.

On screen: Pub/Sub dispatch, then four discovery agents running **in parallel**
across Cloud SQL, Firestore, Cloud Storage and a mock support-desk API. The run
timeline fills in live — each agent reporting matches found, fields classified,
confidence, and elapsed time.

Spoken, over the top: this is the beat that proves it isn't a chat loop. The
work is asynchronous and long-running; the operator could close the tab.

**Requires:** genuine parallel execution with visibly staggered completion.
Seeded data must be messy enough that discovery is non-trivial — the same person
under a different email in one store, an orphaned record in another.

## Beat 4 — The security stance (2:00–2:30)

On screen: the evidence panel for one match, then the exact prompt that agent
sent to Gemini — showing tokens and field metadata where the personal data
would be.

Spoken: the fleet located this person's records without any agent receiving a
single raw value. Models reason over field-level metadata and tokenized
projections; values stay in the datastore behind a resolver the model cannot
call.

This is the thirty seconds a judge remembers. It must be shown, not claimed.

**Requires:** prompt inspection view; tokenization real and verifiable.

## Beat 5 — The gate (2:30–3:05)

On screen: Legal's queue. A lawful-basis assessment with citations back to
specific records, and one record flagged **retain** — an invoice under a
statutory retention obligation that must survive the deletion.

The reviewer approves with the exception intact.

Spoken: the fleet proposes; a human with authority disposes. Nothing irreversible
happens without this click.

**Requires:** at least one genuine exception. A demo where the agent is
uniformly right is less convincing than one where it correctly flags a conflict.

## Beat 6 — Execution and receipts (3:05–3:40)

On screen: deletion executes per store. Each returns a signed receipt. A
verification pass re-runs discovery and reports zero remaining matches except
the retained invoice.

Spoken: the request closes with an audit certificate — what was found, what was
deleted, what was retained and under which legal basis, who approved.

**Requires:** verification must be a real second pass, not a rendered message.

## Beat 7 — Proof it ran on Google Cloud (3:40–4:00)

On screen: Cloud Trace showing the distributed trace for the run — the parallel
fan-out visible as spans — then Cloud Run revisions and the Firestore audit
collection.

The rules require the demo show the Google Cloud backend in operation. This beat
is not optional and it is not padding.

---

## Explicitly not in this demo

Multi-tenant onboarding · configurable policy authoring · connector marketplace ·
access-request (SAR) flows beyond erasure · anything requiring narration to
justify.

## Recording notes

- Seed and rehearse against a **fixed** dataset; a run that varies between takes
  will cost hours.
- Expect the fan-out to be too fast to read. Do not fake latency — stagger the
  seeded workloads so the parallelism is genuinely visible.
- Record the Cloud Trace beat last, from the real run captured in beats 3–6.
