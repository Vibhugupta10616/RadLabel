"""Write results JSON with provenance (git commit, seed, deployments, mapping version, fold)."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radlabel.config import get_settings

RESULTS_DIR = Path("artifacts/results")


def git_commit() -> str:
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout
        # outputs and docs don't make the code dirty (scripts write tracked results one after another)
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no", "--", ".",
                                ":(exclude)artifacts/results", ":(exclude)artifacts/tables", ":(exclude)docs"],
                               capture_output=True, text=True).stdout.strip()
        return sha.strip() + ("-dirty" if dirty else "")
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def provenance(fold: int | str | None, mapping_version: str = "v1", **extra: Any) -> dict[str, Any]:
    s = get_settings()
    return {
        "git_commit": git_commit(),
        "seed": s.seed,
        "llm_provider": s.llm_provider,
        "deployments": {
            "tier1": [s.azure_openai_deployment, s.azure_openai_deployment_version],
            "fallback": [s.azure_openai_fallback_deployment, s.azure_openai_fallback_deployment_version],
            "repair": [s.azure_openai_repair_deployment, s.azure_openai_repair_deployment_version],
            "cheap": [s.azure_openai_cheap_deployment, s.azure_openai_cheap_deployment_version],
        },
        "mapping_version": mapping_version,
        "fold": fold,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        **extra,
    }


def write_result(name: str, payload: dict[str, Any], fold: int | str | None = "oof",
                 mapping_version: str = "v1", **extra: Any) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    out = {"provenance": provenance(fold, mapping_version, **extra), "results": payload}
    path.write_text(json.dumps(out, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    return path
