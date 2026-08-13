#!/usr/bin/env bash
# Remove everything Custodian provisions. Run after the submission is judged.
#
# The largest post-hackathon billing risk is not the demo itself, it is a
# Cloud SQL instance left provisioned for months. Cloud Run and Firestore cost
# nothing when idle; Cloud SQL bills for instance time regardless of traffic.
set -euo pipefail

: "${GOOGLE_CLOUD_PROJECT:?set GOOGLE_CLOUD_PROJECT}"
: "${GOOGLE_CLOUD_LOCATION:=us-central1}"

echo "This deletes Custodian resources in project: $GOOGLE_CLOUD_PROJECT"
read -r -p "Type the project ID to confirm: " CONFIRM
[ "$CONFIRM" = "$GOOGLE_CLOUD_PROJECT" ] || { echo "Aborted."; exit 1; }

echo "==> Cloud Run services"
for svc in custodian-console spike-agent; do
  gcloud run services delete "$svc" --region "$GOOGLE_CLOUD_LOCATION" --quiet 2>/dev/null \
    || echo "    ($svc not present)"
done

echo "==> Cloud SQL instances (the expensive ones)"
for inst in $(gcloud sql instances list --format='value(name)' 2>/dev/null); do
  gcloud sql instances delete "$inst" --quiet
done

echo "==> Cloud Storage buckets"
for b in $(gcloud storage buckets list --format='value(name)' 2>/dev/null | grep -i custodian || true); do
  gcloud storage rm -r "gs://$b" --quiet 2>/dev/null || true
done

echo "==> Pub/Sub topics and subscriptions"
for t in $(gcloud pubsub topics list --format='value(name)' 2>/dev/null | grep -i custodian || true); do
  gcloud pubsub topics delete "$t" --quiet
done

echo "==> Artifact Registry images"
for r in $(gcloud artifacts repositories list --location="$GOOGLE_CLOUD_LOCATION" \
             --format='value(name)' 2>/dev/null | grep -i 'cloud-run-source-deploy' || true); do
  gcloud artifacts repositories delete "$r" --location="$GOOGLE_CLOUD_LOCATION" --quiet
done

cat <<EOF

==> Done. Firestore was left alone — it holds the audit trail and costs nothing
    idle. Delete the database manually if you want it gone.

    The cleanest guarantee is to delete the whole project:
      gcloud projects delete $GOOGLE_CLOUD_PROJECT

    Note that a deleted project ID can never be reused.
EOF
