#!/usr/bin/env bash
# Day-1 spike deploy. Run after `gcloud auth login` has completed.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT (see .env.example)}"
: "${GOOGLE_CLOUD_LOCATION:=us-central1}"
SERVICE_NAME="${SERVICE_NAME:-spike-agent}"

echo "==> project=$GOOGLE_CLOUD_PROJECT region=$GOOGLE_CLOUD_LOCATION service=$SERVICE_NAME"

gcloud config set project "$GOOGLE_CLOUD_PROJECT"

echo "==> enabling APIs (idempotent, slow the first time)"
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  firestore.googleapis.com \
  aiplatform.googleapis.com

# Firestore allows exactly one default database per project, and creation fails
# if one already exists. Tolerate that rather than making the script one-shot.
echo "==> ensuring Firestore database exists"
gcloud firestore databases create --location=nam5 2>/dev/null \
  || echo "    (already exists, continuing)"

echo "==> deploying to Cloud Run from source"
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --region "$GOOGLE_CLOUD_LOCATION" \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --allow-unauthenticated \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$GOOGLE_CLOUD_PROJECT,GOOGLE_CLOUD_LOCATION=$GOOGLE_CLOUD_LOCATION,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GEMINI_MODEL=${GEMINI_MODEL:-gemini-3.5-flash}"

URL=$(gcloud run services describe "$SERVICE_NAME" \
  --region "$GOOGLE_CLOUD_LOCATION" --format='value(status.url)')

echo
echo "==> deployed: $URL"
echo "==> health:   $URL/healthz"
echo "==> dev UI:   $URL  (pick 'spike_agent', then ask it to log a run event)"
