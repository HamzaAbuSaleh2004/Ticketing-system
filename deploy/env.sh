# Shared settings. Sourced by the other scripts.
export PROJECT=help-desk-liverx
export REGION=us-central1
export SQL_INSTANCE=helpdesk-db
export SQL_CONN="$PROJECT:$REGION:$SQL_INSTANCE"
export BUCKET="$PROJECT-helpdesk-attachments"
export REPO=helpdesk
export SERVICE=helpdesk
export RUN_SA="helpdesk-run@$PROJECT.iam.gserviceaccount.com"
export SCHED_SA="helpdesk-scheduler@$PROJECT.iam.gserviceaccount.com"
export IMAGE_BASE="$REGION-docker.pkg.dev/$PROJECT/$REPO/helpdesk"
