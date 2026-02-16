"""Export leads to CSV or JSON."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from src.database.connection import get_session
from src.database.models import Lead

logger = logging.getLogger(__name__)


def export_leads(
    format: str = "csv",
    output_dir: str = "exports",
    state: str = None,
    category: str = None,
    min_quality: int = 0,
    enriched_only: bool = False,
) -> str:
    """
    Export leads to file.

    Returns the output file path.
    """
    session = get_session()
    query = session.query(Lead)

    if state:
        query = query.filter(Lead.state == state.upper())
    if category:
        from sqlalchemy import func
        query = query.filter(func.lower(Lead.category) == category.lower())
    if min_quality > 0:
        query = query.filter(Lead.quality_score >= min_quality)
    if enriched_only:
        query = query.filter(Lead.is_enriched == True)

    leads = query.all()
    session.close()

    if not leads:
        logger.warning("No leads found matching export criteria")
        return ""

    # Convert to list of dicts
    records = []
    for lead in leads:
        record = {c.name: getattr(lead, c.name) for c in lead.__table__.columns}
        # Serialize complex types
        if record.get("tech_stack"):
            record["tech_stack"] = json.dumps(record["tech_stack"])
        if record.get("industry_tags"):
            record["industry_tags"] = ", ".join(record["industry_tags"] or [])
        records.append(record)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format.lower() == "csv":
        filepath = output_path / f"leads_{timestamp}.csv"
        df = pd.DataFrame(records)
        df.to_csv(filepath, index=False)
    elif format.lower() == "json":
        filepath = output_path / f"leads_{timestamp}.json"
        with open(filepath, "w") as f:
            json.dump(records, f, indent=2, default=str)
    else:
        raise ValueError(f"Unsupported format: {format}. Use 'csv' or 'json'.")

    logger.info(f"Exported {len(records)} leads to {filepath}")
    return str(filepath)
