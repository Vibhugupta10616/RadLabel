"""Load a versioned mapping YAML and map expert codes to labels (data_prep / eval / training only)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from radlabel.labels import NO_FINDING

MAPPING_DIR = Path(__file__).resolve().parents[1] / "data" / "mapping"


@dataclass(frozen=True)
class Rule:
    head: str
    subs: frozenset[str] | None = None        # allowed first sub-headings ("" = none); None = any
    exclude_any_sub: frozenset[str] = frozenset()  # reject if any sub-heading is one of these
    site: str | None = None                   # "lung" | "pleura": site-checked rule (see YAML header)
    non_lung: frozenset[str] = frozenset()
    pleura: frozenset[str] = frozenset()

    def matches(self, code: str) -> bool:
        parts = parse_parts(code)
        first = parts[1] if len(parts) > 1 else ""
        if parts[0] != self.head or self.exclude_any_sub.intersection(parts[1:]):
            return False
        if self.site == "lung":  # first sub-heading `lung` wins; otherwise no non-lung/pleural sub-heading
            return first == "lung" or (
                (self.subs is None or first in self.subs) and not (self.non_lung | self.pleura).intersection(parts[1:]))
        if self.site == "pleura":
            return first != "lung" and bool(self.pleura.intersection(parts[1:]))
        return self.subs is None or first in self.subs

    def __str__(self) -> str:
        s = self.head + (f"/{{{','.join(sorted(self.subs))}}}" if self.subs is not None else "")
        s += f" [{self.site} site]" if self.site else ""
        return s + (f" except {','.join(sorted(self.exclude_any_sub))}" if self.exclude_any_sub else "")


@dataclass(frozen=True)
class Mapping:
    version: str
    no_finding_code: str
    other_label: str
    ignore_codes: frozenset[str]
    rules: dict[str, list[Rule]]

    def match(self, code: str) -> list[str]:
        return [lab for lab, rs in self.rules.items() if any(r.matches(code) for r in rs)]

    def map_codes(self, codes: list[str]) -> set[str]:
        if codes == [self.no_finding_code]:
            return {NO_FINDING}
        out: set[str] = set()
        for c in codes:
            head = parse_parts(c)[0]
            if head == self.no_finding_code or head in self.ignore_codes:
                continue
            out.update(self.match(c) or [self.other_label])
        return out


def expert_labels(codes: list[str], v1: Mapping, strict: Mapping) -> dict[str, list[str]]:
    """v1 labels; strict labels (SPEC §4.5: No Finding / Other Abnormality identical to v1, only the
    pathology labels use the strict rules); strict_excluded = v1-only pathology positives, which are
    left out of that label's strict scoring."""
    lab_v1 = v1.map_codes(codes)
    keep = {NO_FINDING, v1.other_label}
    path_strict = strict.map_codes(codes) - keep
    lab_strict = path_strict | (lab_v1 & keep)
    return {
        "v1": sorted(lab_v1),
        "strict": sorted(lab_strict),
        "strict_excluded": sorted((lab_v1 - keep) - path_strict),
    }


def parse_parts(code: str) -> list[str]:
    return [p.strip() for p in code.split("/")]


def _rule(r: Any, sites: dict[str, list[str]]) -> Rule:
    if isinstance(r, dict):
        subs = r.get("subs")
        return Rule(r["head"], None if subs is None else frozenset(subs), frozenset(r.get("exclude_any_sub", [])),
                    r.get("site"), frozenset(sites.get("non_lung", [])), frozenset(sites.get("pleura", [])))
    return Rule(r[0], None if len(r) == 1 else frozenset([r[1]]))


def load_mapping(version: str = "v1") -> Mapping:
    d = yaml.safe_load((MAPPING_DIR / f"mesh_to_labels_{version}.yaml").read_text(encoding="utf-8"))
    sites = d.get("sites", {})
    rules = {lab: [_rule(r, sites) for r in rs] for lab, rs in d["labels"].items()}
    return Mapping(d["version"], d["no_finding_code"], d["other_label"], frozenset(d["ignore_codes"]), rules)


def crosscheck_note() -> dict[str, Any]:
    d = yaml.safe_load((MAPPING_DIR / "mesh_to_labels_v1.yaml").read_text(encoding="utf-8"))
    return dict(d.get("crosscheck", {}))
