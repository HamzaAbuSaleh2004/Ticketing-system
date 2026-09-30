#!/usr/bin/env bash
# One-off: create the first admin. Generates a random password, keeps it in a
# temporary secret, runs a job, deletes the secret. The password is written to
# a local file (never printed). Usage: create-admin.sh EMAIL "Full Name" PASSWORD_FILE
set -euo pipefail
cd "$(dirname "$0")"; source env.sh
G="--project=$PROJECT"; EMAIL=$1; NAME=$2; OUT=$3
IMAGE=$(gcloud run jobs describe helpdesk-migrate --region=$REGION --format='value(spec.template.spec.template.spec.containers[0].image)' $G)
python -c "import secrets;print(secrets.token_urlsafe(18)+'aA1!',end='')" > "$OUT"
gcloud secrets create ADMIN_PASSWORD --replication-policy=automatic --data-file="$OUT" $G
trap 'gcloud secrets delete ADMIN_PASSWORD --quiet --project='"$PROJECT" EXIT
gcloud secrets add-iam-policy-binding ADMIN_PASSWORD --member="serviceAccount:$RUN_SA" --role=roles/secretmanager.secretAccessor $G >/dev/null
gcloud run jobs deploy helpdesk-create-admin --image="$IMAGE" --region=$REGION --service-account=$RUN_SA \
  --set-cloudsql-instances=$SQL_CONN \
  --set-secrets="DATABASE_URL=DATABASE_URL:latest,JWT_SECRET=JWT_SECRET:latest,ADMIN_PASSWORD=ADMIN_PASSWORD:latest" \
  --set-env-vars="ENV=prod,ATTACHMENTS_BACKEND=gcs,ATTACHMENTS_BUCKET=$BUCKET,SWEEP_AUDIENCE=x,SWEEP_INVOKER_EMAIL=x" \
  --command=python --args=-m,app.create_admin,--email,"$EMAIL",--name,"$NAME" --max-retries=0 $G
gcloud run jobs execute helpdesk-create-admin --region=$REGION --wait $G
