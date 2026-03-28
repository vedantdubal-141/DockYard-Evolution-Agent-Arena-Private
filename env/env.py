from typing import Tuple, Dict, Any, Optional
import json
import os
import copy
from env.state import Observation, Action, Reward
from env.actions import apply_action
from env.logs import generate_logs
from env.reward import calculate_reward

from env.domains import java, rust

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenarios")

# Number of consecutive zero-reward steps before the hint is unlocked
HINT_THRESHOLD = 3
# When a hint was used, reward is capped at this value even if the agent fully solves
HINT_REWARD_CAP = 0.5
# If agent needed hint last task but solves this one alone, add this bonus
IMPROVEMENT_BONUS = 0.05


class DockForgeEnv:
    def __init__(self):
        self.scenario_files = []
        if os.path.exists(SCENARIOS_DIR):
            for root, _, files in os.walk(SCENARIOS_DIR):
                for f in files:
                    if f.endswith(".json"):
                        self.scenario_files.append(os.path.join(root, f))
        # Ensure deterministic ordering
        self.scenario_files.sort()

        self.current_scenario_idx = 0
        self.noise_level = 0.0  # 0 = deterministic (for evaluation)
        self.state_data = self._empty_state()
        self.previous_files = {}  # For destructive action detection
        # Track hint history across tasks for improvement bonus logic
        # key: task_idx, value: True if hint was used on that task
        self._hint_history: Dict[int, bool] = {}

        if self.scenario_files:
            self.reset()

    @staticmethod
    def _empty_state() -> Dict[str, Any]:
        return {
            "domain": "",
            "files": {},
            "last_log": "",
            "description": "",
            "reward": 0.0,
            "done": False,
            "step_count": 0,
            "solution_criteria": {},
            "sandbox_penalty": 0.0,
            # Hint mechanic
            "hint_text": "",          # populated from scenario JSON
            "hint_active": False,      # True once unlocked
            "hint_used": False,        # True if agent solved AFTER hint was shown
            "consecutive_zeros": 0,    # streak of steps with reward == 0.0
            "difficulty": "medium",    # difficulty level of the task
        }

    @staticmethod
    def _auto_hint(scenario_data: Dict[str, Any], domain: str) -> str:
        """
        Generate a targeted hint from the scenario's first check.
        Shown after HINT_THRESHOLD consecutive zero-reward builds.
        Gives direction without spelling out the full solution.
        """
        checks   = scenario_data.get("solution_criteria", {}).get("checks", [])
        files    = scenario_data.get("initial_files", {})
        if not checks:
            return "Inspect the build log carefully for the root cause."

        first_check = checks[0]
        target_file  = first_check.get("file", "unknown file")
        error_hint   = first_check.get("error_msg", "")
        snippet_hint = first_check.get("contains", "")

        domain_tip = ""
        if domain == "rust":
            domain_tip = "Check Cargo.toml dependencies and Dockerfile base image tags."
        elif domain == "java":
            domain_tip = "Check Dockerfile CMD, base image tags, and Spring profile settings."

        hint_threshold = 6 if scenario_data.get("difficulty") == "hard" else 3
        return (
            f"You have made {hint_threshold} build attempts with no progress.\n"
            f"Focus on: {target_file}\n"
            f"The build log is telling you: {error_hint}\n"
            f"{domain_tip}\n"
            f"Your fix should include something related to: '{snippet_hint[:60]}...'"
            if len(snippet_hint) > 60 else
            f"You have made {hint_threshold} build attempts with no progress.\n"
            f"Focus on: {target_file}\n"
            f"The build log is telling you: {error_hint}\n"
            f"{domain_tip}"
        )

    def state(self) -> Observation:
        description = self.state_data.get("description", "")
        # Append active hint to task description so agent sees it clearly
        if self.state_data.get("hint_active"):
            hint = self.state_data.get("hint_text", "")
            description = (
                f"{description}\n\n"
                "━━━ HINT UNLOCKED (max score capped at 0.50) ━━━\n"
                f"{hint}\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            )
        return Observation(
            files_content=self.state_data.get("files", {}),
            last_build_log=self.state_data.get("last_log", ""),
            task_description=description,
        )

    def reset(
        self,
        task_idx: Optional[int] = None,
        deterministic: bool = True,
    ) -> Observation:
        """
        Reset the environment to a new task.
        
        Args:
            task_idx: Index of the scenario to load. None = next in sequence.
            deterministic: If True, noise_level=0 (for evaluation runs).
        """
        if not self.scenario_files:
            return self.state()

        if task_idx is not None and 0 <= task_idx < len(self.scenario_files):
            self.current_scenario_idx = task_idx
        else:
            self.current_scenario_idx = (self.current_scenario_idx + 1) % len(
                self.scenario_files
            )

        self.noise_level = 0.0 if deterministic else 0.1

        scenario_path = self.scenario_files[self.current_scenario_idx]

        # Detect domain from path
        domain = "unknown"
        if "java" in scenario_path:
            domain = "java"
        elif "rust" in scenario_path:
            domain = "rust"

        with open(scenario_path, "r") as f:
            data = json.load(f)

        initial_files = copy.deepcopy(data.get("initial_files", {}))

        self.state_data = {
            "domain": domain,
            "files": initial_files,
            "last_log": data.get("initial_log", ""),
            "description": data.get("description", ""),
            "reward": 0.0,
            "done": False,
            "step_count": 0,
            "solution_criteria": data.get("solution_criteria", {}),
            "sandbox_penalty": 0.0,
            # Hint mechanic — load hint from scenario or auto-generate
            "hint_text": data.get("hint_text", self._auto_hint(data, domain)),
            "hint_active": False,
            "hint_used": False,
            "consecutive_zeros": 0,
            "difficulty": data.get("difficulty", "medium"),
        }
        self.previous_files = copy.deepcopy(initial_files)

        return self.state()

    def step(
        self, action: Action
    ) -> Tuple[Observation, Reward, bool, Dict[str, Any]]:
        self.state_data["step_count"] += 1

        # --- Apply action with sandbox check ---
        feedback, action_penalty = apply_action(action, self.state_data["files"])
        self.state_data["sandbox_penalty"] += action_penalty

        # --- Calculate reward with all penalties ---
        raw_reward = calculate_reward(
            state_files=self.state_data["files"],
            criteria=self.state_data["solution_criteria"],
            step_count=self.state_data["step_count"],
            previous_files=self.previous_files,
            action_file=action.file_to_edit,
        )

        if not action.run_build:
            reward_score = max(0.0, (raw_reward * 0.3) + self.state_data["sandbox_penalty"])
        else:
            # --- Domain pre-log hooks ---
            if self.state_data["domain"] == "java":
                java.pre_log_hook(self.state_data)
            elif self.state_data["domain"] == "rust":
                rust.pre_log_hook(self.state_data)

            # Apply sandbox penalty on top
            reward_score = max(0.0, raw_reward + self.state_data["sandbox_penalty"])

            # --- Hint mechanic: track zero-reward streak ---
            if reward_score == 0.0:
                self.state_data["consecutive_zeros"] += 1
            else:
                self.state_data["consecutive_zeros"] = 0

            # Unlock hint after HINT_THRESHOLD consecutive zero-reward builds
            hint_threshold = 6 if self.state_data.get("difficulty") in ("hard", "extra_hard") else 3
            if (
                not self.state_data["hint_active"]
                and self.state_data["consecutive_zeros"] >= hint_threshold
            ):
                self.state_data["hint_active"] = True
                hint_file = self.state_data["solution_criteria"].get("checks", [{}])[0].get("file", "?")
                print(
                    f"[HINT] unlocked after {hint_threshold} zero-reward builds "
                    f"| pointing at: {hint_file} "
                    f"| reward_cap={HINT_REWARD_CAP:.2f} from now on",
                    flush=True,
                )

            # If hint was active and agent just earned reward → first time: mark hint_used
            if self.state_data["hint_active"] and reward_score > 0.0 and not self.state_data["hint_used"]:
                self.state_data["hint_used"] = True
                print(
                    f"[HINT] agent succeeded after using hint "
                    f"| raw_reward={reward_score:.3f} "
                    f"| reward_reduced_to={HINT_REWARD_CAP:.2f}",
                    flush=True,
                )

            # Cap reward if agent needed the hint
            if self.state_data["hint_used"]:
                reward_score = max(0.0, min(reward_score - 0.1, HINT_REWARD_CAP))

            # --- Improvement bonus: solved WITHOUT hint, but last task needed one ---
            improvement_bonus = 0.0
            task_idx = self.current_scenario_idx
            prev_idx  = task_idx - 1
            solved_now = reward_score > 0.0 and not self.state_data["hint_used"]
            prev_used_hint = self._hint_history.get(prev_idx, False)

            if solved_now and prev_used_hint:
                improvement_bonus = IMPROVEMENT_BONUS
                reward_score = min(1.0, reward_score + improvement_bonus)
                print(
                    f"[HINT] prev_task_used_hint=true | solved_without_hint=true "
                    f"| improvement_bonus=+{improvement_bonus:.2f} "
                    f"| new_reward={reward_score:.3f}",
                    flush=True,
                )
            elif solved_now and not prev_used_hint and task_idx > 0:
                # Clean solve, no hint needed, no previous hint debt — just note it
                print(
                    f"[HINT] passed_without_hint=true | no_penalty | reward={reward_score:.3f}",
                    flush=True,
                )

            # Record hint outcome for this task once it completes
            if reward_score > 0.0 or self.state_data["step_count"] >= 15:
                self._hint_history[task_idx] = self.state_data["hint_used"]

            # --- Generate domain-specific logs ---
            build_log = generate_logs(
                state_files=self.state_data["files"],
                criteria=self.state_data["solution_criteria"],
                domain=self.state_data["domain"],
                noise_level=self.noise_level,
            )

            self.state_data["last_log"] = build_log
            self.state_data["done"] = "SUCCESS" in build_log
            feedback = f"Build executed. Reward: {reward_score:.3f}"
            if self.state_data["hint_used"]:
                feedback += f" (hint used | score capped at {HINT_REWARD_CAP})"
            if improvement_bonus > 0.0:
                feedback += f" (+{improvement_bonus:.2f} improvement bonus)"

        if not action.run_build:
            feedback = f"File edited (no build). Partial reward: {reward_score:.3f}"

        self.state_data["reward"] = reward_score
        # Snapshot files for next destructive-action comparison
        self.previous_files = copy.deepcopy(self.state_data["files"])

        obs = self.state()
        reward = Reward(score=self.state_data["reward"], feedback=feedback)

        # Hard cap to prevent infinite loops
        if self.state_data["step_count"] >= 15:
            self.state_data["done"] = True

        info = {
            "task_id": self.current_scenario_idx,
            "step": self.state_data["step_count"],
            "domain": self.state_data["domain"],
            "hint_active": self.state_data["hint_active"],
            "hint_used": self.state_data["hint_used"],
            "hint_history": dict(self._hint_history),
        }
        return obs, reward, self.state_data["done"], info
