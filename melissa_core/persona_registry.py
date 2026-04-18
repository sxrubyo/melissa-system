from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml
except Exception:  # pragma: no cover - fallback for environments without PyYAML
    yaml = None


@dataclass
class PersonaProfile:
    key: str
    identity: str
    opening_style: str = "natural"
    capabilities: List[str] = field(default_factory=list)
    first_turn_variants: List[str] = field(default_factory=list)
    identity_probe_variants: List[str] = field(default_factory=list)
    contextual_followups: Dict[str, str] = field(default_factory=dict)
    question_style: str = "natural"
    sales_style: str = "natural"
    objection_style: str = "natural"
    followup_style: str = "natural"
    humor_policy: str = "light"
    warmth_range: List[float] = field(default_factory=lambda: [0.45, 0.8])
    forbidden_patterns: List[str] = field(default_factory=list)
    channel_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


class PersonaRegistry:
    def __init__(self, root_dir: str | Path):
        self.root_dir = Path(root_dir)
        self._cache: Dict[str, PersonaProfile] = {}
        self._files: Dict[str, Path] = {}
        self._load()

    def _load(self) -> None:
        if not self.root_dir.exists():
            return
        for path in sorted(self.root_dir.glob("*.yaml")):
            profile = self._load_file(path)
            if profile:
                self._cache[profile.key] = profile
                self._files[profile.key] = path

    def _load_file(self, path: Path) -> Optional[PersonaProfile]:
        data = self._read_yaml(path)
        if not isinstance(data, dict):
            return None
        key = str(data.get("key") or path.stem).strip()
        if not key:
            return None
        identity = str(data.get("identity") or "Melissa").strip()
        return PersonaProfile(
            key=key,
            identity=identity,
            opening_style=str(data.get("opening_style") or "natural"),
            capabilities=self._as_list(data.get("capabilities")),
            first_turn_variants=self._as_list(data.get("first_turn_variants")),
            identity_probe_variants=self._as_list(data.get("identity_probe_variants")),
            contextual_followups=self._as_dict(data.get("contextual_followups")),
            question_style=str(data.get("question_style") or "natural"),
            sales_style=str(data.get("sales_style") or "natural"),
            objection_style=str(data.get("objection_style") or "natural"),
            followup_style=str(data.get("followup_style") or "natural"),
            humor_policy=str(data.get("humor_policy") or "light"),
            warmth_range=self._as_float_list(data.get("warmth_range"), default=[0.45, 0.8]),
            forbidden_patterns=self._as_list(data.get("forbidden_patterns")),
            channel_overrides=self._as_dict(data.get("channel_overrides")),
            raw=data,
        )

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if yaml is not None:
            loaded = yaml.safe_load(text)
            return loaded or {}
        return self._fallback_parse(text)

    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        current_key = None
        list_key = None
        dict_key = None
        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("- ") and list_key:
                data.setdefault(list_key, []).append(stripped[2:].strip().strip('"'))
                continue
            if ":" in stripped:
                key, value = stripped.split(":", 1)
                key = key.strip()
                value = value.strip()
                current_key = key
                list_key = None
                dict_key = None
                if not value:
                    data[key] = []
                    list_key = key
                else:
                    data[key] = value.strip().strip('"')
        return data

    def _as_list(self, value: Any) -> List[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value is None:
            return []
        if isinstance(value, str):
            raw = value.strip()
            return [raw] if raw else []
        return [str(value).strip()]

    def _as_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        return {}

    def _as_float_list(self, value: Any, default: List[float]) -> List[float]:
        if isinstance(value, list) and len(value) >= 2:
            try:
                return [float(value[0]), float(value[1])]
            except Exception:
                return default
        return default

    def list_keys(self) -> List[str]:
        return sorted(self._cache.keys())

    def get(self, key: str) -> Optional[PersonaProfile]:
        if not key:
            return None
        normalized = key.strip()
        if normalized in self._cache:
            return self._cache[normalized]
        return self._cache.get("default")

    def resolve_for_clinic(self, clinic: Dict[str, Any]) -> PersonaProfile:
        if not self._cache:
            return PersonaProfile(key="default", identity="Melissa")
        for candidate in (
            clinic.get("persona_key"),
            clinic.get("sector"),
            clinic.get("style_key"),
            clinic.get("channel"),
        ):
            profile = self.get(str(candidate or "").strip())
            if profile:
                return profile
        return self._cache.get("default") or next(iter(self._cache.values()))

