# Facebook Clone Backend — Runbook

> **Version:** 1.0 · **Last updated:** 2026-03-13
> **Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · Redis 7 · S3/MinIO · Docker · Kubernetes

---

## Table of Contents

1. [Quick Reference](#1-quick-reference)
2. [Environment Setup](#2-environment-setup)
3. [Deployment Procedures](#3-deployment-procedures)
4. [Scaling Guide](#4-scaling-guide)
5. [Backup & Restore](#5-backup--restore)
6. [Common Issues & Fixes](#6-common-issues--fixes)
7. [Health Check Endpoints](#7-health-check-endpoints)
8. [Monitoring Dashboards Guide](#8-monitoring-dashboards-guide)
9. [Incident Response Playbook](#9-incident-response-playbook)

---

## 1. Quick Reference

### Important URLs

| Service | Staging | Production |
|---|---|---|
| API Health | `https://staging-api.example.com/health` | `https://api.example.com/health` |
| API Readiness | `https://staging-api.example.com/ready` | `https://api.example.com/ready` |
| Prometheus Metrics | `https://staging-api.example.com/metrics` | `https://api.example.com/metrics` |
| Simple Metrics | `https://staging-api.example.com/metrics/simple` | `https://api.example.com/metrics/simple` |
| Grafana | `https://grafana.internal/d/facebook-clone` | `https://grafana.internal/d/facebook-clone-prod` |
| Jaeger UI | `https://jaeger.internal` | `https://jaeger.internal` |
| AlertManager | `https://alertmanager.internal` | `https://alertmanager.internal` |
| GitHub Actions | `https://github.com/org/facebook-clone/actions` | — |

### Key Commands Cheat Sheet

```bash
# ─── Cluster context ────────────────────────────────────────────────────────
kubectl config use-context staging-cluster
kubectl config use-context prod-cluster

# ─── Pod status ─────────────────────────────────────────────────────────────
kubectl get pods -n facebook-clone [-w]
kubectl get pods -n facebook-clone-staging [-w]

# ─── Logs ───────────────────────────────────────────────────────────────────
kubectl logs -n facebook-clone -l app=facebook-clone --tail=100 -f
kubectl logs -n facebook-clone-staging -l app=facebook-clone --tail=100 -f

# ─── Describe & events ──────────────────────────────────────────────────────
kubectl describe pod -n facebook-clone <pod-name>
kubectl get events -n facebook-clone --sort-by=.lastTimestamp

# ─── Exec into pod ──────────────────────────────────────────────────────────
kubectl exec -it -n facebook-clone <pod-name> -- /bin/sh

# ─── Scale manually ─────────────────────────────────────────────────────────
kubectl scale deployment facebook-clone-blue -n facebook-clone --replicas=5
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=5

# ─── HPA status ─────────────────────────────────────────────────────────────
kubectl get hpa -n facebook-clone
kubectl describe hpa facebook-clone-hpa -n facebook-clone

# ─── Blue/Green deploy ──────────────────────────────────────────────────────
./deploy/scripts/blue-green-deploy.sh production v1.2.3
./deploy/scripts/rollback.sh production

# ─── Tag release ────────────────────────────────────────────────────────────
./deploy/scripts/tag-release.sh patch   # 1.2.3 → 1.2.4
./deploy/scripts/tag-release.sh minor   # 1.2.3 → 1.3.0
./deploy/scripts/tag-release.sh major   # 1.2.3 → 2.0.0

# ─── Database migrations ────────────────────────────────────────────────────
alembic upgrade head
alembic downgrade -1
alembic current
alembic history

# ─── Redis CLI ──────────────────────────────────────────────────────────────
kubectl exec -it -n facebook-clone <redis-pod> -- redis-cli
redis-cli INFO memory
redis-cli DBSIZE

# ─── Health check ───────────────────────────────────────────────────────────
curl -s https://api.example.com/health | jq
curl -s https://api.example.com/ready | jq
curl -s https://api.example.com/metrics/simple | jq
```

### On-Call Escalation Contacts

| Level | Role | Name | Phone | Slack | Escalate After |
|---|---|---|---|---|---|
| L1 | On-Call Engineer | _TBD_ | _TBD_ | `@oncall-eng` | Immediate |
| L2 | Backend Lead | _TBD_ | _TBD_ | `@backend-lead` | 15 min (P0/P1) |
| L3 | Engineering Manager | _TBD_ | _TBD_ | `@eng-manager` | 30 min (P0) |
| L4 | CTO | _TBD_ | _TBD_ | `@cto` | 1 hr (P0 unresolved) |
| DB | DBA / Data Lead | _TBD_ | _TBD_ | `@dba` | Any DB incident |
| SEC | Security Lead | _TBD_ | _TBD_ | `@security` | Any security incident |

> PagerDuty escalation policy: `facebook-clone-production` service.
> Slack alerts channel: `#alerts-facebook-clone`.

---

## 2. Environment Setup

### 2.1 Development

#### Prerequisites

| Tool | Minimum Version | Install |
|---|---|---|
| Python | 3.12 | `pyenv install 3.12` or system package |
| Docker | 24.x | [docs.docker.com](https://docs.docker.com/get-docker/) |
| Docker Compose | v2.x | Bundled with Docker Desktop |
| make | any | `brew install make` / `apt install make` |
| psql (optional) | 16.x | For manual DB inspection |

#### Step-by-Step Setup

```bash
# 1. Clone the repository
git clone https://github.com/org/facebook-clone.git
cd facebook-clone

# 2. Create and activate virtual environment
python3.12 -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 3. Install application + dev dependencies
pip install -e ".[dev]"

# 4. Copy and configure environment variables
cp .env.example .env
# Edit .env — at minimum set:
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/facebook_clone
#   REDIS_URL=redis://localhost:6379/0
#   JWT_SECRET_KEY=dev-secret-change-in-production
#   STORAGE_BACKEND=local
#   DEBUG=true
#   CORS_ORIGINS=http://localhost:3000

# 5. Start backing services
docker compose up -d
# Starts: postgres:16-alpine, redis:7-alpine, minio

# 6. Wait for services to be healthy
docker compose ps                  # all services should show "healthy"

# 7. Run database migrations
alembic upgrade head
# Applies migrations 001 through 006

# 8. Start development server
uvicorn fb.main:create_app --factory --reload --host 0.0.0.0 --port 8000

# 9. Verify the server is running
curl http://localhost:8000/health
# Expected: {"status": "ok"}

curl http://localhost:8000/ready
# Expected: {"status": "ok", "db": "ok", "redis": "ok"}
```

#### Development Verification

```bash
# Run tests
pytest -x -q

# Run linter
ruff check .

# Run security scan
bandit -r src/
safety check

# Open interactive API docs
open http://localhost:8000/docs
```

---

### 2.2 Staging Environment

#### Prerequisites

- `kubectl` configured with access to the staging cluster
- `KUBECONFIG` pointing to staging cluster credentials
- GitHub repository access (for CI/CD)

```bash
# 1. Verify kubectl context
kubectl config current-context
# Should return: staging-cluster

# 2. Create namespace (first-time only)
kubectl create namespace facebook-clone-staging

# 3. Apply base RBAC and config
kubectl apply -k deploy/k8s/base/

# 4. Create secrets (first-time setup — replace placeholder values)
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone-staging \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:pass@postgres-host:5432/facebook_clone" \
  --from-literal=REDIS_URL="redis://redis-host:6379/0" \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=AWS_ACCESS_KEY_ID="<your-access-key>" \
  --from-literal=AWS_SECRET_ACCESS_KEY="<your-secret-key>"

# 5. Apply staging overlay
kubectl apply -k deploy/k8s/overlays/staging

# 6. Verify deployment rollout
kubectl rollout status deployment/facebook-clone-blue -n facebook-clone-staging
kubectl rollout status deployment/facebook-clone-green -n facebook-clone-staging

# 7. Verify pods are running
kubectl get pods -n facebook-clone-staging
# All pods should be in Running state

# 8. Check readiness
STAGING_URL=https://staging-api.example.com
curl -s $STAGING_URL/ready | jq
# Expected: {"status": "ok", "db": "ok", "redis": "ok"}
```

---

### 2.3 Production Environment

#### Automated Deploy (Recommended)

Production deploys are triggered via GitHub Actions **manual dispatch**:

1. Go to **Actions → cd.yml → Run workflow**
2. Select `branch: main`
3. Set `environment: production`
4. Optionally set `image_tag` (defaults to latest SHA)
5. Click **Run workflow**
6. Monitor the `deploy-production` job logs

#### Manual Deploy (Break-Glass)

Use only when GitHub Actions is unavailable:

```bash
# 1. Set context to production
kubectl config use-context prod-cluster

# 2. Run blue/green deploy script
./deploy/scripts/blue-green-deploy.sh production <image-tag>
# e.g.: ./deploy/scripts/blue-green-deploy.sh production v1.4.2

# 3. Monitor the deploy output
# Script will print: current slot, new slot, rollout progress, health check, switch confirmation

# 4. Final health verification
curl -s https://api.example.com/health | jq
curl -s https://api.example.com/ready | jq
curl -s https://api.example.com/metrics/simple | jq
```

---

## 3. Deployment Procedures

### 3.1 Blue/Green Deploy

The blue/green strategy maintains two identical deployments (`slot=blue` and `slot=green`). Traffic routes to the currently active slot via the service selector. The inactive slot receives the new image and is warmed up before traffic switches.

#### Step-by-Step

```bash
# Step 1: Identify the current active slot
ACTIVE=$(kubectl get service facebook-clone -n facebook-clone \
  -o jsonpath='{.spec.selector.slot}')
echo "Current active slot: $ACTIVE"
# Output: blue  (or green)

# The inactive slot is the deploy target
INACTIVE=$([ "$ACTIVE" = "blue" ] && echo "green" || echo "blue")
echo "Deploy target: $INACTIVE"

# Step 2: Update the inactive deployment with the new image
IMAGE="ghcr.io/org/facebook-clone:v1.4.2"
kubectl set image deployment/facebook-clone-$INACTIVE \
  app=$IMAGE \
  -n facebook-clone

# Step 3: Wait for rollout to complete (default timeout: 10 minutes)
kubectl rollout status deployment/facebook-clone-$INACTIVE \
  -n facebook-clone \
  --timeout=600s

# Step 4: Verify health on the inactive slot (direct pod check)
POD=$(kubectl get pods -n facebook-clone -l slot=$INACTIVE \
  -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n facebook-clone $POD -- \
  wget -qO- http://localhost:8000/ready
# Must return: {"status": "ok", "db": "ok", "redis": "ok"}

# Step 5: Switch the service selector to the new slot
kubectl patch service facebook-clone -n facebook-clone \
  -p "{\"spec\":{\"selector\":{\"slot\":\"$INACTIVE\"}}}"
echo "Traffic now routed to: $INACTIVE"

# Step 6: Verify traffic is reaching the new slot
curl -s https://api.example.com/health | jq
curl -s https://api.example.com/ready | jq

# Step 7: Monitor error rates for 5 minutes post-switch
# Watch the Grafana dashboard or run:
watch -n 5 'curl -s https://api.example.com/metrics/simple | jq'
# Prometheus query for error rate:
# sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))
# Acceptable threshold: < 1%
```

> **Note:** The `deploy/scripts/blue-green-deploy.sh` script automates all steps above. Use the manual procedure only for debugging or when the script fails.

---

### 3.2 Rollback Procedure

Rollback switches the service selector back to the previously active slot. It is near-instantaneous (~30 seconds).

#### When to Roll Back

| Signal | Threshold | Action |
|---|---|---|
| HTTP 5xx error rate | > 5% for 2+ minutes | Rollback immediately |
| P99 latency | > 3s for 2+ minutes | Investigate; rollback if worsening |
| Pod crash loops | > 3 restarts in 5 min | Rollback immediately |
| Health check failing | `/ready` returning 503 | Rollback immediately |

#### Immediate Rollback (~30 seconds)

```bash
# Option A: Use the rollback script (recommended)
./deploy/scripts/rollback.sh production

# Option B: Manual patch
ACTIVE=$(kubectl get service facebook-clone -n facebook-clone \
  -o jsonpath='{.spec.selector.slot}')
PREVIOUS=$([ "$ACTIVE" = "blue" ] && echo "green" || echo "blue")

kubectl patch service facebook-clone -n facebook-clone \
  -p "{\"spec\":{\"selector\":{\"slot\":\"$PREVIOUS\"}}}"
echo "Rolled back to slot: $PREVIOUS"
```

#### What the Rollback Does

1. Queries the currently active slot from the service selector
2. Switches the service selector to the other slot (which still runs the previous image)
3. All new connections immediately route to the old version
4. In-flight requests on the new slot complete or time out gracefully (connection draining)
5. The failed deployment remains in the inactive slot for post-mortem investigation

#### Post-Rollback Verification

```bash
# 1. Confirm traffic is flowing to the old slot
kubectl get service facebook-clone -n facebook-clone \
  -o jsonpath='{.spec.selector.slot}'

# 2. Check error rate has recovered
curl -s https://api.example.com/metrics/simple | jq

# 3. Verify all pods are healthy
kubectl get pods -n facebook-clone

# 4. Alert the team
# Post to #incidents: "Rollback to <previous-version> completed at <time>. Investigating root cause."
```

---

## 4. Scaling Guide

### 4.1 When to Scale

| Signal | Threshold | Recommended Action |
|---|---|---|
| CPU utilization | > 70% sustained for 5+ min | HPA will auto-scale; verify it is working |
| Memory utilization | > 80% sustained for 5+ min | HPA will auto-scale; check for leaks |
| WebSocket connections | > 100 per pod average | HPA will auto-scale |
| P99 response latency | > 2s for 5+ min | Scale app; check DB query times |
| Request queue depth | Growing monotonically | Scale app pods; check downstream bottlenecks |
| DB connection wait time | > 5s | Increase connection pool; scale DB read replicas |
| Redis memory | > 80% | Increase Redis memory; review eviction policy |

### 4.2 How to Scale

#### Automatic (HPA — Preferred)

The HPA is configured with `min=2, max=20` and scales on CPU > 70%, Memory > 80%, or WebSocket connections > 100. Check HPA status:

```bash
kubectl get hpa -n facebook-clone
kubectl describe hpa facebook-clone-hpa -n facebook-clone

# View current metrics driving HPA decisions
kubectl top pods -n facebook-clone
```

#### Manual Override

```bash
# Scale both slots to handle a traffic spike immediately
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=8
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=8

# Restore HPA control afterward (set replicas back to HPA min)
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=2
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=2
```

#### Vertical Scaling (Update Resource Requests)

Edit the deployment manifest and increase `resources.requests` / `resources.limits`, then reapply. Trigger a rolling restart:

```bash
kubectl rollout restart deployment/facebook-clone-blue -n facebook-clone
kubectl rollout restart deployment/facebook-clone-green -n facebook-clone
```

#### Database Connection Pool Tuning

Adjust via environment variables (requires pod restart):

```
DB_POOL_SIZE=15        # default: 10
DB_MAX_OVERFLOW=30     # default: 20
DB_POOL_RECYCLE=3600   # seconds
DB_POOL_TIMEOUT=30     # seconds
```

#### Redis Scaling

```bash
# Check current memory usage
redis-cli INFO memory | grep used_memory_human

# Increase memory limit (update Redis config/StatefulSet)
# For usage > 10 GB: evaluate Redis Cluster or Redis Sentinel

# View large keys consuming memory
redis-cli --bigkeys

# Review TTL settings (shorter TTLs = less memory pressure):
# profile cache: 300s (can reduce to 120s)
# feed ZSET:      60s (can reduce to 30s under pressure)
```

---

### 4.3 Pre-Scaling Checklist (Before Major Traffic Events)

Run this checklist **24 hours before** a known traffic spike (product launch, marketing campaign, viral post):

```
□ Notify the team in #ops-facebook-clone with expected traffic window
□ Review current HPA settings: kubectl describe hpa -n facebook-clone
□ Pre-scale pods above HPA minimum to avoid cold-start lag:
    kubectl scale deployment facebook-clone-blue -n facebook-clone --replicas=6
    kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=6
□ Verify DB connection pool can handle pod count × pool_size connections
    (6 pods × 10 pool_size = 60 connections; verify PostgreSQL max_connections > 60)
□ Check Redis memory headroom (should be < 60% before event)
□ Verify S3/MinIO has sufficient capacity and IAM permissions
□ Set Grafana alert thresholds slightly lower for the event window
□ Test /ready endpoint returns 200 on all pods
□ Brief on-call engineer on expected load pattern
□ Prepare rollback plan and confirm rollback script is tested
□ Verify PagerDuty escalation policy is active
```

---

## 5. Backup & Restore

### 5.1 PostgreSQL Backup

#### Manual Backup

```bash
# From a pod with psql access, or from a jump host with DB access:
pg_dump \
  --host=$DB_HOST \
  --port=5432 \
  --username=$DB_USER \
  --dbname=facebook_clone \
  --format=custom \
  --compress=9 \
  --file=backup_$(date +%Y%m%d_%H%M%S).dump

# Verify the backup is readable
pg_restore --list backup_<timestamp>.dump | head -20
```

#### Backup to S3

```bash
# Dump directly to S3 via pipe (requires aws CLI)
pg_dump \
  --host=$DB_HOST \
  --username=$DB_USER \
  --dbname=facebook_clone \
  --format=custom \
  | aws s3 cp - \
    s3://$BACKUP_BUCKET/postgres/facebook_clone_$(date +%Y%m%d_%H%M%S).dump \
    --storage-class STANDARD_IA

# Confirm upload
aws s3 ls s3://$BACKUP_BUCKET/postgres/ | tail -5
```

#### Recommended Automated Backup Schedule

| Frequency | Retention | Storage |
|---|---|---|
| Every 1 hour | 24 hours | S3 Standard |
| Daily (02:00 UTC) | 30 days | S3 Standard-IA |
| Weekly (Sunday 03:00 UTC) | 90 days | S3 Glacier Instant Retrieval |
| Monthly (1st, 04:00 UTC) | 1 year | S3 Glacier Deep Archive |

#### Backup Verification (Weekly)

```bash
# Restore to a test database and verify row counts
pg_restore \
  --host=test-db-host \
  --username=$DB_USER \
  --dbname=facebook_clone_test \
  --no-owner \
  backup_<timestamp>.dump

psql -h test-db-host -U $DB_USER facebook_clone_test \
  -c "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM posts;"
```

---

### 5.2 PostgreSQL Restore

> ⚠️ **CAUTION:** Always restore to a test environment first. Confirm the backup is valid before touching production.

```bash
# Step 1: Stop application traffic (scale to 0 to prevent writes)
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=0
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=0

# Step 2: Download backup from S3 (if needed)
aws s3 cp \
  s3://$BACKUP_BUCKET/postgres/facebook_clone_<timestamp>.dump \
  ./restore.dump

# Step 3: Drop and recreate the database (destructive — confirm twice)
psql -h $DB_HOST -U $DB_USER postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='facebook_clone';"
psql -h $DB_HOST -U $DB_USER postgres \
  -c "DROP DATABASE facebook_clone;"
psql -h $DB_HOST -U $DB_USER postgres \
  -c "CREATE DATABASE facebook_clone OWNER $DB_USER;"

# Step 4: Restore
pg_restore \
  --host=$DB_HOST \
  --username=$DB_USER \
  --dbname=facebook_clone \
  --no-owner \
  --jobs=4 \
  ./restore.dump

# Step 5: Verify data integrity
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "\dt"
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM posts; SELECT COUNT(*) FROM friendships;"

# Step 6: Run migrations to bring schema current (if restoring old backup)
alembic upgrade head

# Step 7: Resume application traffic
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=2
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=2
kubectl rollout status deployment/facebook-clone-blue -n facebook-clone
```

---

### 5.3 Redis Backup

#### RDB Snapshot (Manual)

```bash
# Trigger a background RDB save
kubectl exec -n facebook-clone <redis-pod> -- redis-cli BGSAVE

# Wait for completion
kubectl exec -n facebook-clone <redis-pod> -- redis-cli LASTSAVE

# Copy the dump.rdb file from the pod
kubectl cp facebook-clone/<redis-pod>:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb

# Upload to S3
aws s3 cp ./redis-backup-$(date +%Y%m%d).rdb \
  s3://$BACKUP_BUCKET/redis/dump_$(date +%Y%m%d_%H%M%S).rdb
```

#### AOF (Append-Only File) Recommendation

Enable AOF in Redis config for near-real-time durability:

```
appendonly yes
appendfsync everysec     # balance between durability and performance
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

#### Recovery from RDB

```bash
# 1. Stop Redis
# 2. Replace /data/dump.rdb with the backup file
kubectl cp ./redis-backup.rdb facebook-clone/<redis-pod>:/data/dump.rdb

# 3. Restart Redis pod
kubectl rollout restart statefulset/redis -n facebook-clone

# 4. Verify key count
kubectl exec -n facebook-clone <redis-pod> -- redis-cli DBSIZE
```

> **Note:** Redis is used for caching and rate limiting. Losing Redis data means temporary cache misses (degraded performance, not data loss) and rate limit counter resets. Token blacklist data loss is a security concern — see Section 3 in DISASTER_RECOVERY.md.

---

### 5.4 S3/Media Backup

#### Cross-Region Replication (Recommended)

Enable S3 Cross-Region Replication (CRR) in the AWS console or via Terraform to automatically replicate media files to a secondary region. Set replication rule on the primary bucket targeting a bucket in `us-west-2` (or your DR region).

```bash
# Verify replication status
aws s3api get-bucket-replication --bucket $S3_BUCKET_NAME

# Manually sync media to secondary bucket (for MinIO or manual replication)
aws s3 sync s3://$S3_BUCKET_NAME s3://$S3_BUCKET_NAME-backup \
  --source-region us-east-1 \
  --region us-west-2
```

#### Versioning Policy

Enable bucket versioning to protect against accidental deletions:

```bash
aws s3api put-bucket-versioning \
  --bucket $S3_BUCKET_NAME \
  --versioning-configuration Status=Enabled

# List versions of a specific object
aws s3api list-object-versions \
  --bucket $S3_BUCKET_NAME \
  --prefix "media/users/avatar/user-123.jpg"

# Restore a previous version
aws s3api copy-object \
  --bucket $S3_BUCKET_NAME \
  --copy-source "$S3_BUCKET_NAME/media/users/avatar/user-123.jpg?versionId=<version-id>" \
  --key "media/users/avatar/user-123.jpg"
```

---

## 6. Common Issues & Fixes

---

### Issue 1: App Won't Start — Database Connection Failed

**Symptom:** Pod enters `CrashLoopBackOff`. Logs show `sqlalchemy.exc.OperationalError: could not connect to server`.

**Diagnosis:**
```bash
kubectl describe pod -n facebook-clone <pod-name>  # Check events
kubectl logs -n facebook-clone <pod-name> --previous  # Check last crash logs
# Verify DATABASE_URL secret exists and is correctly formatted
kubectl get secret facebook-clone-secrets -n facebook-clone -o jsonpath='{.data.DATABASE_URL}' | base64 -d
```

**Fix:**
```bash
# 1. Verify PostgreSQL is reachable from within the cluster
kubectl run -it --rm debug --image=postgres:16-alpine --restart=Never -n facebook-clone \
  -- psql "$DATABASE_URL" -c "SELECT 1;"

# 2. If credentials are wrong, update the secret
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=DATABASE_URL="<corrected-url>" \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Restart pods to pick up new secret
kubectl rollout restart deployment/facebook-clone-blue -n facebook-clone
```

---

### Issue 2: High 5xx Error Rate

**Symptom:** Grafana shows > 5% HTTP 500/502/503 errors. AlertManager fires `HighErrorRate`.

**Diagnosis:**
```bash
# Check recent error logs
kubectl logs -n facebook-clone -l app=facebook-clone --tail=200 | grep '"level":"error"'

# Prometheus query for error breakdown by endpoint:
# sum by (path) (rate(http_requests_total{status=~"5.."}[5m]))

# Check pod health
kubectl get pods -n facebook-clone
kubectl top pods -n facebook-clone
```

**Fix:**
```bash
# If caused by a bad deploy → rollback immediately
./deploy/scripts/rollback.sh production

# If pod OOM → increase memory limits and redeploy
# If DB overload → scale DB read replicas, reduce pool pressure
# If downstream service failure → check /ready endpoint for DB/Redis status
```

---

### Issue 3: WebSocket Connections Dropping

**Symptom:** Clients report frequent disconnections. Grafana WS connection gauge drops abruptly.

**Diagnosis:**
```bash
# Check for pod restarts (websocket state is lost on restart)
kubectl get pods -n facebook-clone  # Look at RESTARTS column

# Check NGINX ingress timeout settings
kubectl get configmap -n ingress-nginx ingress-nginx-controller -o yaml | grep proxy-read-timeout

# Prometheus query: websocket_connections_active
```

**Fix:**
```bash
# Increase NGINX proxy read/send timeout via ingress annotation
# In the Ingress manifest, add:
# nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
# nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"

kubectl apply -k deploy/k8s/overlays/production

# Verify PDB is preventing all-pod restarts during upgrades
kubectl get pdb -n facebook-clone
```

---

### Issue 4: Feed Showing Stale Data

**Symptom:** Users see old posts in their feed even after new posts are published.

**Diagnosis:**
```bash
# Check Redis feed cache TTL (feed ZSET: 60s)
kubectl exec -n facebook-clone <redis-pod> -- redis-cli TTL "feed:<user-id>"

# Check cache hit rate
# Prometheus query: rate(cache_hits_total[5m]) / rate(cache_requests_total[5m])
```

**Fix:**
```bash
# Manually invalidate feed cache for affected user
kubectl exec -n facebook-clone <redis-pod> -- redis-cli DEL "feed:<user-id>"

# Bulk invalidate all feed caches (use cautiously — causes cache stampede)
kubectl exec -n facebook-clone <redis-pod> -- redis-cli \
  --scan --pattern "feed:*" | xargs redis-cli DEL

# Reduce feed TTL temporarily if stale data is widespread
# Update FEED_CACHE_TTL env var and restart pods
```

---

### Issue 5: Media Upload Failing

**Symptom:** Users get 500 errors when uploading photos. Logs show S3 permission errors.

**Diagnosis:**
```bash
# Check application logs for S3 errors
kubectl logs -n facebook-clone -l app=facebook-clone --tail=100 | grep -i "s3\|minio\|NoSuchBucket\|AccessDenied"

# Verify storage backend config
kubectl exec -n facebook-clone <pod-name> -- env | grep -E "STORAGE|S3|AWS"

# Test S3 connectivity from pod
kubectl exec -it -n facebook-clone <pod-name> -- \
  python -c "import boto3; s3=boto3.client('s3'); s3.list_buckets(); print('S3 OK')"
```

**Fix:**
```bash
# Verify IAM credentials are valid
aws sts get-caller-identity

# If credentials expired, rotate and update the secret
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=AWS_ACCESS_KEY_ID="<new-key>" \
  --from-literal=AWS_SECRET_ACCESS_KEY="<new-secret>" \
  --dry-run=client -o yaml | kubectl apply -f -

# Verify bucket exists and policy allows PutObject
aws s3 ls s3://$S3_BUCKET_NAME
aws s3api get-bucket-policy --bucket $S3_BUCKET_NAME
```

---

### Issue 6: Rate Limit False Positives

**Symptom:** Legitimate users hitting 429 Too Many Requests unexpectedly.

**Diagnosis:**
```bash
# Check Redis sliding window counters for affected user
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli KEYS "ratelimit:*" | head -20

# Check NGINX rate limit headers in response
curl -v https://api.example.com/api/v1/posts -H "Authorization: Bearer <token>" 2>&1 | \
  grep -i "x-ratelimit\|retry-after"

# NGINX ingress rate limit: 100 RPS global
```

**Fix:**
```bash
# Clear rate limit keys for a specific user/IP
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli DEL "ratelimit:<user-id-or-ip>"

# If global: temporarily increase NGINX rate limit annotation on Ingress
# nginx.ingress.kubernetes.io/limit-rps: "200"

# Review whether rate limiter is using correct user identifier (IP vs JWT sub)
```

---

### Issue 7: Redis Memory Growing — ZSET Leak

**Symptom:** Redis memory usage trending upward. `redis-cli --bigkeys` shows large ZSETs.

**Diagnosis:**
```bash
# Find large keys
kubectl exec -n facebook-clone <redis-pod> -- redis-cli --bigkeys

# Check ZSET cardinality for feed caches
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli ZCARD "feed:<user-id>"

# Scan for keys without TTL
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli --scan --pattern "feed:*" | \
  while read key; do echo "$key: $(redis-cli TTL $key)"; done | grep ":-1"
```

**Fix:**
```bash
# Set TTL on keys missing expiry
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli EXPIRE "feed:<user-id>" 60

# Trim oversized ZSETs (keep only the latest 200 entries)
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli ZREMRANGEBYRANK "feed:<user-id>" 0 -201

# Set Redis maxmemory-policy to allkeys-lru as a safety net
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli CONFIG SET maxmemory-policy allkeys-lru
```

---

### Issue 8: Slow Queries / Database Timeout

**Symptom:** `sqlalchemy.exc.TimeoutError`. Grafana shows DB query duration p99 > 5s.

**Diagnosis:**
```bash
# Check slow query log in PostgreSQL
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT query, calls, mean_exec_time, total_exec_time
      FROM pg_stat_statements
      ORDER BY mean_exec_time DESC LIMIT 10;"

# Check active long-running queries
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT pid, now() - query_start AS duration, state, query
      FROM pg_stat_activity
      WHERE state != 'idle' AND query_start < now() - interval '5 seconds'
      ORDER BY duration DESC;"

# Check index usage
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT relname, seq_scan, idx_scan FROM pg_stat_user_tables ORDER BY seq_scan DESC;"
```

**Fix:**
```bash
# Kill blocking queries
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT pg_terminate_backend(<pid>);"

# Add missing index (example: posts by user_id)
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "CREATE INDEX CONCURRENTLY idx_posts_user_id ON posts(user_id);"

# Run VACUUM ANALYZE to update query planner statistics
psql -h $DB_HOST -U $DB_USER facebook_clone -c "VACUUM ANALYZE;"
```

---

### Issue 9: JWT Tokens Not Being Invalidated

**Symptom:** Logged-out users or password-reset users can still authenticate with old tokens.

**Diagnosis:**
```bash
# Verify token blacklist entry in Redis
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli GET "blacklist:<jti>"
# Should return "1" or the token string; if nil, blacklist write failed

# Check Redis connectivity from app
kubectl exec -n facebook-clone <pod-name> -- \
  python -c "import redis; r=redis.from_url('$REDIS_URL'); print(r.ping())"
```

**Fix:**
```bash
# Manually blacklist a specific token JTI
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli SET "blacklist:<jti>" 1 EX <remaining-ttl-seconds>

# If Redis is down and tokens can't be blacklisted:
# → Rotate JWT_SECRET_KEY immediately (see DISASTER_RECOVERY.md §5)
# → All existing tokens become invalid

# Verify blacklist check is in the auth middleware (code audit)
```

---

### Issue 10: S3 Access Denied Errors

**Symptom:** Media uploads fail with `403 AccessDenied` or `NoCredentialsError`.

**Diagnosis:**
```bash
# Check IAM policy allows s3:PutObject on the bucket
aws iam simulate-principal-policy \
  --policy-source-arn <role-arn> \
  --action-names s3:PutObject \
  --resource-arns arn:aws:s3:::$S3_BUCKET_NAME/*

# Verify environment variables are set in the pod
kubectl exec -n facebook-clone <pod-name> -- env | grep AWS
```

**Fix:** Update IAM role policy to include `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` on `arn:aws:s3:::$S3_BUCKET_NAME/*`. Rotate credentials if suspected compromise.

---

### Issue 11: Alembic Migration Failed Mid-Run

**Symptom:** `alembic upgrade head` exits mid-migration. DB schema is in a partial state.

**Diagnosis:**
```bash
# Check current migration state
alembic current
alembic history --verbose

# Check PostgreSQL alembic_version table
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT * FROM alembic_version;"
```

**Fix:**
```bash
# DO NOT run alembic upgrade again without investigating
# 1. Check what the failed migration was trying to do (check migration file)
# 2. Manually undo partial changes in psql if needed
# 3. Update alembic_version to the last known good state
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "UPDATE alembic_version SET version_num='<last-good-revision>';"
# 4. Fix the migration file if there was a bug
# 5. Re-run: alembic upgrade head
```

---

### Issue 12: Pod OOMKilled

**Symptom:** Pod status shows `OOMKilled`. Grafana memory gauge was at 100% before crash.

**Diagnosis:**
```bash
kubectl describe pod -n facebook-clone <pod-name>
# Look for: "Last State: Terminated — Reason: OOMKilled"

# Check memory limits
kubectl get pod -n facebook-clone <pod-name> -o jsonpath='{.spec.containers[0].resources}'

# Check for memory leak (trending memory growth in Grafana)
# Prometheus query: container_memory_working_set_bytes{namespace="facebook-clone"}
```

**Fix:**
```bash
# Short-term: Increase memory limit in deployment manifest
# requests.memory: 256Mi → 512Mi
# limits.memory: 512Mi → 1Gi

# Apply and restart
kubectl apply -k deploy/k8s/overlays/production
kubectl rollout restart deployment/facebook-clone-blue -n facebook-clone

# Long-term: Profile memory usage to find the leak
# Common causes: unbounded caches, Redis ZSET accumulation, large file buffer reads
```

---

## 7. Health Check Endpoints

### GET /health — Liveness

**Purpose:** Confirms the application process is alive. Kubernetes uses this for the liveness probe.

**What it checks:** Only that the FastAPI application is running and able to accept HTTP requests. Does **not** check database or Redis connectivity.

**Expected response:**
```json
HTTP 200 OK
{"status": "ok"}
```

**Kubernetes liveness probe config:**
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30   # Allow app startup time
  periodSeconds: 10
  failureThreshold: 3        # Restart pod after 3 consecutive failures
  timeoutSeconds: 5
```

---

### GET /ready — Readiness

**Purpose:** Confirms the application is ready to serve traffic. Kubernetes uses this for the readiness probe. Pods failing this check are temporarily removed from the service endpoint pool — no restart is triggered.

**What it checks:**
- PostgreSQL: executes `SELECT 1` query
- Redis: executes `PING` command
- Both must succeed for a 200 response

**Expected responses:**
```json
# Healthy
HTTP 200 OK
{"status": "ok", "db": "ok", "redis": "ok"}

# Degraded (removed from load balancer rotation)
HTTP 503 Service Unavailable
{"status": "degraded", "db": "error", "redis": "ok"}
```

**What 503 means:** The pod cannot currently serve requests. The load balancer stops sending traffic to it. Other pods continue serving. Investigate the failing dependency immediately.

**Kubernetes readiness probe config:**
```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  failureThreshold: 2        # Remove from rotation after 2 failures
  timeoutSeconds: 5
```

---

### GET /metrics — Prometheus Scrape Endpoint

**Purpose:** Exposes all application metrics in Prometheus text format. Scraped by Prometheus every 15 seconds.

**Key metrics exposed:**
- `http_requests_total{method, path, status}` — request counter
- `http_request_duration_seconds{method, path}` — latency histogram
- `websocket_connections_active` — current WS connection gauge
- `cache_hits_total / cache_misses_total` — Redis cache counters
- `db_query_duration_seconds` — database query latency histogram

---

### GET /metrics/simple — Human-Readable Metrics

**Purpose:** Quick operational snapshot for humans and lightweight monitors.

**Expected response:**
```json
{
  "uptime_seconds": 86400,
  "online_users": 1234
}
```

---

## 8. Monitoring Dashboards Guide

### 8.1 Grafana

**Access:** `https://grafana.internal` → Dashboard: `Facebook Clone — Production`

**6-Panel Overview:**

| Panel | What to Watch | Alert Threshold |
|---|---|---|
| HTTP Request Rate | Requests/sec by status code | Sudden drops = potential outage |
| HTTP P99 Latency | 99th percentile response time | > 2s → alert fires |
| Error Rate (5xx) | Percentage of 5xx responses | > 5% → alert fires |
| WebSocket Connections | Active WS connections total | > 100/pod avg → HPA scales |
| Pod CPU/Memory | Resource utilization per pod | CPU > 70%, Mem > 80% |
| DB Query Duration | P99 DB query time | > 1s warrants investigation |

**Quick tips:**
- Filter by namespace (`facebook-clone` or `facebook-clone-staging`) using the top dropdown
- Use time range selector to zoom into an incident window
- `Explore` tab in Grafana → switch datasource to Loki for log correlation

---

### 8.2 Prometheus — Useful PromQL Queries

```promql
# Overall error rate
sum(rate(http_requests_total{namespace="facebook-clone",status=~"5.."}[5m]))
/ sum(rate(http_requests_total{namespace="facebook-clone"}[5m]))

# P99 latency
histogram_quantile(0.99, sum by (le, path) (
  rate(http_request_duration_seconds_bucket{namespace="facebook-clone"}[5m])
))

# Active WebSocket connections
websocket_connections_active{namespace="facebook-clone"}

# Cache hit rate
rate(cache_hits_total{namespace="facebook-clone"}[5m])
/ (rate(cache_hits_total{namespace="facebook-clone"}[5m])
   + rate(cache_misses_total{namespace="facebook-clone"}[5m]))

# Pod restart count in last hour
changes(kube_pod_container_status_restarts_total{namespace="facebook-clone"}[1h])

# DB connection pool utilization
db_pool_checked_out{namespace="facebook-clone"} / db_pool_size
```

---

### 8.3 Loki — Log Queries for Common Issues

Access via Grafana → Explore → Datasource: Loki

```logql
# All error logs from production pods
{namespace="facebook-clone"} | json | level="error"

# Logs from a specific pod
{namespace="facebook-clone", pod="facebook-clone-blue-abc123"} | json

# Slow requests (> 1 second)
{namespace="facebook-clone"} | json | duration > 1000

# Database errors
{namespace="facebook-clone"} | json | level="error" | message=~"sqlalchemy|database|db"

# Authentication failures
{namespace="facebook-clone"} | json | message=~"401|403|Unauthorized|Forbidden"

# S3 errors
{namespace="facebook-clone"} | json | message=~"S3|NoSuchBucket|AccessDenied"

# Recent 500 errors with stack traces
{namespace="facebook-clone"} | json | status=500 | line_format "{{.timestamp}} {{.path}} {{.message}}"
```

---

### 8.4 Jaeger — Tracing a Slow Request

1. Open `https://jaeger.internal`
2. **Service** dropdown → select `facebook-clone`
3. **Operation** → select the slow endpoint (e.g., `GET /api/v1/feed`)
4. Set **Min Duration** to `500ms` to filter slow traces
5. Click **Find Traces**

**Reading a trace:**
- Each span represents one operation (HTTP handler, DB query, Redis call, S3 operation)
- Spans are nested: child spans are called by parent spans
- Wide spans with no children = actual work; look for unexpectedly wide database or Redis spans
- Tags include `db.statement` (SQL query), `http.status_code`, `error=true`

**Common finding:** Feed endpoint slow because of N+1 queries (one DB query per post to load author data). Fix by joining or batching.

---

## 9. Incident Response Playbook

### 9.1 Severity Levels

| Severity | Definition | Response Time | Notification |
|---|---|---|---|
| **P0** | Complete outage — service unavailable for all users | Immediate (< 5 min) | PagerDuty page + Slack #incidents |
| **P1** | Major degradation — > 20% of users affected or core feature broken | < 15 min | PagerDuty page + Slack #incidents |
| **P2** | Partial degradation — < 20% users affected or non-core feature broken | < 1 hour | Slack #incidents |
| **P3** | Minor issue — cosmetic or edge case, low user impact | Next business day | Slack #alerts-facebook-clone |

---

### 9.2 P0 Procedure — Complete Outage

```
00:00  DETECT
  → AlertManager fires HighErrorRate (5xx > 5%) or PodCrashLooping
  → PagerDuty pages on-call engineer

00:01  ACKNOWLEDGE
  1. Acknowledge PagerDuty alert
  2. Post in #incidents: "Investigating P0 — [brief description] — [your name] as IC"

00:02  TRIAGE
  3. Check pod status:
       kubectl get pods -n facebook-clone
  4. Check health endpoint:
       curl -s https://api.example.com/health
       curl -s https://api.example.com/ready
  5. Check recent deployments:
       kubectl rollout history deployment/facebook-clone-blue -n facebook-clone

00:05  MITIGATE
  6. If caused by recent deploy → ROLLBACK IMMEDIATELY:
       ./deploy/scripts/rollback.sh production
  7. If pods are crash-looping → check logs:
       kubectl logs -n facebook-clone -l app=facebook-clone --previous
  8. If DB is down → notify DBA, scale app to 0 to stop error spam:
       kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=0
       kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=0

00:15  ESCALATE (if not resolved)
  9. Call Backend Lead (L2 contact from Section 1)
  10. Post status update in #incidents every 10 minutes

00:30  ESCALATE AGAIN (if not resolved)
  11. Call Engineering Manager (L3)
  12. Consider customer-facing status page update

RESOLVE
  13. Verify health: curl -s https://api.example.com/ready | jq
  14. Monitor Grafana for 15 minutes post-recovery
  15. Post in #incidents: "P0 RESOLVED — [time] — [brief RCA]"
  16. Resolve PagerDuty alert
  17. Open incident retrospective document
```

---

### 9.3 P1 Procedure — Degraded Service

```
1. Acknowledge alert within 15 minutes
2. Post in #incidents: "Investigating P1 — [description] — [IC name]"
3. Identify affected functionality (which endpoints are failing?)
   → Use Grafana error rate panel filtered by path
4. Check if linked to a recent deploy:
   → git log --oneline -10  or  kubectl rollout history
5. Attempt targeted fix:
   → Cache invalidation for stale data issues
   → Scale up pods for capacity issues
   → Rollback for regression issues
6. If not resolved in 30 minutes → escalate to L2
7. Update #incidents every 15 minutes
8. Resolve alert once metrics return to baseline
9. Write post-incident summary within 24 hours
```

---

### 9.4 Post-Incident Process

#### Incident Timeline Template

```markdown
## Incident Report — [Date] — [Brief Title]

**Severity:** P0 / P1 / P2
**Duration:** HH:MM (start) → HH:MM (end) = X minutes total
**Incident Commander:** [Name]
**Affected Service:** facebook-clone production

### Timeline
- HH:MM — Alert fired: [alert name]
- HH:MM — On-call engineer acknowledged
- HH:MM — [What was found during triage]
- HH:MM — [Mitigation action taken]
- HH:MM — Service restored
- HH:MM — Post-incident monitoring period ended

### Root Cause
[1-2 sentence description of the root cause]

### Contributing Factors
- [Factor 1]
- [Factor 2]

### Impact
- Affected users: ~X (estimated)
- Affected requests: ~X (from Prometheus)
- Data loss: None / [description]

### What Went Well
- [e.g., Rollback was fast and effective]

### What Could Be Improved
- [e.g., Alert threshold was too slow to fire]

### Action Items
| Action | Owner | Due Date | Priority |
|---|---|---|---|
| [e.g., Add index to posts.user_id] | [Name] | [Date] | High |
| [e.g., Reduce alert threshold] | [Name] | [Date] | Medium |
```

---

*End of Runbook — For DR scenarios and JWT rotation procedures, see [DISASTER_RECOVERY.md](./DISASTER_RECOVERY.md).*
