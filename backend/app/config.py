"""Centralized, environment-backed application configuration."""
import os
from typing import Tuple

TACTICS: Tuple[str, ...] = ("urgency", "authority", "invoice", "credential")
RESPONSES: Tuple[str, ...] = ("ignore", "report", "click", "credentials")


def required_secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set before starting SecureTrain")
    return value


def benchmark_config() -> tuple[int, int, int]:
    return (int(os.environ.get("BENCHMARK_ROUNDS", "10")), int(os.environ.get("BENCHMARK_REPETITIONS", "40")), int(os.environ.get("BENCHMARK_SEED", "90210")))

