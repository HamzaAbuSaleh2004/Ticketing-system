# Deploying to Google Cloud

Project `help-desk-liverx`, region `us-central1`. Live URL: https://helpdesk-6macn4k47q-uc.a.run.app

- `setup.sh`: one-time, idempotent: APIs, service accounts, Artifact Registry, Cloud SQL (db-f1-micro, 7 daily backups, deletion protection), secrets, private bucket, IAM.
- `deploy.sh`: Cloud Build image (git SHA tag), migrations job, reference-data job, Cloud Run service, Scheduler sweep job (every minute). Re-run to redeploy.
- `create-admin.sh EMAIL "Name" PASSWORD_FILE`: first admin. The random password goes to a local file, and the temporary secret is deleted after the run. The admin enrols 2FA at first sign-in.

Cost: about $9-10/month, nearly all of it Cloud SQL. The existing $10 budget alert applies.

Not done: custom domain and load balancer (about $18/month extra); PITR is off; the backup restore drill is Phase 18.
