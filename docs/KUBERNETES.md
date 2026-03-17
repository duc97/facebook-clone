# Kubernetes Deployment Guide

Facebook Clone Backend — Kubernetes · NGINX Ingress · cert-manager · Prometheus · Kustomize

> **Version:** 1.0 · **Last updated:** 2026-03-17
> **Stack:** Python 3.12 · FastAPI · PostgreSQL · Redis · NGINX Ingress · cert-manager · Prometheus/Grafana · Kustomize

---

## Table of Contents

1. [Overview](#1-overview)
2. [Namespace & Kustomize Structure](#2-namespace--kustomize-structure)
3. [Blue/Green Deployment Strategy](#3-bluegreen-deployment-strategy)
4. [Pod Configuration Deep-Dive](#4-pod-configuration-deep-dive)
5. [Horizontal Pod Autoscaler](#5-horizontal-pod-autoscaler)
6. [Resource Management](#6-resource-management)
7. [Ingress and TLS](#7-ingress-and-tls)
8. [Security](#8-security)
9. [Observability](#9-observability)
10. [Advantages Summary](#10-advantages-summary)
11. [Future Optimisation Roadmap](#11-future-optimisation-roadmap)
12. [Verification / How to Apply](#12-verification--how-to-apply)

---

## 1. Overview

The Facebook Clone backend runs on Kubernetes using a blue/green deployment strategy across two
parallel Deployment slots. Traffic is routed through an NGINX Ingress controller with TLS
certificates managed automatically by cert-manager and Let's Encrypt. A multi-metric HPA scales the
active slot between 2 and 20 replicas based on CPU, memory, and live WebSocket connection counts.
Prometheus scrapes every pod for metrics, and a structured set of alert rules covers error rate,
latency, crash loops, and resource saturation.

### Technology Components

| Component | Role |
|-----------|------|
| **NGINX Ingress** | TLS termination, rate limiting, WebSocket upgrade, CORS enforcement |
| **cert-manager** | Automated Let's Encrypt certificate issuance and renewal |
| **Kustomize** | Layered manifest composition — base + production overlay |
| **Prometheus** | Metrics scraping, alerting rules, custom HPA metric source |
| **Grafana / Loki** | Dashboards and log aggregation (via `deploy/observability/`) |
| **Alertmanager** | Alert routing and notification |

### High-Level Cluster Architecture

```
                      ┌───────────────────────────────────────────────────────┐
                      │                   Internet / Clients                  │
                      │         (Browser, Mobile App, API Consumers)          │
                      └────────────────────────┬──────────────────────────────┘
                                               │ HTTPS (443) / WSS
                                               ▼
                      ┌────────────────────────────────────────────────────────┐
                      │             NGINX Ingress Controller                   │
                      │   TLS: cert-manager + Let's Encrypt (HTTP-01)          │
                      │   Rate limit: 100 rps / 20 conn · Body limit: 50 MB    │
                      │   Host: api.facebook-clone.example.com                 │
                      └───────┬────────────────────────────┬───────────────────┘
                              │ slot: blue (active)         │ slot: green (standby)
                              ▼                             ▼
              ┌───────────────────────────┐   ┌────────────────────────────┐
              │  Service: facebook-clone  │   │  Service: facebook-clone   │
              │  (selector: slot=blue)    │   │  (selector: slot=green)    │
              │  ← active during normal   │   │  ← promoted on next deploy │
              └─────────────┬─────────────┘   └─────────────┬──────────────┘
                            │                               │
              ┌─────────────▼─────────────┐   ┌────────────▼───────────────┐
              │  Deployment: blue         │   │  Deployment: green          │
              │  HPA: 2→20 replicas       │   │  Replicas: 2 (base)        │
              │  CPU 70% · Mem 80%        │   │  (receives new image first) │
              │  WS connections: 100 avg  │   │                             │
              └─────────────┬─────────────┘   └─────────────┬──────────────┘
                            │                               │
          ┌─────────────────┼───────────────────────────────┼─────────────┐
          │                 │                               │             │
          ▼                 ▼                               ▼             ▼
  ┌──────────────┐  ┌──────────────┐               ┌────────────┐  ┌───────────────┐
  │  PostgreSQL  │  │    Redis     │               │  S3/MinIO  │  │  Observability│
  │  Port 5432   │  │  Port 6379   │               │  Port 443  │  │  Prometheus   │
  │  pool: 20    │  │  Cache/PubSub│               │  Uploads   │  │  Grafana      │
  │  overflow:40 │  │  Token BL    │               │  Media     │  │  Loki/Promtail│
  └──────────────┘  └──────────────┘               └────────────┘  └───────────────┘

Namespaces:
  production  — app workloads (blue + green Deployments, Services, HPA, NetworkPolicy)
  staging     — mirrors production, lower resource quotas
  monitoring  — Prometheus, Grafana, Loki, Alertmanager (allowed to scrape production pods)
```

---

## 2. Namespace & Kustomize Structure

### 2.1 Namespaces

Three namespaces are declared in `deploy/k8s/base/namespace.yaml`:

| Namespace | Purpose | Key Labels |
|-----------|---------|------------|
| `production` | Live workloads — blue/green Deployments, Services, HPA, NetworkPolicy | `environment: production` |
| `staging` | Pre-production mirror, lower resource quota | `environment: staging` |
| `monitoring` | Prometheus, Grafana, Loki, Alertmanager | `purpose: observability` |

Namespace isolation is enforced at the network layer: `NetworkPolicy` objects in `production` only
allow ingress from the `ingress-nginx` and `monitoring` namespaces (see §8).

### 2.2 Kustomize Base / Overlay Pattern

Kustomize composes Kubernetes manifests through inheritance rather than templating. The base layer
defines shared infrastructure resources; overlays patch environment-specific values on top.

```
deploy/k8s/
├── base/                          # Shared infrastructure
│   ├── kustomization.yaml         # Lists: namespace, rbac, configmap, secret, resource-quota
│   ├── namespace.yaml             # production / staging / monitoring namespaces
│   ├── rbac.yaml                  # ServiceAccount + Role + RoleBinding
│   ├── configmap.yaml             # DB pool, S3 backend, cache flags
│   └── resource-quota.yaml        # ResourceQuota + LimitRange
│
├── app/                           # Application workload manifests
│   ├── deployment-blue.yaml       # Blue slot Deployment
│   ├── deployment-green.yaml      # Green slot Deployment (mirror)
│   ├── service.yaml               # Active service + blue/green permanent services
│   ├── hpa.yaml                   # HorizontalPodAutoscaler
│   ├── pdb.yaml                   # PodDisruptionBudget
│   ├── ingress.yaml               # NGINX Ingress (TLS, rate limiting, WebSocket)
│   ├── cert-issuer.yaml           # cert-manager ClusterIssuer (Let's Encrypt)
│   └── network-policy.yaml        # Default-deny + allow rules
│
└── overlays/
    └── production/
        └── kustomization.yaml     # References base + app; patches replicas to 3; pins image tag
```

### 2.3 How `kustomize build` Works

```
kustomize build deploy/k8s/overlays/production/
```

1. **Load base** — renders `namespace.yaml`, `rbac.yaml`, `configmap.yaml`, `secret.yaml`,
   `resource-quota.yaml`.
2. **Load overlay resources** — adds `deployment-blue.yaml`, `deployment-green.yaml`,
   `service.yaml`, `hpa.yaml`, `pdb.yaml`, `ingress.yaml`, `cert-issuer.yaml`,
   `network-policy.yaml`.
3. **Apply images transform** — rewrites all `ghcr.io/your-org/facebook-clone` image references to
   use the tag specified in `newTag` (replaced by CI/CD with a concrete digest).
4. **Apply JSON patches** — sets `spec.replicas` to `3` on `facebook-clone-blue`.
5. **Set namespace** — forces all namespaced resources to `production`.
6. **Emit merged YAML** — the final stream is piped to `kubectl apply`.

### 2.4 Resource Composition Tree (Production)

```
overlays/production/kustomization.yaml
├── base/
│   ├── Namespace (production, staging, monitoring)
│   ├── ServiceAccount (facebook-clone)
│   ├── Role (facebook-clone-role)
│   ├── RoleBinding (facebook-clone-rolebinding)
│   ├── ConfigMap (facebook-clone-config)
│   ├── ResourceQuota (production-quota)
│   └── LimitRange (production-limits)
└── app/
    ├── Deployment (facebook-clone-blue)  ← patched: replicas=3
    ├── Deployment (facebook-clone-green) ← base replicas=2
    ├── Service (facebook-clone)          ← active selector
    ├── Service (facebook-clone-blue)
    ├── Service (facebook-clone-green)
    ├── HorizontalPodAutoscaler (facebook-clone-hpa)
    ├── PodDisruptionBudget (facebook-clone-pdb)
    ├── Ingress (facebook-clone-ingress)
    ├── ClusterIssuer (letsencrypt-prod)
    └── NetworkPolicy ×3 (default-deny, allow-ingress-controller, allow-db-egress)
```

---

## 3. Blue/Green Deployment Strategy

### 3.1 What Blue/Green Deployment Is

Blue/green deployment maintains two identical environments — *blue* (currently live) and *green*
(idle). A new release is deployed to the idle slot first. Only after the new version has passed
health checks and is fully ready does traffic switch over — instantaneously, by updating a single
Service selector. The previous version remains untouched and can receive traffic again within
seconds if anything goes wrong.

This is the opposite of a rolling update, which replaces pods one-by-one within the live deployment.
Rolling updates blend two versions simultaneously for the duration of the rollout; blue/green
ensures users are always served by exactly one version at a time.

### 3.2 How the Three Services + Two Deployments Implement It

```
  Service: facebook-clone          (active — selector switches between blue/green)
  Service: facebook-clone-blue     (permanent — always selects slot=blue pods)
  Service: facebook-clone-green    (permanent — always selects slot=green pods)

  Deployment: facebook-clone-blue  (labels: app=facebook-clone, slot=blue)
  Deployment: facebook-clone-green (labels: app=facebook-clone, slot=green)
```

The **active service** (`facebook-clone`) is what the Ingress routes to. Its selector starts as
`{app: facebook-clone, slot: blue}`. After a successful green deploy, the selector is patched to
`{app: facebook-clone, slot: green}`.

The **slot-specific services** (`facebook-clone-blue`, `facebook-clone-green`) permanently target
each slot. They are used for direct health validation before traffic is switched — for example,
smoke-testing the green deployment via its dedicated service before committing to the traffic switch.

```
Ingress ──► Service (facebook-clone)  ◄── selector patch switches this
                         │
                  ┌──────┴──────┐
                  │             │
              slot=blue     slot=green
                  │             │
          [Pod blue-0]    [Pod green-0]
          [Pod blue-1]    [Pod green-1]
          [Pod blue-2]    [Pod green-2]
```

### 3.3 Blue/Green Deploy Script Walk-Through

`deploy/scripts/blue-green-deploy.sh <namespace> <image> <app-name>`

```
Step 1 — Identify active slot
  kubectl get service facebook-clone → reads .spec.selector.slot
  CURRENT_SLOT=blue  →  NEW_SLOT=green
  (defaults to "blue" if the service has never been annotated)

Step 2 — Update inactive deployment's image
  kubectl set image deployment/facebook-clone-green app=<IMAGE> -n <NS>
  This triggers a RollingUpdate within the green slot (maxUnavailable=0, maxSurge=1)

Step 3 — Wait for rollout
  kubectl rollout status deployment/facebook-clone-green --timeout=300s
  Blocks until all new pods are Running and their startupProbe + readinessProbe pass

Step 4 — Verify readiness
  Reads .status.readyReplicas from the green Deployment
  Exits with error if readyReplicas < 1 (prevents traffic switch to a broken slot)

Step 5 — Switch traffic (atomic)
  kubectl patch service facebook-clone \
    -p '{"spec":{"selector":{"app":"facebook-clone","slot":"green"}}}'
  kube-proxy updates iptables/IPVS rules on every node within ~1 second
  Zero new requests reach the old blue pods from this point forward

Step 6 — Report
  Prints rollback command for the old slot (blue) — kept alive for instant recovery
```

### 3.4 Rollback Procedure

Because the previous slot's pods remain running, rollback is a single `kubectl patch`:

```bash
# Rollback to blue (if green was just promoted)
kubectl patch service facebook-clone -n production \
  -p '{"spec":{"selector":{"app":"facebook-clone","slot":"blue"}}}'

# Rollback to green (if blue was just promoted)
kubectl patch service facebook-clone -n production \
  -p '{"spec":{"selector":{"app":"facebook-clone","slot":"green"}}}'
```

Traffic returns to the previous version in under one second. No image pulls, no pod restarts, no
waiting for readiness probes.

### 3.5 Blue vs Green Deployment Configuration

Both manifests are structurally identical; only the `slot` label differs:

| Field | Blue | Green |
|-------|------|-------|
| `metadata.name` | `facebook-clone-blue` | `facebook-clone-green` |
| `metadata.labels.slot` | `blue` | `green` |
| `spec.selector.matchLabels.slot` | `blue` | `green` |
| `spec.template.metadata.labels.slot` | `blue` | `green` |
| `spec.replicas` (base) | `2` | `2` |
| `spec.replicas` (production overlay) | `3` (patched) | `2` (not patched) |

All other fields — probes, securityContext, resources, affinity, tolerations, volumes — are
identical. This symmetry ensures the idle slot is a true production mirror, not a degraded copy.

### 3.6 Advantages and Disadvantages

**Advantages**

| Advantage | Detail |
|-----------|--------|
| Zero-downtime releases | Traffic switches atomically; no partially-updated Deployment |
| Instant rollback | Previous slot stays warm — rollback in < 1 second |
| Full validation before exposure | New version can be smoke-tested on `facebook-clone-green` service before the selector patch |
| No version mixing | Users are never served by two different application versions simultaneously |
| Blast radius isolation | A crash in the new slot cannot affect the live slot before switch |

**Disadvantages / Known Gaps**

| Disadvantage | Impact |
|-------------|--------|
| Double resource cost | Both slots must be sized for production load; 2× pod count at all times |
| Manual HPA target | `hpa.yaml` hardcodes `scaleTargetRef.name: facebook-clone-blue`. After a green promotion, the HPA no longer scales the active slot — must be patched manually (see O2 in §11) |
| No automatic health gate | The script checks `readyReplicas >= 1` but does not validate error rate, latency, or integration tests. A buggy release with passing probes will still be promoted (see O2) |
| State migration risk | If a DB migration changes schema in a backward-incompatible way, the old blue slot becomes incompatible with the new schema |

---

## 4. Pod Configuration Deep-Dive

### 4.1 Pod Security Context

Applied at the `spec.securityContext` (Pod) level — inherited by all containers:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  runAsGroup: 1001
  fsGroup: 1001
  seccompProfile:
    type: RuntimeDefault
```

| Setting | Effect |
|---------|--------|
| `runAsNonRoot: true` | Kubernetes rejects the pod if the container image runs as UID 0; defence against image misconfiguration |
| `runAsUser/Group: 1001` | Sets a specific unprivileged UID/GID rather than the image default |
| `fsGroup: 1001` | All files mounted in volumes (e.g., the `uploads` emptyDir) are owned by GID 1001, allowing the app process to write to them |
| `seccompProfile: RuntimeDefault` | Activates the container runtime's default syscall filter (blocks dangerous syscalls like `ptrace`, `mount`, `reboot`) |

### 4.2 Container Security Context

Applied at the individual `containers[].securityContext` level:

```yaml
securityContext:
  allowPrivilegeEscalation: false
  readOnlyRootFilesystem: false    # ⚠ See O6 in §11
  capabilities:
    drop: ["ALL"]
```

| Setting | Effect |
|---------|--------|
| `allowPrivilegeEscalation: false` | Prevents `setuid` binaries from gaining elevated privileges; blocks `sudo`-style escalation |
| `readOnlyRootFilesystem: false` | **Current gap.** Ideally `true` for Distroless hardening; currently disabled because `/app/uploads` is written directly. Mitigation: move writes to the `uploads` emptyDir mountPath (see O6) |
| `capabilities.drop: ALL` | Drops every Linux capability (e.g., `NET_BIND_SERVICE`, `CHOWN`, `DAC_OVERRIDE`); the process runs with minimal kernel privilege |

### 4.3 Three-Probe Strategy

The deployment uses three complementary probes with non-overlapping responsibilities:

```
Startup Phase (0–120s)          Healthy Phase
──────────────────────────────────────────────────────────────────────
startupProbe                    → DISABLED once passed
  path: /health
  failureThreshold: 12
  periodSeconds: 10
  → 12 × 10s = 120s max grace for slow starts (migrations, warm-up)
  → Until this passes, liveness/readiness are NOT active

                                readinessProbe (every 10s)
                                  path: /ready  ← checks DB + Redis
                                  failureThreshold: 3
                                  → Removes pod from Service endpoints
                                  → Pod stays Running but receives no traffic
                                  → Self-heals when dependency recovers

                                livenessProbe (every 30s)
                                  path: /health  ← basic process check
                                  failureThreshold: 3
                                  → Restarts container on 3 consecutive failures
                                  → Used for deadlock/hang detection
```

**Why `/health` and `/ready` are separate endpoints:**

- `/health` — answers "is the process alive?" It checks only in-process state: the event loop is
  running, there are no unrecoverable errors. It must respond even when external dependencies are
  down. Used by `startupProbe` and `livenessProbe`.
- `/ready` — answers "can this pod safely receive traffic?" It checks external dependencies:
  PostgreSQL connection, Redis ping. A pod failing `/ready` is removed from the Service's endpoint
  slice but is not restarted — it recovers automatically when the database comes back. Used by
  `readinessProbe`.

Using `/health` for liveness and `/ready` for readiness is the correct Kubernetes pattern. The
opposite (using `/ready` for liveness) would cause pods to be killed and restarted every time
PostgreSQL has a momentary connectivity blip.

### 4.4 Graceful Shutdown Sequence

```
Time  Event
───────────────────────────────────────────────────────────────────────
  0s  Pod receives SIGTERM (from Kubernetes during scale-down/rolling update)

  0s  preStop hook executes: sleep 5
      → The pod is removed from the Service endpoint slice before SIGTERM,
        but kube-proxy propagation can lag by 1–3s.
        The 5s sleep ensures no new connections are routed to the pod
        after the endpoint is removed but before SIGTERM is fully handled.

  5s  SIGTERM reaches the application process (uvicorn)
      → FastAPI begins graceful shutdown: stops accepting new requests,
        drains in-flight requests.

 60s  terminationGracePeriodSeconds deadline
      → If the process has not exited, Kubernetes sends SIGKILL.
      → 60s provides ample time for in-flight WebSocket sessions and
        long-running GraphQL queries to complete.
```

The preStop hook uses `sh -c sleep 5`. This is currently broken when using the Distroless image
(which has no shell) — the same root cause as the init container issue (see §4.5). After the
Distroless migration (see `docs/PODMAN_DISTROLESS.md`), `preStop` must be changed to use the exec
form directly: `command: ["sleep", "5"]`.

### 4.5 Init Container — ⚠ Broken After Distroless Migration

```yaml
initContainers:
  - name: run-migrations
    image: ghcr.io/your-org/facebook-clone:latest
    command: ["sh", "-c", "alembic upgrade head"]
```

**Problem:** The production/Distroless image contains no shell (`sh`). This init container will fail
at startup with `exec: "sh": executable file not found in $PATH`, blocking the main container from
starting and causing the pod to enter `Init:CrashLoopBackOff`.

**Why this is the most urgent fix:** Every pod startup — including the rollout of the inactive slot
during a blue/green deploy — depends on the init container succeeding. A broken init container
silently prevents all deployments.

**Correct approach:** Run migrations as a separate pre-deploy Kubernetes Job using the
development/non-Distroless image tag (see O1 and O7 in §11).

### 4.6 Pod Scheduling Constraints

**Pod Anti-Affinity**

```yaml
affinity:
  podAntiAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
      - weight: 100
        podAffinityTerm:
          labelSelector:
            matchLabels:
              app: facebook-clone
          topologyKey: kubernetes.io/hostname
```

The scheduler *prefers* (weight 100 = maximum preference) to place each pod on a different node.
`preferredDuring...` rather than `requiredDuring...` means the scheduler still places pods if
insufficient nodes are available — avoiding stuck pending pods at the cost of co-location.

**Topology Spread Constraints (Zone Spreading)**

```yaml
topologySpreadConstraints:
  - maxSkew: 1
    topologyKey: topology.kubernetes.io/zone
    whenUnsatisfiable: DoNotSchedule
    labelSelector:
      matchLabels:
        app: facebook-clone
```

Ensures pods are spread across availability zones with at most 1 pod difference between the most
and least populated zone. `whenUnsatisfiable: DoNotSchedule` makes this a hard constraint — a pod
will remain Pending rather than violate the skew. Combined with anti-affinity, this provides
multi-AZ resilience.

**Spot Node Toleration**

```yaml
tolerations:
  - key: "node.kubernetes.io/spot"
    operator: "Exists"
    effect: "NoSchedule"
```

Allows pods to be scheduled on spot/preemptible nodes, which are typically tainted with
`node.kubernetes.io/spot:NoSchedule` to prevent non-tolerant workloads from landing on them. This
reduces infrastructure cost but requires the graceful shutdown sequence (§4.4) to handle
preemption notices correctly.

---

## 5. Horizontal Pod Autoscaler

### 5.1 Overview

```yaml
scaleTargetRef:
  kind: Deployment
  name: facebook-clone-blue   # ⚠ Hardcoded — must be updated after green promotion
minReplicas: 2
maxReplicas: 20
```

The HPA manages the replica count of the **active** Deployment. With 3 replicas set by the
production overlay, the HPA will not scale below 3 (it takes the max of `minReplicas` and the
current desired replicas when scaling down).

### 5.2 Multi-Metric Scaling

Three independent metrics drive scaling decisions; the HPA uses the metric that demands the highest
replica count:

```
Metric 1: CPU Utilization
  Target: averageUtilization: 70%
  Example: 3 pods at 90% CPU average → HPA calculates ceil(3 × 90/70) = 4 pods needed

Metric 2: Memory Utilization
  Target: averageUtilization: 80%
  Example: 3 pods at 95% memory → HPA calculates ceil(3 × 95/80) = 4 pods needed

Metric 3: WebSocket Connections (custom)
  Type: Pods  metric: websocket_connections_active
  Target: averageValue: 100 connections per pod
  Example: 3 pods with 600 total WS connections → 600/100 = 6 pods needed
```

The WebSocket metric is required because CPU and memory do not reflect WebSocket load well —
long-lived connections consume minimal CPU while holding goroutines and file descriptors. Without
this metric, the cluster would underscale during a WebSocket-heavy load spike.

**Infrastructure prerequisite:** The `websocket_connections_active` metric must be exposed by
application pods at `/metrics` (Prometheus format), scraped by Prometheus, and made available to
the HPA via the **Prometheus Adapter** (a Kubernetes metrics API adapter that bridges Prometheus
metrics into the `custom.metrics.k8s.io` API group). See O4 for a simpler alternative using KEDA.

### 5.3 Scale-Up Behaviour

```yaml
scaleUp:
  stabilizationWindowSeconds: 30      # Only 30s before acting — respond quickly to spikes
  policies:
    - type: Pods
      value: 4                         # Add up to 4 pods per 60s window
      periodSeconds: 60
    - type: Percent
      value: 100                       # Or double the current count, whichever is larger
      periodSeconds: 60
  selectPolicy: Max                    # Use the policy that allows the most aggressive scale-up
```

A traffic spike can trigger the addition of `max(4, 100% of current)` pods per minute with only
30 seconds of stabilisation. For example, if the cluster has 3 pods and CPU spikes, it can reach 6
pods in the first minute and 12 in the second.

### 5.4 Scale-Down Behaviour

```yaml
scaleDown:
  stabilizationWindowSeconds: 300     # 5-minute cooldown prevents flapping
  policies:
    - type: Pods
      value: 2                         # Remove at most 2 pods per 60s window
      periodSeconds: 60
```

The conservative scale-down protects against load oscillation — a metric that briefly dips below
threshold will not immediately trigger a scale-down that removes capacity needed moments later. The
5-minute stabilisation window means the HPA only scales down if the cluster has been consistently
underloaded for 5 minutes.

### 5.5 HPA and the Production Overlay

The production overlay patches `facebook-clone-blue` to 3 replicas. The HPA's `minReplicas: 2`
acts as a floor. In practice, the effective minimum in production is 3 because Kustomize sets it;
the HPA will not scale below its own `minReplicas: 2` but also will not reduce what Kustomize set
unless the HPA's own scaling logic decides fewer than 3 are needed.

---

## 6. Resource Management

### 6.1 ResourceQuota (Namespace Ceiling)

Defined in `deploy/k8s/base/resource-quota.yaml`:

```
ResourceQuota: production-quota
  requests.cpu     : 8 cores     (total requested CPU across all pods)
  requests.memory  : 8 Gi        (total requested memory)
  limits.cpu       : 16 cores    (total CPU limits)
  limits.memory    : 16 Gi       (total memory limits)
  pods             : 50          (maximum pod count)
  services         : 20
  persistentvolumeclaims: 10
```

**Capacity analysis:** With HPA max=20 pods per slot and two slots, the theoretical maximum is 40
application pods. At 100m CPU request each, that is 4 cores — well within the 8-core request quota.
At CPU limit 1000m each, 40 pods would consume 40 cores in limits — exceeding the 16-core limit
quota. In practice the inactive slot is always 2–3 pods, so both slots combined (23 pods max) fit
within all quota limits.

### 6.2 LimitRange (Per-Container Defaults)

```
LimitRange: production-limits
  Container defaults (applied when not specified in the manifest):
    defaultRequest: cpu=100m, memory=128Mi
    default limit : cpu=500m,  memory=256Mi
  Container constraints:
    min:           cpu=50m,   memory=64Mi
    max:           cpu=2,     memory=1Gi
  Pod constraint:
    max:           cpu=4,     memory=2Gi
```

LimitRange ensures every container has resource requests and limits, even if the Deployment
manifest omits them. This prevents unbounded resource consumption by new workloads (e.g., sidecar
containers, one-off Jobs) that forget to specify limits.

### 6.3 Per-Pod Resource Configuration

The application container explicitly sets its own resources:

```
requests:  cpu=100m,  memory=256Mi
limits:    cpu=1000m, memory=512Mi
```

**CPU throttling implications:** The 10:1 ratio between CPU limit (1000m) and request (100m) means
the scheduler allocates 1/10 of a core for bin-packing, but the container can burst to a full core.
Under sustained load, the Linux CFS scheduler throttles the container back to its limit, causing
latency spikes rather than OOM kills. This is intentional for bursty workloads but should be
validated against actual P99 latency under load (see O3 in §11, which recommends VPA to right-size
requests).

**Memory:** The 2:1 memory ratio (256Mi request, 512Mi limit) is more conservative. Exceeding the
limit causes an OOM kill and container restart. The `readinessProbe` on `/ready` will keep the pod
out of rotation until it is healthy again.

### 6.4 Why Resource Management Matters

| Benefit | Mechanism |
|---------|-----------|
| Prevents noisy-neighbour | ResourceQuota prevents one component from consuming all namespace resources |
| Enables bin-packing | Scheduler uses `requests` (not limits) for placement; lower requests → higher pod density per node → lower cost |
| Guards against OOM at node level | `limits` cap what a container can consume; without limits, one container can trigger a node-level OOM kill affecting all pods |
| Predictable autoscaling | HPA percentage metrics are calculated against `requests`; consistent requests make HPA behaviour predictable |

---

## 7. Ingress and TLS

### 7.1 NGINX Ingress Configuration

```yaml
# deploy/k8s/app/ingress.yaml
annotations:
  kubernetes.io/ingress.class: nginx
  cert-manager.io/cluster-issuer: letsencrypt-prod
  nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/proxy-body-size: "50m"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "60"
  nginx.ingress.kubernetes.io/proxy-connect-timeout: "10"
  nginx.ingress.kubernetes.io/enable-cors: "true"
  nginx.ingress.kubernetes.io/cors-allow-origin: "https://facebook-clone.example.com"
  nginx.ingress.kubernetes.io/limit-rps: "100"
  nginx.ingress.kubernetes.io/limit-connections: "20"
  nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
  nginx.ingress.kubernetes.io/configuration-snippet: |
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
```

| Annotation | Value | Purpose |
|-----------|-------|---------|
| `ssl-redirect` | `true` | Permanent redirect of all HTTP → HTTPS; prevents accidental cleartext API calls |
| `proxy-body-size` | `50m` | Permits file uploads up to 50 MB (profile pictures, media); default nginx limit is 1 MB |
| `proxy-read-timeout` | `60` | Upstream read timeout in seconds; accommodates slow GraphQL queries without premature teardown |
| `proxy-connect-timeout` | `10` | Backend connection timeout; fails fast if pods are unreachable |
| `cors-allow-origin` | `https://facebook-clone.example.com` | CORS origin whitelist; pinned to the known frontend domain |
| `limit-rps` | `100` | Rate limit per client IP (requests per second); protects against bursting and scraping |
| `limit-connections` | `20` | Maximum concurrent connections per client IP |
| `proxy-http-version` | `1.1` | Required for WebSocket upgrade (HTTP/1.0 does not support `Upgrade` header) |
| `configuration-snippet` | `proxy_set_header Upgrade / Connection` | Passes WebSocket handshake headers to the upstream pod |

### 7.2 WebSocket Support

WebSocket connections begin as an HTTP/1.1 request with `Upgrade: websocket` and
`Connection: upgrade` headers. NGINX must forward these headers to the upstream rather than
stripping them (the default). The `configuration-snippet` annotation injects these `proxy_set_header`
directives directly into the NGINX `location` block generated by the Ingress controller.

### 7.3 TLS and cert-manager

```yaml
# ingress.yaml
spec:
  tls:
    - hosts:
        - api.facebook-clone.example.com
      secretName: facebook-clone-tls    # cert-manager creates/updates this Secret

# cert-issuer.yaml
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-key
    solvers:
      - http01:
          ingress:
            class: nginx
```

**Certificate lifecycle:**

```
1. cert-manager detects the Ingress resource (via cert-manager.io/cluster-issuer annotation)
2. cert-manager creates a Certificate resource for api.facebook-clone.example.com
3. cert-manager submits an ACME HTTP-01 challenge to Let's Encrypt
4. Let's Encrypt verifies /.well-known/acme-challenge/<token> via HTTP on port 80
   (cert-manager temporarily injects this path into the Ingress)
5. Let's Encrypt issues the certificate; cert-manager stores it in Secret: facebook-clone-tls
6. NGINX Ingress picks up the Secret and serves TLS
7. cert-manager monitors expiry and automatically renews ~30 days before expiration
```

**HTTP-01 limitation:** The cluster must be publicly reachable on port 80 for Let's Encrypt to
complete the challenge. See O10 in §11 for the DNS-01 alternative.

---

## 8. Security

### 8.1 NetworkPolicy

Three NetworkPolicy objects enforce a default-deny stance in the `production` namespace:

**Policy 1: default-deny-ingress**

```yaml
podSelector: {}      # Matches ALL pods in the namespace
policyTypes: [Ingress]
# No ingress rules → deny all inbound traffic to all pods
```

This is a catch-all baseline. Every pod in `production` starts with zero allowed ingress. Only
subsequent policies that explicitly match pods and allow specific sources override this.

**Policy 2: allow-ingress-controller**

```yaml
podSelector: {app: facebook-clone}
ingress:
  - from: [{namespaceSelector: {kubernetes.io/metadata.name: ingress-nginx}}]
    ports: [{TCP: 8000}]
  - from: [{namespaceSelector: {kubernetes.io/metadata.name: monitoring}}]
    ports: [{TCP: 8000}]
```

Application pods accept inbound TCP:8000 only from:
- The `ingress-nginx` namespace (NGINX Ingress controller forwarding external traffic)
- The `monitoring` namespace (Prometheus scraping `/metrics`)

**Policy 3: allow-db-egress**

```yaml
podSelector: {app: facebook-clone}
policyTypes: [Egress]
egress:
  - to: [{ipBlock: {cidr: 0.0.0.0/0}}]
    ports:
      - TCP:5432   # PostgreSQL
      - TCP:6379   # Redis
      - TCP:443    # HTTPS (S3, external APIs)
      - TCP:53     # DNS
      - UDP:53     # DNS
```

Outbound traffic is whitelisted by port. The `0.0.0.0/0` CIDR allows connections to any IP on
these ports — suitable when database IPs are not static. For a more hardened setup, restrict the
CIDR to the specific IP ranges of the PostgreSQL and Redis clusters.

### 8.2 RBAC

```
ServiceAccount: facebook-clone  (namespace: production)
    │
    └─ RoleBinding: facebook-clone-rolebinding
           └─ Role: facebook-clone-role
                  └─ Rules:
                       resources: configmaps, secrets
                       verbs: get, list, watch
```

The application pod's service account can only read ConfigMaps and Secrets within the `production`
namespace. It cannot create, update, or delete any resources, and has no cluster-level permissions.
This follows the **principle of least privilege** — a compromised pod cannot escalate to cluster
admin or modify other workloads.

### 8.3 Container Hardening Summary

| Control | Status | Detail |
|---------|--------|--------|
| Non-root user | ✅ Active | `runAsUser: 1001`, `runAsNonRoot: true` |
| Privilege escalation blocked | ✅ Active | `allowPrivilegeEscalation: false` |
| All capabilities dropped | ✅ Active | `capabilities.drop: ALL` |
| Seccomp profile | ✅ Active | `seccompProfile: RuntimeDefault` |
| Read-only root filesystem | ⚠ Disabled | `readOnlyRootFilesystem: false` — blocked by `/app/uploads` write path (see O6) |
| Network default-deny | ✅ Active | NetworkPolicy default-deny-ingress + whitelist |
| Minimal RBAC | ✅ Active | get/list/watch on configmaps/secrets only |

---

## 9. Observability

### 9.1 Prometheus Metrics Scraping

Every pod is annotated for auto-discovery by the Prometheus operator or a `prometheus.io/scrape`
annotation scraper:

```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "8000"
  prometheus.io/path: "/metrics"
```

Prometheus scrapes `http://<pod-ip>:8000/metrics` at its configured interval (typically 15–30s),
collecting all metrics exposed by the FastAPI application (request counters, latency histograms,
database pool metrics, WebSocket connection gauges).

### 9.2 Alert Rules

All rules are defined in `deploy/observability/prometheus/rules/alerts.yml` with a 30-second
evaluation interval.

| Alert | Expression | Threshold | For | Severity | Action |
|-------|-----------|-----------|-----|----------|--------|
| `HighErrorRate` | 5xx rate / total rate | > 5% | 2m | critical | Check recent deploy; inspect pod logs |
| `HighP99Latency` | `histogram_quantile(0.99, ...)` | > 2s | 5m | warning | Check DB pool saturation; look for slow queries |
| `PodCrashLooping` | `rate(restarts[15m]) > 0` | any | 5m | critical | Inspect pod logs; check init container; check OOM kills |
| `DeploymentReplicasMismatch` | spec replicas ≠ available replicas | any | 5m | warning | Check HPA status; check resource quota; check node capacity |
| `RedisHighMemory` | used / max | > 85% | 5m | warning | Review cache TTLs; consider memory increase |
| `DBPoolSaturation` | pool_checked_out / pool_size | > 80% | 3m | warning | Review `DB_POOL_SIZE` (currently 20); check for connection leaks |

### 9.3 Observability Stack

The observability stack is configured in `deploy/observability/` (separate from the Kubernetes
manifests):

```
deploy/observability/
├── prometheus/
│   ├── prometheus.yml          # Scrape config, alertmanager integration
│   └── rules/
│       └── alerts.yml          # Alert rule groups
├── grafana/
│   └── dashboards/             # Pre-built JSON dashboards
├── loki/
│   └── loki-config.yml         # Log retention, storage backend
└── promtail/
    └── promtail-config.yml     # Log shipping from pod stdout/stderr
```

**Data flow:**

```
Pod stdout/stderr
    └── Promtail (DaemonSet) ──► Loki ──► Grafana (log panels)

Pod /metrics
    └── Prometheus ──► Alertmanager ──► PagerDuty / Slack
                  └──► Grafana (metric panels)
                  └──► kube-state-metrics ──► HPA (custom metrics via Prometheus Adapter)
```

### 9.4 ConfigMap Settings Affecting Observability

```yaml
# deploy/k8s/base/configmap.yaml
DATABASE_ECHO: "false"     # Set to "true" temporarily for query logging
LOG_LEVEL: "info"          # Set to "debug" for verbose request tracing
DB_POOL_SIZE: "20"         # Baseline pool size; DBPoolSaturation alert fires at 80% = 16 connections
DB_POOL_MAX_OVERFLOW: "40" # Allows bursting to 60 total connections before rejection
DB_POOL_RECYCLE: "3600"    # Recycle connections every hour; prevents stale connection errors
CACHE_ENABLED: "true"      # Disabling this increases DB load significantly
```

---

## 10. Advantages Summary

Comparison between the current setup and a naive single-Deployment approach:

| Capability | Naive Single Deployment | Current Setup | Benefit |
|-----------|------------------------|---------------|---------|
| **Release downtime** | Rolling update — brief mixed-version window | Blue/green — atomic traffic switch | Zero user-visible downtime |
| **Rollback speed** | Minutes (new rollout required) | Seconds (single `kubectl patch`) | Near-instant recovery |
| **Concurrent version isolation** | Two versions serve traffic simultaneously during roll | One version at a time | Eliminates version-mixing bugs |
| **Pod failure tolerance** | PDB minAvailable: 1 (node drain won't kill last pod) | Same PDB, but across two slots | Maintenance safety |
| **Autoscaling** | Single metric (CPU) | Triple metric (CPU + memory + WebSocket) | Better scaling under WebSocket-heavy load |
| **Resource safety** | No quota — one workload can starve others | ResourceQuota + LimitRange | Noisy-neighbour prevention |
| **Zone resilience** | Single-zone risk | topologySpreadConstraints maxSkew=1 | Survives AZ failure |
| **Node resilience** | Pods may co-locate | podAntiAffinity weight=100 | Spread across nodes |
| **Spot node support** | No — default nodes only | Toleration for `spot` taint | Cost reduction |
| **TLS management** | Manual cert renewal | cert-manager auto-renew | Zero cert-expiry incidents |
| **Rate limiting** | Application-level or none | Ingress-level 100 rps / 20 conn | Edge protection before the app layer |
| **Network isolation** | No NetworkPolicy — pods communicate freely | Default-deny + explicit allow | Lateral movement prevention |
| **RBAC** | Default service account (cluster-wide) | Minimal Role (read-only configmaps/secrets) | Least privilege |
| **Security posture** | Default container settings | Non-root, dropped caps, seccomp | Reduced attack surface |
| **Observability** | No structured alerting | 6 alert rules covering error rate, latency, crashes, saturation | Proactive incident detection |

---

## 11. Future Optimisation Roadmap

The following optimisations are grounded in specific gaps identified in the current manifests.
They are ordered from most urgent (O1) to longer-term improvements (O10).

| # | Optimisation | Root Cause / Gap | Suggested Change |
|---|-------------|-----------------|-----------------|
| **O1** | **Fix init container — URGENT** | `command: ["sh", "-c", "alembic upgrade head"]` fails in Distroless images (no shell). Every pod startup crashes with `Init:CrashLoopBackOff`. | Replace init container with a pre-deploy Kubernetes **Job** that uses the development image tag (with shell and Alembic). See O7. |
| **O2** | Switch to Argo Rollouts or Flagger | HPA hardcodes `scaleTargetRef.name: facebook-clone-blue` — after promoting green, the HPA no longer scales the active slot. Script has no automatic health gate (error rate, latency). | Argo Rollouts replaces both Deployments with an `AnalysisTemplate` + canary/blue-green strategy with automatic rollback on metric breach. Flagger integrates with the existing NGINX Ingress. |
| **O3** | Vertical Pod Autoscaler (VPA) | CPU request=100m vs limit=1000m (10:1 ratio) causes CFS throttling under sustained load. The right request value is unknown without production data. | Deploy VPA in `recommendation` mode to observe actual CPU/memory usage patterns. Use VPA recommendations to right-size `requests` and reduce throttling. |
| **O4** | KEDA for WebSocket scaling | The `websocket_connections_active` custom metric requires deploying and configuring the Prometheus Adapter, which adds operational complexity (custom API registration, ConfigMap with PromQL mappings). | Replace the HPA custom metric with a **KEDA ScaledObject**. KEDA has a native `prometheus` scaler — point it at the PromQL expression and remove the Prometheus Adapter. |
| **O5** | Raise PDB to `minAvailable: 2` | Current `minAvailable: 1` allows Kubernetes to drain two pods simultaneously during a node upgrade when 3 replicas are running. With zone spread, losing 2 of 3 pods breaks zone-level redundancy. | Set `minAvailable: 2`. This ensures at least 2 pods remain during voluntary disruptions, matching the intent of zone spreading. |
| **O6** | Enable `readOnlyRootFilesystem: true` | Currently `false` because the app writes to `/app/uploads`. This prevents full filesystem hardening. | Mount `uploads` emptyDir at `/app/uploads` (already done). Change the app to write only to that mountPath, then enable `readOnlyRootFilesystem: true` in both deployment manifests and the init container. |
| **O7** | Separate DB migration Job | Migrations in initContainers block every pod restart. If a migration takes 10 minutes, all pods are stuck for 10 minutes. Parallel pod startups run migrations concurrently, risking lock contention. | Create a Kubernetes Job with `ttlSecondsAfterFinished: 600` run as a CI/CD pre-deploy step (or ArgoCD sync hook). The Job uses the dev image (with shell + Alembic) and runs before the Deployment rollout begins. |
| **O8** | Document resource quota sizing | ResourceQuota allows 50 pods; HPA max is 20 per slot. With 2 deployments × 20 = 40 pods, plus any Jobs, the 50-pod quota is appropriately sized. This is not wrong but is undocumented, causing confusion during capacity planning. | Add a comment to `resource-quota.yaml` explaining the sizing rationale. Consider setting quota to `pods: 45` to leave headroom for Jobs without allowing unbounded growth. |
| **O9** | Pin image tags to SHA digests | `kustomization.yaml` sets `newTag: latest`. In production, `latest` is mutable — the same tag can resolve to a different image layer at any time, making deploys non-deterministic. | CI/CD should resolve the image to its SHA digest and pass `newTag: sha256-<digest>` to Kustomize. This makes every deploy fully reproducible and auditable. |
| **O10** | Switch to DNS-01 ACME challenge | HTTP-01 requires Let's Encrypt to reach port 80 on the cluster's public IP. This fails in air-gapped environments, behind strict firewalls, and does not support wildcard certificates (`*.facebook-clone.example.com`). | Configure the cert-manager `ClusterIssuer` to use DNS-01 with a supported provider (Route53, Cloudflare, Google Cloud DNS). This also enables wildcard certificates for `*.api.facebook-clone.example.com`. |

### Priority Matrix

```
                    ┌──────────────────────────────────────────────┐
High Impact         │  O1 (init container crash — deploy blocker)  │
                    │  O2 (HPA target breaks after blue/green swap) │
                    ├──────────────────────────────────────────────┤
Medium Impact       │  O3 (VPA — CPU throttling under load)        │
                    │  O5 (PDB — disruption budget too low)         │
                    │  O7 (migration Job — safer than initContainer)│
                    ├──────────────────────────────────────────────┤
Lower Impact        │  O4 (KEDA — operational simplification)       │
(Long Term)         │  O6 (readOnlyRootFilesystem hardening)        │
                    │  O9 (image SHA pinning — reproducibility)     │
                    │  O10 (DNS-01 — wildcard certs, air-gap)       │
                    └──────────────────────────────────────────────┘
                         Fix Now           Fix Soon      Backlog
```

---

## 12. Verification / How to Apply

### 12.1 Apply the Full Production Stack

```bash
# Preview what kustomize will generate (dry run)
kubectl kustomize deploy/k8s/overlays/production/

# Apply base + production overlay
kubectl apply -k deploy/k8s/overlays/production/

# Verify all resources were created
kubectl get all -n production
kubectl get networkpolicy -n production
kubectl get ingress -n production
kubectl get hpa -n production
kubectl get pdb -n production
kubectl get clusterissuer letsencrypt-prod
```

### 12.2 Run a Blue/Green Deploy

```bash
# Deploy a new image to the inactive slot, wait for readiness, switch traffic
./deploy/scripts/blue-green-deploy.sh production ghcr.io/your-org/facebook-clone:v1.2.3 facebook-clone

# Monitor rollout in another terminal
watch kubectl get pods -n production -l app=facebook-clone

# Verify the active slot after the switch
kubectl get service facebook-clone -n production -o jsonpath='{.spec.selector.slot}'
```

### 12.3 Rollback

```bash
# Instant rollback: switch traffic back to blue
kubectl patch service facebook-clone -n production \
  -p '{"spec":{"selector":{"app":"facebook-clone","slot":"blue"}}}'

# Confirm
kubectl get service facebook-clone -n production -o jsonpath='{.spec.selector}'
```

### 12.4 Check HPA and Autoscaling Status

```bash
# Current HPA state (TARGETS column shows current vs target metric values)
kubectl get hpa -n production

# Detailed HPA events and scaling decisions
kubectl describe hpa facebook-clone-hpa -n production

# Manually scale a slot (bypass HPA temporarily)
kubectl scale deployment facebook-clone-blue -n production --replicas=5
```

### 12.5 Check Pod Distribution

```bash
# View pods with their node assignments
kubectl get pods -n production -l app=facebook-clone -o wide

# Verify zone spread
kubectl get pods -n production -l app=facebook-clone \
  -o custom-columns='NAME:.metadata.name,NODE:.spec.nodeName,ZONE:.metadata.labels.topology\.kubernetes\.io/zone'

# Check pod disruption budget status
kubectl get pdb -n production
```

### 12.6 Inspect TLS Certificate

```bash
# Check cert-manager Certificate resource
kubectl get certificate -n production

# Check the underlying Secret
kubectl get secret facebook-clone-tls -n production

# Describe for renewal timing and status
kubectl describe certificate -n production
```

### 12.7 Check Network Policies

```bash
# List all NetworkPolicy objects in production
kubectl get networkpolicy -n production

# Verify specific policies
kubectl describe networkpolicy default-deny-ingress -n production
kubectl describe networkpolicy allow-ingress-controller -n production
kubectl describe networkpolicy allow-db-egress -n production
```

### 12.8 Verify Resource Quota Usage

```bash
# Current namespace quota usage
kubectl describe resourcequota production-quota -n production

# LimitRange defaults
kubectl describe limitrange production-limits -n production
```

---

*See also:*
- [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) — Clean Architecture layers, data flow, component overview
- [`docs/RUNBOOK.md`](RUNBOOK.md) — Incident response, scaling procedures, common fixes
- [`docs/PODMAN_DISTROLESS.md`](PODMAN_DISTROLESS.md) — Distroless image migration (context for O1 and O6)
- [`docs/DATABASE.md`](DATABASE.md) — PostgreSQL schema, connection pooling, migration strategy
- [`deploy/k8s/`](../deploy/k8s/) — All Kubernetes manifests
- [`deploy/scripts/blue-green-deploy.sh`](../deploy/scripts/blue-green-deploy.sh) — Blue/green deploy script
