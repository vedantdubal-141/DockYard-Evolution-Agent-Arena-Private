"""Rust domain-specific log generation and validation hooks."""
import random
from typing import Dict, Any
from env.domains.base import DomainBase

# Realistic Docker/Cargo build preamble lines shown before any error.
# The agent must scan through these to find the actual failure.
_RUST_BUILD_PREAMBLE = [
    "[+] Building...",
    "#1 [internal] load build definition from rust_dashboard_app.Dockerfile",
    "#1 DONE 0.0s",
    "#2 [internal] load .dockerignore",
    "#2 DONE 0.0s",
    "#3 [internal] load metadata for docker.io/library/{base_image}",
]

_RUST_BUILDER_PREAMBLE = [
    "#4 [builder 1/5] FROM docker.io/library/{base_image}",
    "#5 [builder 2/5] RUN rustup target add wasm32-unknown-unknown",
    "#5 CACHED",
    "#6 [builder 3/5] WORKDIR /app",
    "#6 DONE 0.1s",
    "#7 [builder 4/5] COPY . .",
    "#7 DONE 0.4s",
    "#8 [builder 5/5] RUN cargo build --release",
    "#8 0.831 Updating crates.io index",
    "#8 4.217 Compiling proc-macro2 v1.0.70",
    "#8 5.103 Compiling unicode-ident v1.0.12",
    "#8 6.445 Compiling syn v2.0.39",
    "#8 9.230 Compiling serde_derive v1.0.193",
    "#8 11.102 Compiling serde v1.0.193",
    "#8 15.880 Compiling tokio v1.35.1",
    "#8 22.340 Compiling hyper v0.14.28",
    "#8 28.750 Compiling axum v0.6.20",
    "#8 34.100 Compiling dashboard-app v0.1.0 (/app)",
]

_RUST_WASM_PREAMBLE = [
    "    Updating crates.io index",
    "    Locking 127 packages to latest compatible versions",
    "      Adding getrandom v0.2.11",
    "      Adding getrandom v0.3.0",
    "      Adding wasm-bindgen v0.2.92",
    "    Compiling proc-macro2 v1.0.70",
    "    Compiling unicode-ident v1.0.12",
    "    Compiling getrandom v0.2.11",
    "    Compiling getrandom v0.3.0",
]

_CARGO_CACHE_PREAMBLE = [
    "[+] Building 0.3s (4/12)",
    " => [internal] load build definition from rust_dashboard_app.Dockerfile  0.0s",
    " => => transferring dockerfile: 512B                                      0.0s",
    " => [internal] load .dockerignore                                         0.0s",
    " => [internal] load metadata for docker.io/library/rust:1.75-slim-boo... 0.2s",
]


class RustDomain(DomainBase):

    @staticmethod
    def pre_log_hook(state_data: Dict[str, Any]) -> None:
        """Enrich state with Rust-specific context before log generation."""
        files = state_data.get("files", {})
        for path, content in files.items():
            if "Dockerfile" in path or ".Dockerfile" in path:
                if "rust:nightly" in content:
                    state_data.setdefault("rust_flags", {})["invalid_nightly_tag"] = True
                if "target/server/release" in content:
                    state_data.setdefault("rust_flags", {})["wrong_binary_path"] = True
            if path.endswith("Cargo.toml"):
                if "=0.2.92" in content:
                    state_data.setdefault("rust_flags", {})["wasm_bindgen_pinned"] = True

    @staticmethod
    def generate_domain_logs(state_files: Dict[str, str], check: Dict[str, Any]) -> str:
        """Generate realistic cargo/rustc/Docker error output with build preamble noise."""
        error_msg  = check.get("error_msg", "")
        error_lower = error_msg.lower()

        # --- Invalid nightly tag ---
        if "manifest" in error_lower or "nightly" in error_lower:
            base = "rust:nightly"
            preamble = "\n".join(_RUST_BUILD_PREAMBLE).format(base_image=base)
            return (
                f"{preamble}\n"
                "#3 ERROR 1.2s\n"
                "------\n"
                f" > [internal] load metadata for docker.io/library/{base}:\n"
                "------\n"
                f"ERROR: failed to pull manifest for docker.io/library/{base}\n"
                f"docker.io/library/{base}: not found\n"
                f"{error_msg}\n"
                "Hint: Check https://hub.docker.com/_/rust for valid tags.\n"
            )

        # --- getrandom / WASM entropy ---
        elif "getrandom" in error_lower or "wasm" in error_lower:
            preamble = "\n".join(_RUST_WASM_PREAMBLE)
            return (
                f"{preamble}\n"
                "    Compiling dashboard-app v0.1.0 (/app)\n"
                "error[E0554]: `#![feature]` may not be used on the stable release channel\n"
                "  --> getrandom/src/lib.rs:42:1\n"
                "   |\n"
                f"   = {error_msg}\n"
                "   = help: consider using the `js` or `wasm_js` feature\n"
                "\n"
                "For more information about this error, try `rustc --explain E0554`.\n"
                "error: could not compile `getrandom` (lib) due to 1 previous error\n"
            )

        # --- Build context (2B / cache) ---
        elif "cache" in error_lower or "context" in error_lower or "ignore" in error_lower:
            preamble = "\n".join(_CARGO_CACHE_PREAMBLE)
            size_str = "2.4GB" if "ignore" in error_lower else "2B"
            return (
                f"{preamble}\n"
                " => [builder 1/5] FROM docker.io/library/rust:1.75-slim-bookworm  0.0s\n"
                " => CACHED [builder 2/5] RUN rustup target add wasm32...           0.0s\n"
                " => CACHED [builder 3/5] WORKDIR /app                              0.0s\n"
                "------\n"
                " > [builder 4/5] COPY . .:\n"
                "------\n"
                f"ERROR: {error_msg}\n"
                f"Sending build context to Docker daemon  {size_str}\n"
            )

        # --- Wrong binary path ---
        elif "target" in error_lower or "binary" in error_lower:
            preamble = "\n".join(_RUST_BUILDER_PREAMBLE).format(base_image="rust:1.75-slim-bookworm")
            return (
                f"{preamble}\n"
                "#8 DONE 41.3s\n"
                "#9 [stage-2 1/3] FROM docker.io/library/debian:bookworm-slim\n"
                "#9 CACHED\n"
                "------\n"
                " > [stage-2 2/3] COPY --from=builder /app/target/server/release/dashboard-app /app/:\n"
                "------\n"
                f"ERROR: {error_msg}\n"
            )

        # --- wasm-bindgen version conflict ---
        elif "wasm-bindgen" in error_lower or "conflict" in error_lower:
            preamble = "\n".join(_RUST_WASM_PREAMBLE)
            return (
                f"{preamble}\n"
                "error: failed to select a version for `wasm-bindgen`.\n"
                "    ... required by package `getrandom v0.3.0`\n"
                f"  {error_msg}\n"
                "  failed to select a version for `wasm-bindgen` which could resolve this conflict\n"
            )

        else:
            return f"error: {error_msg}\n"


# Module-level convenience functions for backward compatibility
def pre_log_hook(state_data: Dict[str, Any]) -> None:
    RustDomain.pre_log_hook(state_data)

def generate_domain_logs(state_files: Dict[str, str], check: Dict[str, Any]) -> str:
    return RustDomain.generate_domain_logs(state_files, check)
