#!/usr/bin/env bash
# Build the image (tagged with the git SHA), run migrations, then roll out the service.
set -euo pipefail
cd "$(dirname "$0")"; source env.sh
G="--project=$PROJECT"
TAG=$(git rev-parse --short HEAD); IMAGE="$IMAGE_BASE:$TAG"

gcloud builds submit .. --config=cloudbuild.yaml --substitutions=_IMAGE="$IMAGE" $G

COMMON_SECRETS="DATABASE_URL=DATABASE_URL:latest,JWT_SECRET=JWT_SECRET:latest"
COMMON_ENV="ENV=prod,ATTACHMENTS_BACKEND=gcs,ATTACHMENTS_BUCKET=$BUCKET,STAFF_EMAIL_DOMAINS=liverx.me,TRUST_PROXY=true,SWEEPS_MODE=off"

# Migrations job: created or updated, then executed to completion before traffic moves.
JOB_FLAGS=(--image="$IMAGE" --region=$REGION --service-account=$RUN_SA --set-cloudsql-instances=$SQL_CONN
  --set-secrets="$COMMON_SECRETS" --set-env-vars="$COMMON_ENV,SWEEP_AUDIENCE=x,SWEEP_INVOKER_EMAIL=x"
  --max-retries=0 $G)
if gcloud run jobs describe helpdesk-migrate --region=$REGION $G >/dev/null 2>&1; then
  gcloud run jobs update helpdesk-migrate "${JOB_FLAGS[@]}" --command=alembic --args=upgrade,head
else
  gcloud run jobs create helpdesk-migrate "${JOB_FLAGS[@]}" --command=alembic --args=upgrade,head
fi
gcloud run jobs execute helpdesk-migrate --region=$REGION --wait $G

# Reference data (SLA policies, categories); idempotent. A ticket can't be created without a policy.
if gcloud run jobs describe helpdesk-seed --region=$REGION $G >/dev/null 2>&1; then VERB=update; else VERB=create; fi
gcloud run jobs $VERB helpdesk-seed "${JOB_FLAGS[@]}" --command=python --args=-m,app.seed_reference
gcloud run jobs execute helpdesk-seed --region=$REGION --wait $G

# The first deploy needs its own URL for SWEEP_AUDIENCE: deploy, read it, redeploy.
deploy() {
  gcloud run deploy $SERVICE --image="$IMAGE" --region=$REGION --service-account=$RUN_SA \
    --allow-unauthenticated --min-instances=0 --max-instances=3 --cpu=1 --memory=512Mi \
    --concurrency=40 --cpu-throttling --add-cloudsql-instances=$SQL_CONN \
    --set-secrets="$COMMON_SECRETS" \
    --set-env-vars="$COMMON_ENV,SWEEP_AUDIENCE=$1,SWEEP_INVOKER_EMAIL=$SCHED_SA" $G
}
URL=$(gcloud run services describe $SERVICE --region=$REGION --format='value(status.url)' $G 2>/dev/null || true)
if [ -z "$URL" ]; then
  deploy placeholder
  URL=$(gcloud run services describe $SERVICE --region=$REGION --format='value(status.url)' $G)
fi
deploy "$URL"
echo "URL: $URL"

gcloud run services add-iam-policy-binding $SERVICE --region=$REGION \
  --member="serviceAccount:$SCHED_SA" --role=roles/run.invoker $G >/dev/null

SCHED_FLAGS=(--location=$REGION --schedule="* * * * *" --uri="$URL/api/internal/sweeps" --http-method=POST
  --oidc-service-account-email=$SCHED_SA --oidc-token-audience="$URL" $G)
if gcloud scheduler jobs describe helpdesk-sweeps --location=$REGION $G >/dev/null 2>&1; then
  gcloud scheduler jobs update http helpdesk-sweeps "${SCHED_FLAGS[@]}"
else
  gcloud scheduler jobs create http helpdesk-sweeps "${SCHED_FLAGS[@]}"
fi
