"""Export leads to CSV or JSON."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.database.connection import get_client, disconnect
from src.database.models import to_snake_dict

logger = logging.getLogger(__name__)


async def export_leads(
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
    db = await get_client()

    # Build where clause
    where = {}
    if state:
        where["state"] = state.upper()
    if category:
        where["category"] = {"equals": category, "mode": "insensitive"}
    if min_quality > 0:
        where["qualityScore"] = {"gte": min_quality}
    if enriched_only:
        where["isEnriched"] = True

    leads = await db.lead.find_many(where=where if where else None)
    await disconnect()

    if not leads:
        logger.warning("No leads found matching export criteria")
        return ""

    # Convert to list of snake_case dicts
    records = []
    for lead in leads:
        record = to_snake_dict(lead)
        # Serialize complex types
        if record.get("tech_stack") and isinstance(record["tech_stack"], dict):
            record["tech_stack"] = json.dumps(record["tech_stack"])
        if record.get("industry_tags") and isinstance(record["industry_tags"], list):
            record["industry_tags"] = ", ".join(record["industry_tags"])
        records.append(record)

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

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
