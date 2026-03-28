# DockForge — Rust Dashboard Build Solutions
# All errors confirmed RESOLVED on 2026-04-03 (build success achieved)

---

## RUST_001 — Invalid Docker Base Image Tag

**Error:**
```
ERROR: failed to pull manifest for docker.io/library/rust:nightly
```

**Root Cause:**
`rust:nightly` is not a valid Docker Hub tag. The official `rust` image only provides stable version tags (e.g., `1.75`, `1.75-slim-bookworm`, `latest`). The nightly *toolchain* must be installed manually inside the container.

**Fix:**
```dockerfile
# WRONG:
FROM rust:nightly AS builder

# CORRECT: use stable image + install nightly via rustup
FROM rust:1.75-slim-bookworm AS builder
RUN rustup default nightly && \
    rustup target add wasm32-unknown-unknown
```

---

## RUST_002 — getrandom 0.2.x: No WASM Entropy Backend

**Error:**
```
error: target `wasm32-unknown-unknown` is not supported by default,
you may need to enable the "js" feature
--> getrandom-0.2.x/src/lib.rs
```

**Root Cause:**
`getrandom` 0.2.x cannot generate random numbers on `wasm32-unknown-unknown` by default because the browser has no native OS entropy. The `js` feature must be explicitly enabled to delegate to browser Web APIs (`crypto.getRandomValues`).

**Fix — `Cargo.toml`:**
```toml
[dependencies]
getrandom = { version = "0.2", features = ["js"] }
```

---

## RUST_003 — Docker Cache Hiding File Changes

**Error:**
Same getrandom error repeated even after RUST_002 fix was applied.

**Root Cause:**
Docker cached the `COPY app/rust_dashboard_app .` layer from a previous build run. New files (`.cargo/config.toml`) and updated `Cargo.toml` were never picked up inside the container — Docker was serving stale cached layers.

**Fix — `scripts/deploy.sh`:**
```bash
# Add --no-cache to force full rebuild and pick up all file changes
# Use $BASE_DIR (absolute path) as build context instead of `.` (relative, unreliable)
docker build --no-cache -t rust-dashboard-debug -f "$DOCKERFILE" "$BASE_DIR" 2>&1 | tee -a "$LOG_FILE"
```

---

## RUST_004 — getrandom 0.3.x: Missing wasm_js Feature (API Change)

**Error:**
```
error: The "wasm_js" backend requires the `wasm_js` feature for `getrandom`
--> getrandom-0.3.4/src/backends.rs:40
```

**Root Cause:**
`uuid v1.16.0` (resolved from `uuid = "1.9.1"` after Cargo.lock deletion) pulls `getrandom` 0.3.x as a transitive dependency. The 0.3.x API changed completely from 0.2.x:

| Version | Cargo Feature | Rustflag cfg |
|---------|--------------|--------------|
| 0.2.x   | `features = ["js"]` | not needed |
| 0.3.x   | `features = ["wasm_js"]` | `--cfg getrandom_backend="wasm_js"` |

Both the rustflag AND the cargo feature are required simultaneously for 0.3.x.

**Fix 1 — `.cargo/config.toml` (created in app root):**
```toml
[target.wasm32-unknown-unknown]
rustflags = ["--cfg", "getrandom_backend=\"wasm_js\""]
# No hardcoded jobs= — use CARGO_BUILD_JOBS=$(nproc) in Dockerfile for dynamic core usage
```

**Fix 2 — `Cargo.toml` (add alongside 0.2.x entry):**
```toml
[dependencies]
getrandom = { version = "0.2", features = ["js"] }
# getrandom 0.3.x pulled by uuid v1.16.0+; needs wasm_js feature for WASM.
# Alias avoids key conflict with 0.2.x. Feature unification propagates wasm_js
# to all transitive users of getrandom 0.3.x in the dependency graph.
# Safe globally: getrandom internally gates wasm-bindgen/js-sys behind target_arch=wasm32.
getrandom-wasm3 = { package = "getrandom", version = "0.3", features = ["wasm_js"] }
```

---

## RUST_005 — wasm-bindgen Version Conflict (Exact Pin vs getrandom 0.3.x)

**Error:**
```
error: failed to select a version for `wasm-bindgen`
  ... required by package `getrandom v0.3.0` → requires `^0.2.98`
  ... which satisfies dependency `wasm-bindgen = "=0.2.92"` of `dashboard-app`
  failed to select a version for `wasm-bindgen` which could resolve this conflict
```

**Root Cause:**
`Cargo.toml` had an exact pin `wasm-bindgen = "=0.2.92"` (4-year-old exact pin from the original project). `getrandom` 0.3.x requires `wasm-bindgen >= 0.2.98`. Cargo's resolver could not satisfy both constraints simultaneously.

**Fix — `Cargo.toml`:**
```toml
# WRONG: exact pin incompatible with getrandom 0.3.x
wasm-bindgen = "=0.2.92"

# CORRECT: loosen to allow >= 0.2.98
wasm-bindgen = "^0.2.98"  # was =0.2.92; getrandom 0.3.x requires >= 0.2.98
```

---

## RUST_006 — Docker Build Context Wrong (2B context, COPY fails)

**Error:**
```
ERROR: failed to build: failed to solve: failed to compute cache key:
failed to calculate checksum of ref: "/app/rust_dashboard_app": not found
```
Build context was only `2B` — Docker daemon received an empty context.

**Root Cause:**
The `docker build` command used `.` (relative CWD) as the build context. When the script was invoked from certain paths or terminal states, `.` resolved incorrectly and Docker sent an almost-empty context (only 2B) to the daemon.

**Fix — `scripts/deploy.sh`:**
```bash
# Use explicit absolute path $BASE_DIR instead of relative `.`
docker build --no-cache -t rust-dashboard-debug -f "$DOCKERFILE" "$BASE_DIR" 2>&1 | tee -a "$LOG_FILE"
```

---

## RUST_007 — Wrong Binary Output Path in Export Stage

**Error:**
```
ERROR: failed to build: failed to solve: failed to compute cache key:
"/app/target/server/release/dashboard-app": not found
```

**Root Cause:**
The Dockerfile export stage assumed `cargo leptos` outputs the server binary at `target/server/release/`. In practice `cargo leptos build --release` with `--features ssr` places the binary at `target/release/dashboard-app` (standard Cargo release output directory). `target/server/` does not exist.

**Fix — `rust_dashboard_app.Dockerfile`:**
```dockerfile
# WRONG:
COPY --from=builder /app/target/server/release/dashboard-app /app/

# CORRECT:
COPY --from=builder /app/target/release/dashboard-app /app/
```

---

## Performance Tip — Dynamic CPU Core Usage

**Context:**
Rust compilation is CPU-bound and single-threaded during linking. On a multi-core machine the compile job count should max out available cores dynamically.

**Fix — `rust_dashboard_app.Dockerfile`:**
```dockerfile
# CARGO_BUILD_JOBS=$(nproc) detects available cores at container build time
# Works on any machine: 8-core CI runner or 32-thread workstation
RUN rm -f Cargo.lock && CARGO_BUILD_JOBS=$(nproc) cargo leptos build --release
```

---

## Final Build Config Summary

| File | Change |
|------|--------|
| `rust_dashboard_app.Dockerfile` | Base image: `rust:1.75-slim-bookworm` + manual nightly |
| `rust_dashboard_app.Dockerfile` | Build context: `$BASE_DIR` (absolute), `--no-cache` |
| `rust_dashboard_app.Dockerfile` | Binary path: `target/release/dashboard-app` |
| `rust_dashboard_app.Dockerfile` | Dynamic jobs: `CARGO_BUILD_JOBS=$(nproc)` |
| `Cargo.toml` | `getrandom 0.2.x`: `features = ["js"]` |
| `Cargo.toml` | `getrandom 0.3.x`: aliased dep with `features = ["wasm_js"]` |
| `Cargo.toml` | `wasm-bindgen`: loosened from `=0.2.92` → `^0.2.98` |
| `.cargo/config.toml` | WASM rustflag: `getrandom_backend="wasm_js"` |
| `scripts/deploy.sh` | `$BASE_DIR` context, `--no-cache`, `tee -a` (append logs) |
