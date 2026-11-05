# GCP setup for the spike-engine PoC (BR-20..25, BR-70..77, §13)

Account: **elms@thecollcon.com**. These are the commands to review and run together. Claudia wrote them, but she could not run them from her cloud workspace, because its network policy blocks Google APIs.

Nothing has been created yet. Every command is read-only toward the **target** project, except creating the test workload in step 2, which you opt into.

```bash
# Fill these in first
export HOST=devrails-core-dev        # DevRails dev host (E, N3 2026-10-27): the existing dev Firebase project.
                                     # Confirm the exact ID in step 1; Firebase may have added a suffix.
export TARGET=devrails-poc-target    # the monitored project (E, N3; TASK-031). New.
export REGION=us-central1
export BILLING=XXXXXX-XXXXXX-XXXXXX  # gcloud billing accounts list
export SA=devrails-spike-engine-poc
export SCHED_SA=devrails-scheduler-poc
```

## 0. Sign in

```bash
gcloud auth login elms@thecollcon.com
gcloud config set account elms@thecollcon.com
```

## 1. Projects

**Host: check `devrails-core-dev`, don't create it.** These commands are read-only:

```bash
gcloud projects list --filter="projectId~devrails"                # exact IDs
gcloud billing projects describe $HOST                            # billingEnabled must be true (Blaze)
gcloud firestore databases list --project=$HOST                   # is there a (default) Native database, and where?
```

If billing is off, link it with `gcloud billing projects link $HOST --billing-account=$BILLING`. Cloud Run Jobs, Scheduler and Cloud Build need it. Only if no database exists, create one in a location you choose:

```bash
gcloud firestore databases create --location=nam5 --project=$HOST
```

**Prod later:** `devrails-core-prod` (LEDGER-01) gets the same steps for the PoC acceptance run.

Create the target project. It must be on the same billing account as the free tier it watches.

```bash
gcloud projects create $TARGET --name="DevRails PoC target"
gcloud billing projects link $TARGET --billing-account=$BILLING
```

## 2. APIs, and an optional test workload in the target (D1)

```bash
gcloud services enable run.googleapis.com cloudscheduler.googleapis.com monitoring.googleapis.com \
  firestore.googleapis.com iam.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com \
  --project=$HOST
gcloud services enable monitoring.googleapis.com run.googleapis.com storage.googleapis.com --project=$TARGET

# Optional D1 workload: one hello-world service (min instances 0) and one bucket
gcloud run deploy hello --image=us-docker.pkg.dev/cloudrun/container/hello --region=$REGION \
  --project=$TARGET --allow-unauthenticated --min-instances=0 --max-instances=1
gcloud storage buckets create gs://$TARGET-poc-bucket --location=$REGION --project=$TARGET
```

> **Heads-up for D1.** The free tier is shared across the whole billing account. Pushing the test project past 75% or 90% on purpose uses up the same allowance as your other projects. We should agree on the load test before running one.

## 3. Identities and IAM (least privilege)

```bash
gcloud iam service-accounts create $SA --project=$HOST --display-name="DevRails spike-engine (PoC)"
gcloud iam service-accounts create $SCHED_SA --project=$HOST --display-name="DevRails scheduler (PoC)"

# Read-only on the monitored project (BR-20): the only role DevRails gets on the target
gcloud projects add-iam-policy-binding $TARGET \
  --member=serviceAccount:$SA@$HOST.iam.gserviceaccount.com --role=roles/monitoring.viewer

# Feed writes in the host project (BR-25)
gcloud projects add-iam-policy-binding $HOST \
  --member=serviceAccount:$SA@$HOST.iam.gserviceaccount.com --role=roles/datastore.user

# Bills Monitoring reads to the host project, never the customer's (BR-74, BR-16).
# Approved by E on 2026-10-27. It is DevRails' own project; the target gets nothing new.
gcloud projects add-iam-policy-binding $HOST \
  --member=serviceAccount:$SA@$HOST.iam.gserviceaccount.com --role=roles/serviceusage.serviceUsageConsumer
```

This setup is **keyless** [PROPOSED N2]: the Cloud Run Job runs as `$SA` and uses its own credentials.

If you keep the SSOT key path instead (Q7/Q11/Q28), add these steps:

1. Create a key for a Monitoring Viewer SA.
2. Store it as the Secret Manager secret `devrails-poc-monitoring-sa-key`.
3. Grant `$SA` `roles/secretmanager.secretAccessor` on that secret only.
4. Add `--set-secrets=/secrets/sa.json=devrails-poc-monitoring-sa-key:latest` and `GOOGLE_APPLICATION_CREDENTIALS=/secrets/sa.json` to step 4.

The engine code is the same either way.

## 4. Build and deploy the Cloud Run Job (BR-05, BR-70, BR-71)

```bash
gcloud artifacts repositories create devrails --repository-format=docker --location=$REGION --project=$HOST
gcloud builds submit spike-engine --project=$HOST \
  --tag=$REGION-docker.pkg.dev/$HOST/devrails/spike-engine:poc

gcloud run jobs deploy devrails-spike-engine --project=$HOST --region=$REGION \
  --image=$REGION-docker.pkg.dev/$HOST/devrails/spike-engine:poc \
  --service-account=$SA@$HOST.iam.gserviceaccount.com \
  --tasks=1 --max-retries=0 --task-timeout=120s --cpu=1 --memory=512Mi \
  --set-env-vars=DEVRAILS_GCP_PROJECT_ID=$TARGET,DEVRAILS_FIREBASE_PROJECT_ID=$HOST,DEVRAILS_QUOTA_PROJECT_ID=$HOST,DEVRAILS_POC_USER_UID=<E_FIREBASE_UID>,DEVRAILS_POC_PROJECT_ID=$TARGET,DEVRAILS_POLLING_INTERVAL_MINUTES=10
```

The engine refuses to start if `DEVRAILS_QUOTA_PROJECT_ID` is empty or equals `$TARGET`. That way, DevRails' reads can never fall back to the customer's project.

Why these settings:

- `--max-retries=0`: a failed poll already writes Sync Failed, and the next scheduled run, 10 minutes later, is the retry.
- A Job has no endpoint and can never stay warm.

## 5. Provision the feed stub, then run one poll

```bash
gcloud run jobs execute devrails-spike-engine --project=$HOST --region=$REGION --wait \
  --args=provision,--uid,<E_FIREBASE_UID>,--project,$TARGET
gcloud run jobs execute devrails-spike-engine --project=$HOST --region=$REGION --wait
gcloud logging read 'resource.type="cloud_run_job" AND jsonPayload.component="spike-engine"' \
  --project=$HOST --limit=5 --format='value(jsonPayload.event,jsonPayload.system_status,jsonPayload.error_class)'
```

## 6. Schedule every 10 minutes (BR-70)

```bash
gcloud run jobs add-iam-policy-binding devrails-spike-engine --project=$HOST --region=$REGION \
  --member=serviceAccount:$SCHED_SA@$HOST.iam.gserviceaccount.com --role=roles/run.invoker
gcloud scheduler jobs create http devrails-spike-engine-10m --project=$HOST --location=$REGION \
  --schedule="*/10 * * * *" --http-method=POST \
  --uri="https://run.googleapis.com/v2/projects/$HOST/locations/$REGION/jobs/devrails-spike-engine:run" \
  --oauth-service-account-email=$SCHED_SA@$HOST.iam.gserviceaccount.com \
  --max-retry-attempts=1
```

## 7. Safety net: an alert-only budget (BR-72; amount is for E/Valerie to confirm)

```bash
gcloud billing budgets create --billing-account=$BILLING --display-name="DevRails PoC safety net" \
  --budget-amount=5USD --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
```

A budget sends alerts only. It does not cap spending.

## 8. LEDGER-09: who pays for the Monitoring reads (BR-74)

Do not claim "no added customer cost" until this test proves it.

1. Run a handful of polls.
2. Check **APIs & Services → Cloud Monitoring API → Metrics** in both projects.
3. The `timeSeries.list` calls should be counted under `$HOST` (the quota project), not `$TARGET`.

## 9. Local development on the Mac (no key needed)

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project $HOST
cd spike-engine && python -m venv .venv && . .venv/bin/activate && pip install -r requirements-dev.txt
DEVRAILS_GCP_PROJECT_ID=$TARGET DEVRAILS_POC_USER_UID=local DEVRAILS_POC_PROJECT_ID=$TARGET \
  python main.py --dry-run        # reads Cloud Monitoring, prints the payload, writes nothing
```

## 10. Teardown (BR-24, TASK-142)

```bash
gcloud scheduler jobs delete devrails-spike-engine-10m --project=$HOST --location=$REGION
gcloud run jobs delete devrails-spike-engine --project=$HOST --region=$REGION
gcloud projects remove-iam-policy-binding $TARGET \
  --member=serviceAccount:$SA@$HOST.iam.gserviceaccount.com --role=roles/monitoring.viewer
# Key path only: disable/delete the SA key, then destroy the secret versions
```
