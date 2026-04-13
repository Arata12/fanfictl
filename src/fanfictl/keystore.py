from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from fanfictl.config import Settings
from fanfictl.storage import atomic_write_text


def key_id_for(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def mask_key(value: str) -> str:
    if len(value) <= 10:
        return "*" * len(value)
    return f"{value[:6]}…{value[-4:]}"


class StoredAPIKey(BaseModel):
    key: str
    added_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds")
    )


@dataclass
class RuntimeAPIKey:
    id: str
    key: str
    source: str
    is_default: bool


@dataclass
class APIKeySummary:
    id: str
    source: str
    masked: str
    is_default: bool
    added_at: str | None


class APIKeyStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.output_dir / ".api_keys.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def runtime_keys(self) -> list[RuntimeAPIKey]:
        keys: list[RuntimeAPIKey] = []
        seen: set[str] = set()

        if self.settings.gemini_api_key:
            key_id = key_id_for(self.settings.gemini_api_key)
            keys.append(
                RuntimeAPIKey(
                    id=key_id,
                    key=self.settings.gemini_api_key,
                    source="env",
                    is_default=True,
                )
            )
            seen.add(key_id)

        for item in self._load_items():
            key_id = key_id_for(item.key)
            if key_id in seen:
                continue
            keys.append(
                RuntimeAPIKey(
                    id=key_id,
                    key=item.key,
                    source="stored",
                    is_default=False,
                )
            )
            seen.add(key_id)

        return keys

    def list_keys(self) -> list[APIKeySummary]:
        summaries: list[APIKeySummary] = []
        stored_map = {key_id_for(item.key): item for item in self._load_items()}
        for item in self.runtime_keys():
            stored = stored_map.get(item.id)
            summaries.append(
                APIKeySummary(
                    id=item.id,
                    source=item.source,
                    masked=mask_key(item.key),
                    is_default=item.is_default,
                    added_at=stored.added_at if stored else None,
                )
            )
        return summaries

    def add_key(self, raw_key: str) -> None:
        value = raw_key.strip()
        if not value:
            raise ValueError("API key cannot be empty")

        items = self._load_items()
        candidate_id = key_id_for(value)
        if self.settings.gemini_api_key and candidate_id == key_id_for(
            self.settings.gemini_api_key
        ):
            return
        if any(key_id_for(item.key) == candidate_id for item in items):
            return
        items.append(StoredAPIKey(key=value))
        self._save_items(items)

    def remove_key(self, key_id: str) -> None:
        items = [item for item in self._load_items() if key_id_for(item.key) != key_id]
        self._save_items(items)

    def _load_items(self) -> list[StoredAPIKey]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        return [StoredAPIKey.model_validate(item) for item in payload]

    def _save_items(self, items: list[StoredAPIKey]) -> None:
        atomic_write_text(
            self.path, json.dumps([item.model_dump() for item in items], indent=2)
        )
