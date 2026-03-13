# Facebook Clone Backend — Disaster Recovery Plan

> **Version:** 1.0 · **Last updated:** 2026-03-13
> **Stack:** Python 3.12 · FastAPI · PostgreSQL 16 · Redis 7 · S3/MinIO · Kubernetes

---

## Table of Contents

1. [RTO / RPO Targets](#1-rto--rpo-targets)
2. [Architecture Resilience](#2-architecture-resilience)
3. [Failure Scenarios & Procedures](#3-failure-scenarios--procedures)
4. [Data Recovery](#4-data-recovery)
5. [JWT Key Rotation Runbook](#5-jwt-key-rotation-runbook)
6. [Security Incident Response](#6-security-incident-response)
7. [Recovery Testing Schedule](#7-recovery-testing-schedule)
8. [Contact & Escalation Matrix](#8-contact--escalation-matrix)

---

## 1. RTO / RPO Targets

> **RTO (Recovery Time Objective):** Maximum acceptable time from failure detection to service restoration.
> **RPO (Recovery Point Objective):** Maximum acceptable data loss measured in time (how far back we may need to roll back).

| Scenario | RTO Target | RPO Target | Current Capability | Gap / Notes |
|---|---|---|---|---|
| Single pod failure | < 2 min | 0 (stateless) | Kubernetes auto-restarts in ~30s | ✅ Met |
| Full deployment failure | < 5 min | 0 (stateless) | Blue/green rollback in ~30s | ✅ Met |
| Database failure (primary) | < 30 min | < 5 min | Manual failover + WAL archiving | ⚠️ Needs automated failover (Patroni/RDS Multi-AZ) |
| Redis failure | < 5 min | Cache only (acceptable) | Redis restart or new pod; cache warms naturally | ✅ Met (cache miss acceptable) |
| S3 storage failure | < 1 hr | < 1 hr | S3 SLA 99.99%; CRR for DR bucket | ✅ Met with CRR enabled |
| Complete datacenter / AZ failure | < 2 hr | < 15 min | Manual cluster failover to DR region | ⚠️ DR cluster not yet automated |
| Data corruption | < 4 hr | < 1 hr | PITR via WAL archiving; RTO depends on DB size | ⚠️ PITR must be pre-enabled |
| Security breach / compromised credentials | < 1 hr | N/A (rotate, not restore) | JWT rotation + secret update procedure | ✅ Procedure documented (§5) |

### Key Assumptions

- Hourly PostgreSQL backups are running and stored in S3 (see RUNBOOK §5.1).
- WAL archiving is enabled for PITR capability.
- S3 Cross-Region Replication is enabled on the primary media bucket.
- The DR region Kubernetes cluster is provisioned but dormant (warm standby).

---

## 2. Architecture Resilience

The following mechanisms provide defense-in-depth against various failure modes.

### 2.1 Pod Redundancy (HPA min=2)

The Horizontal Pod Autoscaler maintains a minimum of 2 running replicas across the active deployment slot at all times. A single pod failure leaves the service fully operational. HPA scales up to 20 pods when CPU exceeds 70%, memory exceeds 80%, or WebSocket connections exceed 100 per pod — preventing resource exhaustion under traffic spikes.

### 2.2 Blue/Green Zero-Downtime Deploys

Every production deployment uses the blue/green strategy. The inactive slot receives the new image, becomes healthy, and is verified before traffic switches. If the new version is unhealthy, the service selector is never updated. If a post-switch problem is discovered, the service selector is flipped back in ~30 seconds with no image rebuild required.

### 2.3 Pod Disruption Budget (minAvailable=1)

The PDB prevents Kubernetes from evicting all pods simultaneously during voluntary disruptions (node drains, cluster upgrades). At least one pod remains running and serving traffic throughout any planned maintenance operation.

### 2.4 Health Probes (Startup / Readiness / Liveness)

- **Liveness probe** (`/health`): Detects application deadlock or hang. Kubernetes automatically restarts the pod.
- **Readiness probe** (`/ready`): Detects dependency failures (DB/Redis down). Pod is removed from load balancer rotation without restarting, preventing cascading failures.
- **Startup probe**: Gives the app sufficient time to initialize before liveness/readiness checks begin, avoiding false restarts on slow startup.

### 2.5 Redis Fail-Open Pattern (Cache Misses Degrade Gracefully)

All Redis cache reads are wrapped in try/except. If Redis is unavailable, the application falls through to the PostgreSQL source of truth. This means:
- Cache misses → higher DB load, slower responses, but no errors returned to users
- Rate limiting fail-open → requests pass through (slightly reduced protection)
- Token blacklist unavailable → JWT validation relies on expiry time only (temporary window of risk)

### 2.6 Database Connection Pool with Timeout

SQLAlchemy is configured with `pool_size=10, max_overflow=20, pool_timeout=30, pool_recycle=3600`. If the database is temporarily unreachable, connection requests wait up to 30 seconds before raising an exception — preventing threads from blocking indefinitely. Pool recycling avoids stale connection issues after network interruptions.

### 2.7 NGINX Rate Limiting (100 RPS via Ingress)

The NGINX Ingress controller enforces 100 requests-per-second at the edge, providing a first line of defense against accidental traffic floods and DDoS attempts before they reach application pods.

### 2.8 NetworkPolicy (Default-Deny)

Kubernetes NetworkPolicies enforce default-deny ingress. Only traffic from the `ingress-nginx` and `monitoring` namespaces is permitted to reach application pods. This limits the blast radius of a compromised pod and prevents unauthorized lateral movement.

---

## 3. Failure Scenarios & Procedures

---

### Scenario 1: Single Pod Failure

**Detection:** Kubernetes detects the failed pod via liveness probe failure (3 consecutive failures in 30s). AlertManager may fire `PodCrashLooping` if the pod restarts more than 3 times in 5 minutes.

**Impact:** 1 of 2+ replicas is unavailable. Remaining pods absorb the traffic. Users may see a brief spike in latency. No data loss (pods are stateless).

**Recovery Steps:**
```bash
# 1. Kubernetes auto-restarts the pod — no manual action usually needed
# Monitor recovery:
kubectl get pods -n facebook-clone -w

# 2. If pod enters CrashLoopBackOff, investigate:
kubectl logs -n facebook-clone <pod-name> --previous
kubectl describe pod -n facebook-clone <pod-name>

# 3. If crash is due to a bug in the current deploy → rollback:
./deploy/scripts/rollback.sh production
```

**Verification:** All pods show `Running` status with 0 restarts. Error rate returns to baseline.

---

### Scenario 2: Full Deployment Failure

**Detection:** All pods in the active slot fail simultaneously (CrashLoopBackOff or all `/ready` checks failing). Error rate reaches 100%. AlertManager fires `HighErrorRate` and `PodCrashLooping`.

**Impact:** Service fully unavailable. P0 incident.

**Recovery Steps:**
```bash
# 1. Immediately rollback (30-second procedure)
./deploy/scripts/rollback.sh production

# 2. Verify rollback succeeded
kubectl get service facebook-clone -n facebook-clone \
  -o jsonpath='{.spec.selector.slot}'
# Should now show the previous slot

# 3. Verify traffic is flowing
curl -s https://api.example.com/health | jq
curl -s https://api.example.com/ready | jq

# 4. Scale up the now-active (old) slot if needed
kubectl scale deployment facebook-clone-<old-slot> -n facebook-clone --replicas=4

# 5. Investigate the failed deployment in the inactive slot
kubectl logs -n facebook-clone -l slot=<failed-slot> --previous
```

**Verification:** Error rate drops to < 1% within 2 minutes of rollback. `/ready` returns 200 on all active pods.

---

### Scenario 3: PostgreSQL Primary Failure

**Detection:** `/ready` endpoint returns `503` with `"db": "error"`. All pods removed from load balancer. AlertManager fires `DatabaseUnavailable`. DB connection pool timeout errors in logs.

**Impact:** Complete service unavailability (all write and read operations fail). P0 incident.

**Recovery Steps:**
```bash
# Immediate (< 5 min): Scale app to 0 to stop error storm
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=0
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=0

# If using managed DB (RDS Multi-AZ): automatic failover occurs within 60-120s
# Monitor AWS console for failover completion

# If self-managed PostgreSQL (manual failover):
# 1. Promote standby replica to primary
#    On the standby server:
pg_ctl promote -D /var/lib/postgresql/data
# or: touch /var/lib/postgresql/data/failover.trigger (trigger file method)

# 2. Update DATABASE_URL secret to point to new primary
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=DATABASE_URL="postgresql+asyncpg://user:pass@<new-primary-host>:5432/facebook_clone" \
  --dry-run=client -o yaml | kubectl apply -f -

# 3. Resume application
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=2
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=2

# 4. Verify readiness
kubectl rollout status deployment/facebook-clone-blue -n facebook-clone
curl -s https://api.example.com/ready | jq
```

**Verification:** `/ready` returns `{"status": "ok", "db": "ok"}`. DB query duration returns to normal in Grafana. Run `SELECT COUNT(*) FROM users;` to confirm data integrity.

---

### Scenario 4: Redis Failure

**Detection:** Application logs show `redis.exceptions.ConnectionError`. Grafana shows cache hit rate drops to 0. Latency increases (DB reads for all cached data). AlertManager fires `RedisUnavailable`.

**Impact:** Degraded performance (higher latency, increased DB load). Rate limiting fails open. Token blacklist unavailable (security window). NOT a complete outage — application continues via fail-open pattern.

**Recovery Steps:**
```bash
# 1. Check Redis pod status
kubectl get pods -n facebook-clone -l app=redis

# 2. If Redis pod is in CrashLoopBackOff:
kubectl logs -n facebook-clone <redis-pod> --previous
kubectl describe pod -n facebook-clone <redis-pod>

# 3. Restart Redis pod
kubectl rollout restart statefulset/redis -n facebook-clone

# 4. If StatefulSet volume is corrupted:
# → Restore from RDB snapshot (see RUNBOOK §5.3)

# 5. Monitor cache hit rate recovery in Grafana
# Cache will warm up over the next 5-10 minutes as requests come in
```

**Verification:** `/ready` returns `{"redis": "ok"}`. Cache hit rate recovers in Grafana within 10 minutes.

**Security note:** If Redis was unavailable for > 1 hour, review token blacklist status. Consider forcing re-authentication for sensitive operations.

---

### Scenario 5: S3 / MinIO Failure

**Detection:** Media upload endpoints return 500 errors. Logs show `S3ServiceError` or `EndpointConnectionError`. Media images fail to load (403/404 responses from CDN).

**Impact:** Users cannot upload new media. Existing media URLs may return errors if the CDN cache is expired. Core social features (text posts, comments) continue working.

**Recovery Steps:**
```bash
# 1. Verify S3 connectivity
aws s3 ls s3://$S3_BUCKET_NAME

# 2. If bucket is unavailable in the primary region:
#    Switch to the cross-region replica bucket (read-only restore)
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=S3_BUCKET_NAME="$S3_BUCKET_NAME-backup" \
  --from-literal=S3_REGION="us-west-2" \
  --from-literal=S3_ENDPOINT_URL="https://s3.us-west-2.amazonaws.com" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl rollout restart deployment/facebook-clone-blue -n facebook-clone

# 3. For MinIO on-premise failure:
#    Restart MinIO pod first
kubectl rollout restart deployment/minio -n facebook-clone

# 4. If MinIO data volume is lost: restore from S3 backup
aws s3 sync s3://$S3_BUCKET_NAME-backup s3://$S3_BUCKET_NAME
```

**Verification:** POST to a media upload endpoint returns 200 with a valid URL. GET to the media URL returns the file.

---

### Scenario 6: Network Partition

**Detection:** Intermittent connection timeouts. Some pods unreachable. Kubernetes marks nodes `NotReady`. Split-brain symptoms in distributed state.

**Impact:** Variable — depends on which nodes are partitioned. Partial service degradation or complete outage.

**Recovery Steps:**
```bash
# 1. Assess node health
kubectl get nodes
kubectl describe node <NotReady-node>

# 2. Cordon affected nodes to stop new pod scheduling
kubectl cordon <affected-node>

# 3. Drain affected nodes (evicts pods to healthy nodes)
kubectl drain <affected-node> --ignore-daemonsets --delete-emptydir-data

# 4. Verify remaining pods are healthy
kubectl get pods -n facebook-clone -o wide

# 5. Scale up to restore replica count
kubectl scale deployment facebook-clone-blue -n facebook-clone --replicas=3

# 6. Once network is restored: uncordon nodes
kubectl uncordon <recovered-node>
```

**Verification:** All nodes show `Ready`. Pod distribution is balanced across nodes. Error rate returns to baseline.

---

### Scenario 7: Secrets Leak / JWT Key Compromise

**Detection:** Unauthorized API access detected via audit logs. Security team alerts on anomalous token usage. External security report.

**Impact:** All existing JWT tokens may be compromised. Attackers can impersonate users.

**Recovery Steps:**
```bash
# IMMEDIATE ACTION — Rotate JWT secret (invalidates ALL existing tokens)
# This forces all users to re-authenticate. Communicate downtime or re-auth requirement.

# Step 1: Generate a new secret
NEW_SECRET=$(openssl rand -hex 32)
echo "New JWT secret (store securely): $NEW_SECRET"

# Step 2: Update the Kubernetes secret
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=JWT_SECRET_KEY="$NEW_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

# Step 3: Restart all pods to pick up the new secret
kubectl rollout restart deployment/facebook-clone-blue  -n facebook-clone
kubectl rollout restart deployment/facebook-clone-green -n facebook-clone
kubectl rollout status deployment/facebook-clone-blue   -n facebook-clone

# Step 4: Flush the Redis token blacklist (old tokens are now invalid anyway)
kubectl exec -n facebook-clone <redis-pod> -- redis-cli FLUSHDB

# Step 5: Audit who generated the old secret and rotate access to secret store
# Review GitHub Actions secrets, CI environment variables, and developer access
```

**See also:** Full JWT key rotation runbook in §5 for the non-emergency rotation procedure.

**Verification:** All existing JWT tokens return 401 Unauthorized. New tokens issued after rotation work correctly.

---

### Scenario 8: Data Corruption (Accidental Mass Delete)

**Detection:** Users report missing data. DB row counts drop suddenly. Grafana shows a spike in `DELETE` query counts.

**Impact:** User data loss. Severity depends on scope. P0 if widespread.

**Recovery Steps:**
```bash
# Step 1: STOP the application immediately to prevent further writes
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=0
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=0

# Step 2: Take an immediate snapshot of the current (corrupted) DB state for investigation
pg_dump --host=$DB_HOST --username=$DB_USER --dbname=facebook_clone \
  --format=custom --file=corrupted_state_$(date +%Y%m%d_%H%M%S).dump

# Step 3: Determine the time of the corruption event
# Check audit logs: kubectl logs -n facebook-clone ... | grep "DELETE"
# Find the last known good backup before that timestamp

# Step 4: Restore using PITR (see §4.1) or the last clean backup (see RUNBOOK §5.2)

# Step 5: Verify restored data
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT COUNT(*) FROM users; SELECT COUNT(*) FROM posts;"

# Step 6: Resume application
kubectl scale deployment facebook-clone-blue -n facebook-clone --replicas=2

# Step 7: Notify affected users and legal/compliance team
```

**Verification:** Row counts match pre-corruption expectations. Data audit shows no anomalies.

---

### Scenario 9: DDoS Attack

**Detection:** Sudden traffic spike to > 10x normal. High 429 rate from NGINX rate limiter. CPU/memory spikes on all pods. Requests from many unique IPs.

**Impact:** Degraded performance for legitimate users; possible complete unavailability.

**Recovery Steps:**
```bash
# Step 1: Verify it is DDoS (vs organic traffic spike)
# Prometheus: sum by (remote_addr) (rate(http_requests_total[1m])) — look for top IPs
# If traffic is from many IPs → DDoS; if one source → targeted abuse

# Step 2: Tighten NGINX rate limit temporarily
# Update Ingress annotation: nginx.ingress.kubernetes.io/limit-rps: "20"
kubectl apply -k deploy/k8s/overlays/production

# Step 3: Enable AWS WAF / CloudFlare protection (if available)
# Block attack signature at edge before it reaches the cluster

# Step 4: If traffic overwhelms NGINX: scale NGINX ingress
kubectl scale deployment ingress-nginx-controller -n ingress-nginx --replicas=4

# Step 5: Scale application pods to absorb legitimate traffic
kubectl scale deployment facebook-clone-blue -n facebook-clone --replicas=10

# Step 6: If bandwidth is saturated: contact cloud provider for DDoS mitigation
# AWS Shield Advanced, Cloudflare Magic Transit, etc.

# Step 7: After attack subsides: restore normal rate limits
```

**Verification:** Traffic returns to normal pattern. Error rate drops. No legitimate users blocked.

---

### Scenario 10: CI/CD Pipeline Compromise

**Detection:** Unexpected or unauthorized GitHub Actions workflow runs. Unfamiliar images pushed to container registry. Security scanner alert on new image.

**Impact:** Potentially malicious code deployed to production or staging. Supply chain compromise.

**Recovery Steps:**
```bash
# Step 1: FREEZE all deployments immediately
# Disable GitHub Actions: Settings → Actions → Disable all workflows

# Step 2: Audit recent workflow runs and container image digests
gh run list --repo org/facebook-clone --limit 20
# Compare image digests in production against known-good CI outputs

# Step 3: If malicious image was deployed → rollback to last known-good image
./deploy/scripts/rollback.sh production
# Verify the active slot is running a verified image:
kubectl get pods -n facebook-clone -o jsonpath='{.items[0].spec.containers[0].image}'

# Step 4: Rotate ALL CI/CD secrets
# - GitHub Actions secrets: REGISTRY_TOKEN, KUBECONFIG, AWS_ACCESS_KEY_ID, etc.
# - Kubernetes service account tokens used by CI
# - Container registry access tokens

# Step 5: Review git history for unauthorized commits
git log --all --oneline --graph | head -30

# Step 6: Engage security team for forensic analysis
# Review Trivy scan results, check for injected dependencies

# Step 7: Re-enable pipelines only after secrets are rotated and audit is complete
```

**Verification:** All CI/CD secrets rotated. Image digests verified. Security team sign-off obtained before resuming deployments.

---

## 4. Data Recovery

### 4.1 Point-in-Time Recovery (PostgreSQL PITR)

PITR allows restoring the database to any point in time, not just the last backup. It requires WAL archiving to be enabled **before** a corruption event.

#### Enable WAL Archiving

Add to `postgresql.conf`:
```
wal_level = replica
archive_mode = on
archive_command = 'aws s3 cp %p s3://$BACKUP_BUCKET/wal/%f'
archive_timeout = 60
```

#### Base Backup

```bash
# Run a base backup (the starting point for PITR)
pg_basebackup \
  --host=$DB_HOST \
  --username=$DB_USER \
  --pgdata=/tmp/base_backup \
  --format=tar \
  --gzip \
  --checkpoint=fast \
  --wal-method=stream

# Upload base backup to S3
aws s3 sync /tmp/base_backup s3://$BACKUP_BUCKET/basebackup/$(date +%Y%m%d_%H%M%S)/
```

#### PITR Restore Procedure

```bash
# 1. Stop the application (scale to 0)
kubectl scale deployment facebook-clone-blue  -n facebook-clone --replicas=0
kubectl scale deployment facebook-clone-green -n facebook-clone --replicas=0

# 2. Download the base backup
aws s3 sync s3://$BACKUP_BUCKET/basebackup/<nearest-backup-before-incident>/ \
  /var/lib/postgresql/data_restore/

# 3. Create recovery configuration file
cat > /var/lib/postgresql/data_restore/recovery.conf << EOF
restore_command = 'aws s3 cp s3://$BACKUP_BUCKET/wal/%f %p'
recovery_target_time = '2026-03-13 14:30:00 UTC'   ← set to just before corruption
recovery_target_action = 'promote'
EOF

# 4. Start PostgreSQL in recovery mode pointing at the restored data directory
# (Use pg_ctl or restart the DB service with the new data directory)

# 5. PostgreSQL will replay WAL segments up to the target time

# 6. Verify data at the recovery point
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "SELECT COUNT(*) FROM posts; SELECT MAX(created_at) FROM posts;"

# 7. Resume application
kubectl scale deployment facebook-clone-blue -n facebook-clone --replicas=2
```

**RPO with WAL archiving enabled:** ~1–5 minutes (one `archive_timeout` interval worth of WAL).

---

### 4.2 Media File Recovery (S3)

#### Restore from S3 Versioning

```bash
# List versions of a deleted object
aws s3api list-object-versions \
  --bucket $S3_BUCKET_NAME \
  --prefix "media/users/avatar/user-123.jpg"

# Remove delete marker to restore the latest version
aws s3api delete-object \
  --bucket $S3_BUCKET_NAME \
  --key "media/users/avatar/user-123.jpg" \
  --version-id "<delete-marker-version-id>"

# Restore a specific older version
aws s3api copy-object \
  --bucket $S3_BUCKET_NAME \
  --copy-source "$S3_BUCKET_NAME/media/users/avatar/user-123.jpg?versionId=<version-id>" \
  --key "media/users/avatar/user-123.jpg"
```

#### Cross-Region Backup Restore

```bash
# If primary region S3 is unavailable, serve from replica bucket
# Update S3_BUCKET_NAME and S3_REGION in the Kubernetes secret
# (see Scenario 5 recovery steps above)

# Sync replica back to primary once primary is restored
aws s3 sync \
  s3://$S3_BUCKET_NAME-backup \
  s3://$S3_BUCKET_NAME \
  --source-region us-west-2 \
  --region us-east-1
```

---

## 5. JWT Key Rotation Runbook

Use this procedure for **planned** key rotation (security audit, scheduled rotation policy, credential hygiene). For **emergency** rotation after a compromise, go directly to Scenario 7 in §3.

### Step 1: Generate New Key

```bash
# Generate a cryptographically secure 256-bit key
NEW_JWT_SECRET=$(openssl rand -hex 32)
echo "New key generated. Store in your secrets manager before proceeding."
# Store in AWS Secrets Manager or HashiCorp Vault before continuing
```

### Step 2: Deploy Dual-Key Validation Period (Zero-Downtime)

To avoid logging out all users at once, deploy a version of the application that accepts tokens signed with **either** the old OR the new key:

```bash
# Add NEW_JWT_SECRET as a secondary validation key in app settings
# The app should validate: try new key → if fails → try old key

# Update secrets with BOTH keys
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=JWT_SECRET_KEY="$NEW_JWT_SECRET" \
  --from-literal=JWT_SECRET_KEY_OLD="$OLD_JWT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -

# Deploy the dual-key validation build
kubectl rollout restart deployment/facebook-clone-blue -n facebook-clone
kubectl rollout status deployment/facebook-clone-blue -n facebook-clone
```

### Step 3: Token Migration Period (24–48 hours)

Wait for existing tokens to expire naturally. Token lifespan is typically 15 minutes (access) or 7 days (refresh). Allow at least one full refresh token lifetime (7 days) for a seamless migration with no forced re-authentication.

```bash
# Monitor: count of tokens being validated against the OLD key
# Prometheus query (if instrumented): jwt_validation_old_key_total
# When this counter approaches 0, all active tokens use the new key
```

### Step 4: Full Rotation — Remove Old Key

```bash
# Remove the OLD key from secrets
kubectl create secret generic facebook-clone-secrets \
  --namespace=facebook-clone \
  --from-literal=JWT_SECRET_KEY="$NEW_JWT_SECRET" \
  --dry-run=client -o yaml | kubectl apply -f -
# (Omit JWT_SECRET_KEY_OLD entirely)

# Deploy the single-key build
kubectl rollout restart deployment/facebook-clone-blue  -n facebook-clone
kubectl rollout restart deployment/facebook-clone-green -n facebook-clone
kubectl rollout status deployment/facebook-clone-blue   -n facebook-clone
```

### Step 5: Cleanup and Verification

```bash
# Verify old key is no longer in any pod's environment
kubectl exec -n facebook-clone <pod-name> -- env | grep JWT
# Should show only JWT_SECRET_KEY (no JWT_SECRET_KEY_OLD)

# Test token issuance and validation
curl -X POST https://api.example.com/api/v1/auth/login \
  -d '{"username":"test@example.com","password":"testpassword"}' \
  -H "Content-Type: application/json"
# Should return a valid access token

# Verify old tokens are now rejected (use a token from before Step 2)
curl https://api.example.com/api/v1/me \
  -H "Authorization: Bearer <old-token>"
# Should return 401 Unauthorized
```

---

## 6. Security Incident Response

### 6.1 Compromised Token

**Scenario:** A specific user's JWT token has been stolen and is being used by an attacker.

```bash
# 1. Extract the JTI (JWT ID) from the stolen token
# Decode: echo "<token>" | cut -d. -f2 | base64 -d | jq .jti

# 2. Blacklist the specific token in Redis (lasts until token natural expiry)
kubectl exec -n facebook-clone <redis-pod> -- \
  redis-cli SET "blacklist:<jti>" 1 EX <remaining-ttl-seconds>

# 3. Force password reset for the affected user
# Via admin API or directly in DB:
psql -h $DB_HOST -U $DB_USER facebook_clone \
  -c "UPDATE users SET password_reset_required=true WHERE id='<user-id>';"

# 4. Audit login activity for the affected user
kubectl logs -n facebook-clone -l app=facebook-clone \
  | jq 'select(.user_id=="<user-id>")' | tail -50
```

### 6.2 Data Breach

```bash
# Immediate actions within first hour:
# 1. Scope assessment: which tables/records were accessed?
#    - Audit PostgreSQL logs: SELECT * FROM pg_stat_activity WHERE query LIKE '%SELECT%';
#    - Review application access logs in Loki for the attacker's session

# 2. Revoke the compromised credentials used to access the data
# 3. Preserve evidence: snapshot logs, DB audit trail, K8s events

# Notification obligations (consult legal team):
# - GDPR: notify supervisory authority within 72 hours of discovery
# - Affected users: notify without undue delay if likely to cause harm
# - Internal: immediate notification to security lead, CTO, legal

# Data assessment checklist:
# □ Which user records were accessed? (PII: email, name, profile data)
# □ Were passwords exposed? (bcrypt hashed — low risk but notify)
# □ Were private messages exposed?
# □ Were payment details exposed? (PCI scope — notify card brands)
# □ How long was unauthorized access active?
```

### 6.3 Unauthorized Access — Audit Log Analysis

```bash
# Find all requests by a suspicious user/IP in the last 24 hours
{namespace="facebook-clone"} | json
  | remote_addr="<suspicious-ip>"
  | line_format "{{.timestamp}} {{.method}} {{.path}} {{.status}}"

# Find all admin actions
{namespace="facebook-clone"} | json | path=~"/api/v1/admin/.*"

# Find privilege escalation attempts (403 responses)
{namespace="facebook-clone"} | json | status=403

# Find mass data export attempts (large response bodies)
{namespace="facebook-clone"} | json | response_size > 1000000
```

---

## 7. Recovery Testing Schedule

Regular DR drills ensure that recovery procedures work when needed and that the team is practiced.

### 7.1 Monthly: Blue/Green Rollback Drill

**Objective:** Verify rollback script works in production and takes < 60 seconds.

```
□ Schedule during low-traffic window (e.g., Sunday 02:00 UTC)
□ Notify team in #ops-facebook-clone 24 hours in advance
□ Deploy a "canary" version to the inactive slot
□ Switch traffic to the canary slot
□ Immediately run rollback: ./deploy/scripts/rollback.sh production
□ Measure time from rollback start to confirmed traffic switch
□ Record result: target < 60 seconds
□ Confirm no user-facing errors during drill (check Grafana)
□ Document any issues in the drill log
```

### 7.2 Quarterly: Full Database Restore Drill

**Objective:** Verify that the most recent automated backup can be restored to a test environment in < 4 hours.

```
□ Provision a temporary test PostgreSQL instance (same version: 16)
□ Download the latest automated backup from S3
□ Execute the full restore procedure (RUNBOOK §5.2)
□ Verify row counts match the expected values at backup time
□ Run alembic current to confirm schema version
□ Run the full test suite against the restored DB
□ Document restore time and any issues
□ Tear down the test instance
□ Update the RTO/RPO table in §1 if capability has changed
```

### 7.3 Semi-Annual: Full DR Simulation

**Objective:** Simulate a complete datacenter failure and validate recovery to the DR region.

```
□ Engage all stakeholders: engineering, product, leadership
□ Pre-brief on-call team 1 week in advance
□ Simulate primary region unavailability (block traffic at DNS/load balancer level)
□ Execute DR region activation:
  - Switch DNS to DR cluster endpoint
  - Restore latest DB backup to DR PostgreSQL
  - Verify S3 replica bucket is accessible
  - Scale DR cluster application pods to production capacity
□ Verify all critical user flows in DR environment:
  - User login
  - Post creation
  - Feed retrieval
  - Media upload
□ Measure actual RTO against targets in §1
□ Revert to primary region after 30-minute validation window
□ Document gaps, update DR runbook, file action items
```

### 7.4 Drill Log Template

| Date | Drill Type | Lead | Duration | Result | Issues Found | Action Items |
|---|---|---|---|---|---|---|
| YYYY-MM-DD | Rollback Drill | Name | X seconds | Pass/Fail | None / Description | Ticket links |
| YYYY-MM-DD | DB Restore Drill | Name | X minutes | Pass/Fail | None / Description | Ticket links |
| YYYY-MM-DD | Full DR Sim | Name | X minutes | Pass/Fail | None / Description | Ticket links |

---

## 8. Contact & Escalation Matrix

| Role | Name | Primary Contact | Secondary Contact | Escalation Condition |
|---|---|---|---|---|
| On-Call Engineer (L1) | _(Rotation)_ | PagerDuty | Slack `@oncall-eng` | Any P0/P1 alert |
| Backend Lead (L2) | _TBD_ | Phone: _TBD_ | Slack `@backend-lead` | P0/P1 not resolved in 15 min |
| Engineering Manager (L3) | _TBD_ | Phone: _TBD_ | Slack `@eng-manager` | P0 not resolved in 30 min |
| CTO (L4) | _TBD_ | Phone: _TBD_ | Email: _TBD_ | P0 not resolved in 1 hr |
| DBA / Data Lead | _TBD_ | Phone: _TBD_ | Slack `@dba` | Any DB failure or data loss |
| Security Lead | _TBD_ | Phone: _TBD_ | Slack `@security` | Any security breach / compromise |
| Cloud Infra Lead | _TBD_ | Phone: _TBD_ | Slack `@infra` | K8s cluster failure, AZ failure |
| Legal / Compliance | _TBD_ | Email: _TBD_ | Phone: _TBD_ | Data breach, GDPR notification required |
| AWS Support | — | Console: support.aws.amazon.com | Phone: _TBD_ | AWS service failure (S3, RDS, etc.) |
| PagerDuty | — | Service: `facebook-clone-production` | — | Automated alert routing |

### Escalation Flow

```
Alert Fires
    │
    ▼
L1 On-Call Engineer ──(15 min, no resolution)──► L2 Backend Lead
                                                        │
                                              (15 min, no resolution)
                                                        │
                                                        ▼
                                              L3 Engineering Manager
                                                        │
                                              (30 min, no resolution)
                                                        │
                                                        ▼
                                                     L4 CTO
```

### External Contacts

| Vendor | Service | Contact | SLA |
|---|---|---|---|
| AWS | Cloud infrastructure | support.aws.amazon.com | Business/Enterprise support plan |
| GitHub | CI/CD | githubstatus.com / support | — |
| PagerDuty | Alerting | app.pagerduty.com | — |
| Grafana | Observability | grafana.com/support | — |

---

*End of Disaster Recovery Plan — For day-to-day operational procedures, see [RUNBOOK.md](./RUNBOOK.md).*
