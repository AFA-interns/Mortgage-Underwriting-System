"""Report generation service — exports report as structured JSON."""
from __future__ import annotations

from typing import Any

from app.models.decision import UnderwritingReport


def export_report_json(report: UnderwritingReport) -> dict[str, Any]:
    """Export underwriting report as serializable dict."""
    return report.model_dump(mode="json")
