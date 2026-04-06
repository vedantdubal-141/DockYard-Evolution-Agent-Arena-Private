---
title: DockForge OpenEnv
emoji: 🐳
colorFrom: blue
colorTo: purple
sdk: docker
sdk_version: "4.15.0"
python_version: "3.11"
app_file: runner/server.py
pinned: false
tags:
- openenv
- docker
- devops
- rust
- java
- hackathon
- agent
- llm-evaluation
short_description: AI agent env for Docker/build config debugging
---

# DockForge OpenEnv: DevOps Debugging Environment

A real-world AI agent environment where LLMs must debug broken Docker and build configurations. Submitted to the Meta PyTorch OpenEnv Hackathon.

---

## What Is This?

DockForge OpenEnv simulates genuine DevOps debugging scenarios that the developers encountered while building the original DockForge project. Instead of games or toy problems, agents must fix:

- Deprecated Docker base images
- WASM dependency conflicts
- Spring Boot profile misconfigurations
- Docker build context issues

---

## Project Structure

```
debugging/
|
|-- env/                        # Core environment engine
|   |-- env.py                  # step() / reset() / state() orchestrator
|   |-- state.py                # Typed Observation, Action, Reward models
|   |-- reward.py               # Partial reward calculator with penalties
|   |-- actions.py              # Sandbox validation for file edits
|   |-- logs.py                 # Realistic log generation
|   |-- domains/
|       |-- java.py             # Java/Spring/Maven log patterns
|       |-- rust.py             # Rust/Cargo/WASM log patterns
|       |-- base.py             # Abstract base class
|
|-- scenarios/                  # 7 graded tasks
|   |-- java/
|   |   |-- easy.json           # Dead base images
|   |   |-- medium.json         # Spring profile + H2 scope
|   |   |-- hard.json           # Cascading failures (all of above)
|   |-- rust/
|       |-- easy.json           # Invalid rust:nightly tag
|       |-- medium.json         # Build context + binary path
|       |-- hard.json           # getrandom 0.2/0.3 WASM conflict
|       |-- extra_hard.json     # Full WASM cascade (5-step gating)
|
|-- runner/
|   |-- server.py               # FastAPI for Hugging Face Spaces
|   |-- run_env.py              # Interactive human playtest
|
|-- agents/                     # Baseline test agents
|   |-- random_agent.py         # Chaos baseline (scores ~0)
|   |-- heuristic_agent.py      # Rule-based baseline
|   |-- lm_studio_agent.py      # Local LLM development
|
|-- inference.py                # Root inference script (REQUIRED)
|-- openenv.yaml                 # OpenEnv metadata
|-- Dockerfile                   # Container for HF Spaces
|-- tools/
|   |-- validate_scenario.py    # Pre-submission validator
```

---

## The Story: How Qwen 3.5 35B A3B Changed Everything

### Early Models: Single-File Thinkers

Initial testing with smaller models (Mistral 3B, Qwen 3 4B) revealed a critical limitation: these models could only edit one file per step. When faced with tasks requiring multiple coordinated fixes (like Rust Hard with its 5-step dependency chain), they would oscillate between files without making progress.

Example from Qwen 3 4B on R-3 Hard:
```
Step 1: edit(Cargo.toml)      → 0.30
Step 2: edit(.cargo/config.toml) → 0.30  (lost Cargo.toml progress)
Step 3: edit(Cargo.toml)      → 0.30
... repeated for 10 steps ...
Final score: 0.30 (failed)
```

### The Breakthrough: Qwen 3.5 35B A3B Apex

When we tested the **Qwen 3.5 35B A3B Apex** model, something different happened. Despite being a MoE model (only 3B parameters active per token), it demonstrated **Multi-Action capability**:

```
Step 1: The model read the task description, identified ALL 4 required fixes
        - js feature for getrandom 0.2
        - wasm-bindgen version update
        - rustflag configuration
        - getrandom-wasm3 alias for transitive dep
        
Step 2: Applied Cargo.toml fixes + .cargo/config.toml in one pass
Final score: 0.99 / 2 steps
```

This was the first model to solve Rust Hard in 2 steps. The same model also solved Java Hard in 2 steps (compared to 4 steps with other models).

### Consequence: Extra Hard Creation

The success with 35B Apex revealed that our "Hard" task was no longer hard for capable models. We created **Rust Extra Hard** to preserve the challenge:

- Added 5th check: deploy.sh fix (context problem)
- Required 5 files to be edited in correct order
- Maintains gating chain: each check requires the previous to pass

### Thermal Efficiency

The MoE architecture kept temperatures low:
- 8B "Thinking" model: 95°C (thermal throttle risk)
- 35B A3B Apex: 70-75°C (stable)

This made the 35B A3B the "Gold Standard" for our evaluation pipeline.

---

## Task Overview

| Task | Difficulty | Domain | Core Problem | Expected Score (35B) |
|------|------------|--------|--------------|---------------------|
| J-1 Easy | Easy | Java/Docker | Dead base images (java:8, maven:3.6) | 0.99 |
| J-2 Medium | Medium | Java/Spring | Wrong Spring profile + missing H2 scope | 0.99 |
| J-3 Hard | Hard | Java/Docker/Node | Cascading: base images + profile + multi-file | 0.99 |
| R-1 Easy | Easy | Rust/Docker | Invalid rust:nightly tag | 0.99 |
| R-2 Medium | Medium | Rust/Docker | Wrong binary path + missing .dockerignore | 0.98 |
| R-3 Hard | Hard | Rust/WASM | getrandom 0.2/0.3 transitive conflict | 0.99 |
| R-4 Extra Hard | Extra Hard | Rust/WASM/Docker | Full cascade: context + WASM + deps | 0.00-0.50 |

### Order-Dependent Gating

Rust Hard and Extra Hard use "requires" chains - a check only scores if its prerequisite is already satisfied:

```
check 1: Cargo.toml has "js" feature          → 0.10 points
check 2: Cargo.toml has "^0.2.98"             → 0.15 points (requires check 1)
check 3: .cargo/config.toml has rustflags    → 0.20 points (requires check 2)
check 4: Cargo.toml has getrandom-wasm3      → 0.40 points (requires check 3)
```

This prevents "brute force" approaches where an agent randomly edits files hoping for points.

---

## Reward System

### Partial Progress Signals
- Each check in solution_criteria awards partial points
- Total points sum to 1.0 across all checks

### Penalties
- Step efficiency: -0.02 per step taken
- Destructive action: -0.15 if a previously-passing check now fails

### Hint System
- Unlocks after 3 consecutive zero-reward builds
- Points capped at 0.50 if agent uses the hint

### Improvement Bonus
- +0.05 if agent needed hint on previous task but solves current one independently

---

## Setup & Usage

### 1. Install Dependencies
```bash
cd debugging
python -m venv .venv
.venv/bin/pip install pydantic fastapi uvicorn openai requests
```

### 2. Run Validation (Pre-Submission)
```bash
.venv/bin/python tools/validate_scenario.py
```
All 7 scenarios must pass.

### 3. Run Inference

#### With LM Studio (Local)
1. Load model in LM Studio → Start Server (port 1234)
2. Run:
```bash
export OPENAI_API_KEY="lm-studio"
export API_BASE_URL="http://127.0.0.1:1234/v1"
export MODEL_NAME="qwen3.5-35b-a3b-apex-i"
.venv/bin/python inference.py
```

#### With Hugging Face Endpoint
```bash
export HF_TOKEN="your-hf-token"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
.venv/bin/python inference.py
```

### 4. Interactive Playtest
```bash
.venv/bin/python runner/run_env.py --list     # List all tasks
.venv/bin/python runner/run_env.py --task 4   # Play Rust Easy
```

---

## Docker Deployment

### Build
```bash
docker build -t dockforge .
```

### Run
```bash
docker run -p 7860:7860 dockforge
```

The server exposes port 7860 for Hugging Face Spaces.

---

## Inference Output Format

The script outputs strict STDOUT format required by the hackathon:

```
[START] task=J-1 (easy) env=dockforge model=qwen3.5-35b-a3b-apex-i
[STEP] step=1 action=edit('app/atsea-shop.Dockerfile',run_build=True) reward=0.99 done=true error=null
[END] success=true steps=1 score=0.99 rewards=0.99 prompt_tokens=388 completion_tokens=507 reasoning_tokens=0 total_tokens=895
```

---

## Key Innovations

1. **Deterministic Log Simulation**: Instead of running real Docker/Cargo builds (which would OOM on 8GB VMs), we simulate the exact log output patterns. This guarantees consistency.

2. **Order-Dependent Gating**: The "requires" chain in solution_criteria prevents trivial point-farming and forces genuine understanding.

3. **Multi-Action Support**: The environment handles cases where capable models apply multiple file edits in a single step.

4. **Session Isolation**: Thread-safe server architecture prevents state corruption during concurrent judge evaluations.

---

## License

MIT
