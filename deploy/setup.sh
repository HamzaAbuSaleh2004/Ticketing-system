#!/usr/bin/env bash
# One-time (idempotent) infrastructure setup. Creates billable resources:
# Cloud SQL db-f1-micro (~$8-9/month) is the main cost.
set -euo pipefail
cd "$(dirname "$0")"; source env.sh
G="--project=$PROJECT"

gcloud services enable run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com \
  cloudscheduler.googleapis.com artifactregistry.googleapis.com storage.googleapis.com \
  cloudbuild.googleapis.com iam.googleapis.com $G

for sa in helpdesk-run helpdesk-scheduler; do
  gcloud iam service-accounts describe "$sa@$PROJECT.iam.gserviceaccount.com" $G >/dev/null 2>&1 ||
    gcloud iam service-accounts create $sa --display-name="$sa" $G
done

gcloud artifacts repositories describe $REPO --location=$REGION $G >/dev/null 2>&1 ||
  gcloud artifacts repositories create $REPO --repository-format=docker --location=$REGION $G

if ! gcloud sql instances describe $SQL_INSTANCE $G >/dev/null 2>&1; then
  gcloud sql instances create $SQL_INSTANCE --database-version=POSTGRES_16 --edition=ENTERPRISE \
    --tier=db-f1-micro --region=$REGION --availability-type=zonal --storage-type=HDD \
    --storage-size=10GB --storage-auto-increase --backup-start-time=03:00 \
    --retained-backups-count=7 --deletion-protection $G
fi
gcloud sql databases describe helpdesk --instance=$SQL_INSTANCE $G >/dev/null 2>&1 ||
  gcloud sql databases create helpdesk --instance=$SQL_INSTANCE $G

secret_exists() { gcloud secrets describe "$1" $G >/dev/null 2>&1; }
if ! secret_exists DATABASE_URL; then
  DB_PASSWORD=$(python -c "import secrets;print(secrets.token_hex(24))")
  gcloud sql users create helpdesk --instance=$SQL_INSTANCE --password="$DB_PASSWORD" $G
  gcloud secrets create DATABASE_URL --replication-policy=automatic $G
  printf 'postgresql+asyncpg://helpdesk:%s@/helpdesk?host=/cloudsql/%s' "$DB_PASSWORD" "$SQL_CONN" |
    gcloud secrets versions add DATABASE_URL --data-file=- $G
  unset DB_PASSWORD
fi
if ! secret_exists JWT_SECRET; then
  gcloud secrets create JWT_SECRET --replication-policy=automatic $G
  python -c "import secrets;print(secrets.token_urlsafe(64),end='')" |
    gcloud secrets versions add JWT_SECRET --data-file=- $G
fi

gcloud storage buckets describe gs://$BUCKET $G >/dev/null 2>&1 ||
  gcloud storage buckets create gs://$BUCKET --location=$REGION --uniform-bucket-level-access \
    --public-access-prevention $G

# Least-privilege IAM
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$RUN_SA" --role=roles/cloudsql.client --condition=None >/dev/null
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$RUN_SA" --role=roles/logging.logWriter --condition=None >/dev/null
for s in DATABASE_URL JWT_SECRET; do
  gcloud secrets add-iam-policy-binding $s --member="serviceAccount:$RUN_SA" --role=roles/secretmanager.secretAccessor $G >/dev/null
done
gcloud storage buckets add-iam-policy-binding gs://$BUCKET --member="serviceAccount:$RUN_SA" --role=roles/storage.objectAdmin $G >/dev/null
echo "setup done"
