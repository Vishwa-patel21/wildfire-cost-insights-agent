# wildfire_agent/tools.py
"""
Custom tools for the Wildfire Cost Insights Agent.
"""

from __future__ import annotations

from typing import List, Dict, Any
import logging
import random

logger = logging.getLogger(__name__)

# ------------------------------
# Tool 1: Load mock cost data
# ------------------------------

def load_mock_wildfire_costs(
    year: int = 2024,
) -> List[Dict[str, Any]]:
    """
    Tool: Returns a small, mock wildfire cost dataset.
    """
    logger.info("Loading mock wildfire cost data for year=%s", year)

    regions = ["Northwest", "Northeast", "Central", "South"]
    categories = ["aircraft", "equipment", "personnel"]

    data: List[Dict[str, Any]] = []
    random.seed(42)

    for region in regions:
        for cat in categories:
            # generate 3 fake fires per category-region
            for idx in range(3):
                base_cost = {
                    "aircraft": 50_000,
                    "equipment": 20_000,
                    "personnel": 30_000,
                }[cat]

                noise_factor = random.uniform(0.7, 1.3)
                cost = base_cost * noise_factor

                hours = 0.0
                if cat == "aircraft":
                    hours = round(random.uniform(10, 80), 1)

                row = {
                    "region": region,
                    "year": year,
                    "fire_id": f"{region[:2].upper()}-{cat[:2].upper()}-{idx+1:02d}",
                    "category": cat,
                    "cost": round(cost, 2),
                    "hours": hours,
                }
                data.append(row)

    logger.info("Loaded %d mock rows for year=%s", len(data), year)
    return data


# ----------------------------------------------
# Tool 2: Aggregate cost by region & category
# ----------------------------------------------

def aggregate_costs_by_region_and_category(
    records: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Tool: Aggregates cost by (region, category).
    """
    logger.info("Aggregating %d records by region and category", len(records))

    agg: Dict[tuple, Dict[str, Any]] = {}

    for row in records:
        key = (row["region"], row["category"])
        if key not in agg:
            agg[key] = {
                "region": row["region"],
                "category": row["category"],
                "total_cost": 0.0,
                "total_hours": 0.0,
            }

        agg[key]["total_cost"] += float(row.get("cost", 0.0))
        agg[key]["total_hours"] += float(row.get("hours", 0.0))

    aggregated = []
    for (_, _), v in agg.items():
        v["total_cost"] = round(v["total_cost"], 2)
        v["total_hours"] = round(v["total_hours"], 1)
        aggregated.append(v)

    logger.info("Aggregation produced %d rows", len(aggregated))
    return aggregated


# ---------------------------------------------
# Tool 3: Build a text table for visualization
# ---------------------------------------------

def build_cost_table_text(
    aggregated: List[Dict[str, Any]],
) -> str:
    """
    Tool: Converts aggregated cost data into a simple text table.
    """
    logger.info("Building text table for %d aggregated rows", len(aggregated))

    if not aggregated:
        return "No data to display."

    aggregated_sorted = sorted(
        aggregated,
        key=lambda r: r["total_cost"],
        reverse=True,
    )

    lines = []
    header = f"{'Region':<12} | {'Category':<10} | {'Total Cost ($)':>14} | {'Total Hours':>11}"
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    for row in aggregated_sorted:
        lines.append(
            f"{row['region']:<12} | {row['category']:<10} | {row['total_cost']:>14,.2f} | {row['total_hours']:>11,.1f}"
        )

    table_text = "\n".join(lines)
    logger.debug("Built table text:\n%s", table_text)
    return table_text
