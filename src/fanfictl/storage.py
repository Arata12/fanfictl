from __future__ import annotations

import json
import re
from pathlib import Path

from fanfictl.models import Checkpoint, Work, WorkKind


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"[-\s]+", "-", value)
    return value.strip("-") or "untitled"


def work_output_dir(base_dir: Path, work: Work) -> Path:
    title = work.original_title
    prefix = "novel" if work.kind == WorkKind.NOVEL else "series"
    return base_dir / f"{prefix}-{work.pixiv_id}-{slugify(title)}"


def ensure_work_dirs(base_dir: Path, work: Work) -> Path:
    root = work_output_dir(base_dir, work)
    (root / "chapters").mkdir(parents=True, exist_ok=True)
    return root


def save_metadata(root: Path, work: Work) -> None:
    (root / "metadata.json").write_text(
        work.model_dump_json(indent=2), encoding="utf-8"
    )


def save_checkpoint(root: Path, checkpoint: Checkpoint) -> None:
    (root / "checkpoint.json").write_text(
        checkpoint.model_dump_json(indent=2), encoding="utf-8"
    )


def load_checkpoint(root: Path) -> Checkpoint | None:
    path = root / "checkpoint.json"
    if not path.exists():
        return None
    return Checkpoint.model_validate(json.loads(path.read_text(encoding="utf-8")))
