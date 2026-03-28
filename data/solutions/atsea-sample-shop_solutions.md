# DockForge — AtSea Shop Java Build Solutions
# All errors confirmed RESOLVED on 2026-04-03 (build success achieved)

---

## JAVA_001 — Outdated / Dead Base Images in Original Dockerfile

**Error:**
```
ERROR: failed to build: failed to solve: maven:3.6-eclipse-temurin-8: failed to resolve source metadata for docker.io/library/maven:3.6-eclipse-temurin-8: docker.io/library/maven:3.6-eclipse-temurin-8: not found
```
(Previously prscm-history-item:/home/vista/fake-thon/debugging/app/rust_dashboard_app?%7B%22repositoryId%22%3A%22scm1%22%2C%22historyItemId%22%3A%226af0bce36a5f06082ab29817f6197500a4af9ea0%22%2C%22historyItemDisplayId%22%3A%226af0bce%22%7Deceded by issues where `java:8-jdk-alpine` was completely dead/removed from Docker Hub).

**Root Cause:**
The original `Dockerfile` used base images that are either fully deprecated/removed from Docker Hub or incompatible with the legacy codebase:
1. `java:8-jdk-alpine` was deprecated and removed from Docker Hub in 2022.
2. `maven:latest` now ships with JDK 21+, which is fundamentally incompatible with the project's target Java version (1.8) and ancient Spring Boot 1.5.3 (from 2017).
3. Attempting to use `maven:3.6-eclipse-temurin-8` failed because the `eclipse-temurin` variant tags were only introduced to the Maven Docker library starting from the `3.8` series.
4. `node:latest` (Node 20+) breaks the older React frontend scripts due to OpenSSL legacy provider changes introduced in Node 17+.

**Fix:**
Re-engineered the entire `Dockerfile` stages to pin versions to the last compatible LTS releases for this era of software:

```dockerfile
# STAGE 1: Frontend (Pinned to Node 16 LTS to avoid OpenSSL issues)
FROM node:16-alpine AS storefront

# STAGE 2: App Server (Pinned to Maven 3.9 + Java 8)
# Switched from 3.6 to 3.9 as it's the LTS that formally supports eclipse-temurin-8
FROM maven:3.9-eclipse-temurin-8 AS appserver

# STAGE 3: Runtime (Modern replacement for the dead java:8-jdk-alpine image)
FROM eclipse-temurin:8-jre-alpine AS runtime
```

---

## JAVA_002 — UnknownHostException: database (PostgreSQL connection failure)

**Error:**
```
Caused by: java.net.UnknownHostException: database
...
Caused by: org.postgresql.util.PSQLException: The connection attempt failed.
...
ERROR 1 --- [main] o.s.boot.SpringApplication : Application startup failed
org.springframework.beans.factory.BeanCreationException: Error creating bean with name 'entityManagerFactory'
```

**Root Cause:**
The original `Dockerfile` had a default command setting the Spring profile to `postgres` (`CMD ["--spring.profiles.active=postgres"]`). The `application.yml` for this profile specifies a hardcoded JDBC URL: `jdbc:postgresql://database:5432/atsea`. 

In a standalone `docker run` scenario, there is no container/host named `database` on the network, causing a DNS resolution failure inside the JRE. The app requires a sidecar PostgreSQL container to function in this mode.

**Fix:**
Changed the default `CMD` in the `Dockerfile` to use the `local` profile, which utilizes an in-memory **H2 database**. This allows the container to run successfully in standalone mode without external dependencies.

```dockerfile
# Changed from postgres to local for standalone usability
CMD ["--spring.profiles.active=local"]
```

---

## Build Notes & Observations
- **NPM Warnings:** Expected and ignored. The React app is ancient and uses deeply deprecated dependencies (`querystring`, `uglify-js`, etc.). These trigger ~50 deprecation warnings but do not fail the build on Node 16.
- **Node Circular Dependency Warnings:** Minor warnings during the build (`Accessing non-existent property 'find' of module exports inside circular dependency`). These are benign artifacts of old scripts on modernized Node platforms.
- **Success:** The application compiled and exported successfully without requiring changes to the `pom.xml` or Java source code, strictly by establishing a period-accurate container build environment.
