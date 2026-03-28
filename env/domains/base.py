"""Abstract base for domain-specific environment hooks."""
from typing import Dict, Any, List
from abc import ABC, abstractmethod


class DomainBase(ABC):
    """Base class that all domain handlers inherit from."""

    @staticmethod
    @abstractmethod
    def pre_log_hook(state_data: Dict[str, Any]) -> None:
        """Called before log generation. Can mutate state_data in-place."""
        ...

    @staticmethod
    @abstractmethod
    def generate_domain_logs(state_files: Dict[str, str], check: Dict[str, Any]) -> str:
        """Generate a realistic domain-specific error string for a failing check."""
        ...
