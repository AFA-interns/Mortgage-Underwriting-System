"""Loaders for labeled datasets and precomputed prediction files (JSON)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.evaluation.schemas import LabeledCase
from app.models.decision import DecisionResult


def _read_json(path: Path | str) -> Any:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def _extract_list(payload: Any, keys: tuple[str, ...], source: Path | str) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in keys:
            if isinstance(payload.get(key), list):
                return payload[key]
    raise ValueError(
        f"{source}: expected a JSON list or an object with one of the keys {keys}"
    )


def load_labeled_cases(path: Path | str) -> list[LabeledCase]:
    """Load labeled cases from a JSON file (bare list or {"cases": [...]})."""
    raw_cases = _extract_list(_read_json(path), ("cases", "labeled_cases"), path)
    cases: list[LabeledCase] = []
    for index, item in enumerate(raw_cases):
        try:
            cases.append(LabeledCase.model_validate(item))
        except ValidationError as exc:
            app_id = item.get("application_id", "?") if isinstance(item, dict) else "?"
            raise ValueError(
                f"{path}: invalid labeled case at index {index} "
                f"(application_id={app_id!r}): {exc}"
            ) from exc
    if not cases:
        raise ValueError(f"{path}: no labeled cases found")
    return cases


def load_predictions(path: Path | str) -> dict[str, DecisionResult]:
    """Load precomputed decisions from JSON (bare list or {"predictions": [...]})."""
    raw = _extract_list(_read_json(path), ("predictions", "decisions"), path)
    predictions: dict[str, DecisionResult] = {}
    for index, item in enumerate(raw):
        try:
            decision = DecisionResult.model_validate(item)
        except ValidationError as exc:
            raise ValueError(
                f"{path}: invalid prediction at index {index}: {exc}"
            ) from exc
        predictions[decision.application_id] = decision
    if not predictions:
        raise ValueError(f"{path}: no predictions found")
    return predictions
