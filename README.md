# All Things Agentic — Day-1 Spike

Deployment spike for the [All Things Agentic Hackathon](https://allthingsagentichackathon.devpost.com/)
(Google, submissions close **31 Aug 2026, 5:00 PM PDT**).

This is not the product. It exists to prove the deploy path end to end — a
Gemini 3.5 call, running on Cloud Run, writing durable state to Firestore —
so that authentication, region, quota and container surprises surface now
rather than on deadline weekend.

## Stack requirements this satisfies

The hackathon screens submissions on three mandatory technologies before any
scoring happens. All three are exercised here:

| Requirement | Satisfied by |
| --- | --- |
| Gemini 3.5 or newer | `gemini-3.5-flash` via Vertex AI (`spike_agent/agent.py`) |
| A Google agent framework | Google ADK 2.6.3 (`google-adk`) |
| A Google Cloud service | Cloud Run (host) + Firestore (run event log) |

> The ADK README quickstart still shows `gemini-2.5-flash`. Copying it verbatim
> would fail the stack screen — the model is pinned to 3.5 here and overridable
> via `GEMINI_MODEL`.

## Layout

```
main.py              FastAPI wrapper ADK serves on Cloud Run
spike_agent/
  agent.py           root_agent + two Firestore tools
  __init__.py
deploy.sh            one-shot deploy: enables APIs, creates Firestore, ships
Dockerfile           python:3.13-slim
requirements.txt
```

## Run locally

Requires Python 3.13 specifically — `python3` on this machine currently
resolves to 3.14, which does not match the container.

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp .env.example .env        # then fill in GOOGLE_CLOUD_PROJECT
set -a && source .env && set +a

./.venv/bin/python main.py  # http://localhost:8080
```

The ADK dev UI is served at the root. Pick `spike_agent`, then ask it
something like *"log that the evidence collector finished for run demo-1"* and
confirm the document lands in Firestore.

## Deploy to Cloud Run

Requires an authenticated gcloud session (`gcloud auth login` opens a browser)
and a GCP project with billing enabled.

```bash
gcloud auth login
gcloud auth application-default login

set -a && source .env && set +a
./deploy.sh
```

`deploy.sh` enables the required APIs, creates the default Firestore database
if absent, deploys from source, and prints the service URL. Verify with:

```bash
curl -s "$URL/healthz"
```

## Verified so far

- [x] gcloud CLI 580.0.0 installed and on PATH
- [x] ADK 2.6.3 installed on Python 3.13
- [x] `root_agent` loads with `gemini-3.5-flash`, both tools registered
- [x] FastAPI app builds, `/healthz` route present
- [ ] `gcloud auth login` — needs an interactive browser session
- [ ] Firestore database created
- [ ] Deployed to Cloud Run, live URL responding
- [ ] Agent round-trip: prompt in → Firestore document out

## Not done here, deliberately

Sessions use ephemeral SQLite, so they do not survive a Cloud Run revision.
Firestore-backed sessions, Pub/Sub dispatch and the operator console belong to
the real build, once the track and product are locked.
