"""Java domain-specific log generation and validation hooks."""
from typing import Dict, Any
from env.domains.base import DomainBase

# Realistic Maven/Docker build preamble — agent must read through this noise
_JAVA_BUILD_PREAMBLE = [
    "[+] Building...",
    "#1 [internal] load build definition from Dockerfile",
    "#1 DONE 0.0s",
    "#2 [internal] load .dockerignore",
    "#2 DONE 0.0s",
    "#3 [internal] load metadata for docker.io/library/{base_image}",
]

_MAVEN_BUILD_PREAMBLE = [
    "#4 [appserver 1/5] FROM docker.io/library/maven:3.9-eclipse-temurin-8",
    "#4 DONE 0.0s",
    "#5 [appserver 2/5] WORKDIR /usr/src/atsea",
    "#5 DONE 0.1s",
    "#6 [appserver 3/5] COPY pom.xml .",
    "#6 DONE 0.2s",
    "#7 [appserver 4/5] RUN mvn -B dependency:resolve",
    "#7 0.831 [INFO] Scanning for projects...",
    "#7 1.002 [INFO]",
    "#7 1.003 [INFO] -------< com.docker.atseashop:atseashop-api >--------",
    "#7 1.004 [INFO] Building AtSea Shop 0.0.1-SNAPSHOT",
    "#7 1.005 [INFO] --------------------------------[ jar ]--------------------------------",
    "#7 3.217 [INFO] --- maven-dependency-plugin:2.8:resolve (default-cli) @ atseashop-api ---",
    "#7 5.100 [INFO] Resolving dependencies...",
    "#7 12.345 [INFO] BUILD SUCCESS",
    "#7 DONE 13.1s",
    "#8 [appserver 5/5] RUN mvn -B package -DskipTests",
    "#8 0.500 [INFO] Scanning for projects...",
    "#8 2.103 [INFO] Compiling 47 source files...",
    "#8 8.890 [INFO] Building jar: /usr/src/atsea/target/atseashop-api.0.0.1-SNAPSHOT.jar",
    "#8 9.100 [INFO] BUILD SUCCESS",
    "#8 DONE 9.8s",
]

_SPRING_STARTUP_PREAMBLE = [
    "  .   ____          _            __ _ _",
    " /\\\\ / ___'_ __ _ _(_)_ __  __ _ \\ \\ \\ \\",
    "( ( )\\___ | '_ | '_| | '_ \\/ _` | \\ \\ \\ \\",
    " \\\\/  ___)| |_)| | | | | || (_| |  ) ) ) )",
    "  '  |____| .__|_| |_|_| |_\\__, | / / / /",
    " =========|_|==============|___/=/_/_/_/",
    " :: Spring Boot ::       (v1.5.3.RELEASE)",
    "",
    "2026-04-03 10:15:30.123  INFO 1 --- [main] c.d.atseashop.AtseaShopApplication  : Starting AtseaShopApplication",
    "2026-04-03 10:15:30.508  INFO 1 --- [main] s.c.a.AnnotationConfigApplicationContext : Refreshing context",
    "2026-04-03 10:15:31.211  INFO 1 --- [main] o.s.b.f.s.DefaultListableBeanFactory     : Overriding bean definition",
    "2026-04-03 10:15:31.890  INFO 1 --- [main] o.s.j.d.DriverManagerDataSource          : Loaded JDBC driver: org.h2.Driver",
    "2026-04-03 10:15:32.004  INFO 1 --- [main] o.s.w.s.handler.SimpleUrlHandlerMapping  : Mapped URL path [/**] onto handler",
    "2026-04-03 10:15:32.340  INFO 1 --- [main] o.s.j.e.a.AnnotationMBeanExporter        : Registering beans for JMX exposure on startup",
    "2026-04-03 10:15:32.891  INFO 1 --- [main] o.e.j.server.AbstractConnector           : Started ServerConnector{HTTP/1.1}",
]

_NODE_BUILD_PREAMBLE = [
    "#3 [storefront 1/4] FROM docker.io/library/node:16-alpine",
    "#3 DONE 0.0s",
    "#4 [storefront 2/4] WORKDIR /usr/src/atsea/app/react-app",
    "#4 DONE 0.1s",
    "#5 [storefront 3/4] COPY react-app .",
    "#5 DONE 0.3s",
    "#6 [storefront 4/4] RUN npm install && npm run build",
    "#6 0.441 npm warn deprecated querystring@0.2.0: Use the `qs` module",
    "#6 0.762 npm warn deprecated @npmcli/move-file@1.1.2: This functionality has been moved to @npmcli/fs",
    "#6 2.103 added 1482 packages in 4.891s",
    "#6 4.550 > react-app@0.1.0 build",
    "#6 4.551 > react-scripts build",
    "#6 6.002 Creating an optimized production build...",
    "#6 18.330 Compiled successfully.",
    "#6 DONE 20.1s",
]


class JavaDomain(DomainBase):

    @staticmethod
    def pre_log_hook(state_data: Dict[str, Any]) -> None:
        """Enrich state with Java-specific context before log generation."""
        files = state_data.get("files", {})
        for path, content in files.items():
            if "Dockerfile" in path or ".Dockerfile" in path:
                if "java:8-jdk-alpine" in content:
                    state_data.setdefault("java_flags", {})["dead_base_image"] = True
                if "spring.profiles.active=postgres" in content:
                    state_data.setdefault("java_flags", {})["wrong_profile"] = True

    @staticmethod
    def generate_domain_logs(state_files: Dict[str, str], check: Dict[str, Any]) -> str:
        """Generate realistic Java/Maven/Spring Boot error output with build preamble."""
        error_msg   = check.get("error_msg", "")
        error_lower = error_msg.lower()

        # --- Dead base image / maven image not found ---
        if "maven" in error_lower or "eclipse-temurin" in error_lower or "not found" in error_lower:
            bad_image = "maven:3.6-eclipse-temurin-8"
            preamble  = "\n".join(_JAVA_BUILD_PREAMBLE).format(base_image=bad_image)
            return (
                f"{preamble}\n"
                "#3 ERROR 2.4s\n"
                "------\n"
                f" > [internal] load metadata for docker.io/library/{bad_image}:\n"
                "------\n"
                f"ERROR: failed to build: failed to solve: {error_msg}\n"
                "------\n"
                " > [internal] load metadata for docker.io/library/maven:\n"
                "------\n"
                "Hint: maven:3.6-eclipse-temurin-8 does not exist. Try maven:3.9-eclipse-temurin-8\n"
            )

        # --- UnknownHostException (database DNS not found) or Runtime crash ---
        elif "unknownhostexception" in error_lower or "database" in error_lower or "postgres" in error_lower or "crash" in error_lower:
            preamble = "\n".join(_SPRING_STARTUP_PREAMBLE)
            return (
                f"{preamble}\n"
                "2026-04-03 10:15:33.212  INFO 1 --- [main] o.s.orm.jpa.LocalContainerEntityManagerFactoryBean : Building JPA container EntityManagerFactory\n"
                "2026-04-03 10:15:33.456 ERROR 1 --- [main] o.s.boot.SpringApplication               : Application startup failed\n"
                "org.springframework.beans.factory.BeanCreationException: Error creating bean with name 'entityManagerFactory'\n"
                "    at org.springframework.beans.factory.support.AbstractAutowireCapableBeanFactory.instantiateBean\n"
                "    at org.springframework.beans.factory.support.AbstractAutowireCapableBeanFactory.instantiate\n"
                "    ... 12 common frames omitted\n"
                f"Caused by: {error_msg}\n"
                "Caused by: org.postgresql.util.PSQLException: The connection attempt failed.\n"
                "    at org.postgresql.core.v3.ConnectionFactoryImpl.openConnectionImpl\n"
                "    ... 8 common frames omitted\n"
            )

        # --- Node/OpenSSL issues (storefront stage) ---
        elif "node" in error_lower or "openssl" in error_lower:
            preamble = "\n".join(_NODE_BUILD_PREAMBLE)
            return (
                f"{preamble}\n"
                "------\n"
                " > [storefront 4/4] RUN npm install && npm run build:\n"
                "------\n"
                "npm ERR! code ERR_OSSL_EVP_UNSUPPORTED\n"
                "npm ERR! error:0308010C:digital envelope routines::unsupported\n"
                f"{error_msg}\n"
                "npm ERR! A complete log of this run can be found in: /root/.npm/_logs/\n"
            )

        # --- Wrong Spring profile / generic Java error ---
        else:
            maven_preamble = "\n".join(_MAVEN_BUILD_PREAMBLE)
            return (
                f"{maven_preamble}\n"
                f"BUILD ERROR: {error_msg}\n"
            )


# Module-level convenience functions for backward compatibility
def pre_log_hook(state_data: Dict[str, Any]) -> None:
    JavaDomain.pre_log_hook(state_data)

def generate_domain_logs(state_files: Dict[str, str], check: Dict[str, Any]) -> str:
    return JavaDomain.generate_domain_logs(state_files, check)
