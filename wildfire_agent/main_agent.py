# wildfire_agent/main_agent.py

import os
import json
import logging
from typing import Any, Dict, List, Tuple

import requests
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

# -------------------------------------------------------------------
# Logging / observability
# -------------------------------------------------------------------

logger = logging.getLogger("wildfire_cost_agent")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
        )
    )
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# -------------------------------------------------------------------
# Environment / constants
# -------------------------------------------------------------------

MODEL_NAME = "gemini-2.5-flash"

# Search-specific env vars (support both ADK-style and fallback names)
SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY") or os.getenv("GOOGLE_API_KEY")
SEARCH_CSE_ID = os.getenv("GOOGLE_SEARCH_CX") or os.getenv("GOOGLE_CSE_ID")

# -------------------------------------------------------------------
# Simple in-memory session state
# -------------------------------------------------------------------
# NOTE: This is process-local memory, good enough to demonstrate
# "Sessions & Memory" for the capstone. In production, you would use
# a persistent store or Memory Bank instead.

SESSION_MEMORY: Dict[str, Dict[str, Any]] = {}


def _get_session_memory(session_id: str) -> Dict[str, Any]:
    """Return (and initialise) a per-session memory dict."""
    if session_id not in SESSION_MEMORY:
        SESSION_MEMORY[session_id] = {
            "last_year": None,
            "last_raw_records": None,
            "last_aggregated": None,
            "last_compacted": None,
            "last_summary": None,
            "last_search_query": None,
            "last_search_results": None,
        }
        logger.info("Created new session memory for session_id=%s", session_id)
    return SESSION_MEMORY[session_id]


# -------------------------------------------------------------------
# Tool implementations
# -------------------------------------------------------------------


def load_mock_wildfire_costs(
    year: int = 2024,
    session_id: str = "default",
) -> List[Dict[str, Any]]:
    """
    Load a small synthetic wildfire cost dataset for a given year.

    Each record has:
      - region: geographic region name
      - category: 'aircraft', 'personnel', or 'equipment'
      - cost: total cost in dollars
      - hours: usage hours (0 where not tracked)

    Session / memory:
      - Stores raw records and year in SESSION_MEMORY[session_id].
    """
    data: List[Dict[str, Any]] = [
        {"region": "South", "category": "aircraft", "cost": 176_870.51, "hours": 116.9},
        {"region": "Central", "category": "aircraft", "cost": 161_923.60, "hours": 102.7},
        {"region": "Northwest", "category": "aircraft", "cost": 154_527.82, "hours": 94.8},
        {"region": "Northeast", "category": "aircraft", "cost": 131_905.83, "hours": 123.2},
        {"region": "Central", "category": "personnel", "cost": 97_266.43, "hours": 0.0},
        {"region": "Northeast", "category": "personnel", "cost": 84_489.65, "hours": 0.0},
        {"region": "Northwest", "category": "personnel", "cost": 76_568.23, "hours": 0.0},
        {"region": "South", "category": "personnel", "cost": 74_011.79, "hours": 0.0},
        {"region": "Central", "category": "equipment", "cost": 66_877.06, "hours": 0.0},
        {"region": "Northeast", "category": "equipment", "cost": 61_460.99, "hours": 0.0},
        {"region": "Northwest", "category": "equipment", "cost": 58_812.48, "hours": 0.0},
        {"region": "South", "category": "equipment", "cost": 49_164.94, "hours": 0.0},
    ]

    mem = _get_session_memory(session_id)
    mem["last_year"] = year
    mem["last_raw_records"] = data

    logger.info(
        "Loaded mock wildfire costs for year=%s (records=%d, session_id=%s)",
        year,
        len(data),
        session_id,
    )
    return data


def aggregate_costs(
    records: List[Dict[str, Any]],
    session_id: str = "default",
) -> List[Dict[str, Any]]:
    """
    Aggregate wildfire costs by (region, category).

    Parameters
    ----------
    records:
        List of records with keys: region, category, cost, hours.

    Returns
    -------
    List[Dict[str, Any]]:
        One row per (region, category) with:
        - region
        - category
        - total_cost
        - hours  (summed)

    Session / memory:
      - Stores aggregated list in SESSION_MEMORY[session_id]["last_aggregated"].
    """
    logger.info(
        "Aggregating costs (input_records=%d, session_id=%s)",
        len(records),
        session_id,
    )

    totals: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for r in records:
        region = r.get("region")
        category = r.get("category")
        cost = float(r.get("cost", 0.0))
        hours = float(r.get("hours", 0.0))
        key = (region, category)

        if key not in totals:
            totals[key] = {
                "region": region,
                "category": category,
                "total_cost": 0.0,
                "hours": 0.0,
            }

        totals[key]["total_cost"] += cost
        totals[key]["hours"] += hours

    aggregated_list = list(totals.values())
    aggregated_list.sort(key=lambda x: x["total_cost"], reverse=True)

    mem = _get_session_memory(session_id)
    mem["last_aggregated"] = aggregated_list

    logger.info(
        "Aggregation complete (groups=%d, session_id=%s)",
        len(aggregated_list),
        session_id,
    )
    return aggregated_list


def compact_aggregated_costs(
    aggregated: List[Dict[str, Any]],
    max_rows: int = 6,
    session_id: str = "default",
) -> List[Dict[str, Any]]:
    """
    Context engineering helper: compact aggregated costs to the top N rows.

    This keeps only the highest-cost buckets so that downstream prompts
    stay small in the context window.

    Session / memory:
      - Stores compacted list in SESSION_MEMORY[session_id]["last_compacted"].
    """
    logger.info(
        "Compacting aggregated costs (input_rows=%d, max_rows=%d, session_id=%s)",
        len(aggregated),
        max_rows,
        session_id,
    )

    # Sort defensively in case the caller didn't.
    sorted_rows = sorted(
        aggregated,
        key=lambda x: float(x.get("total_cost", 0.0)),
        reverse=True,
    )
    compacted = sorted_rows[:max_rows]

    mem = _get_session_memory(session_id)
    mem["last_compacted"] = compacted

    logger.info(
        "Compaction complete (output_rows=%d, session_id=%s)",
        len(compacted),
        session_id,
    )
    return compacted


def build_cost_table(
    aggregated: Any,
    session_id: str = "default",
) -> str:
    """
    Build a markdown table + short narrative summary from aggregated costs.

    Context / memory:
      - Accepts either a Python list or a JSON string of aggregated rows.
      - Stores the final summary string in SESSION_MEMORY[session_id]["last_summary"].
    """
    if isinstance(aggregated, str):
        try:
            aggregated = json.loads(aggregated)
            logger.info(
                "Parsed aggregated JSON string into %d rows (session_id=%s)",
                len(aggregated),
                session_id,
            )
        except Exception as e:
            logger.error("Failed to parse aggregated JSON: %s", e)
            return "Could not parse aggregated cost data."

    if not aggregated:
        logger.warning("build_cost_table called with empty data (session_id=%s)", session_id)
        return "No cost data available."

    lines = ["Region | Category | Total Cost ($) | Hours", "---|---|---|---"]

    for row in aggregated:
        region = row.get("region", "")
        category = row.get("category", "")
        total_cost = float(row.get("total_cost", 0.0))
        hours = float(row.get("hours", 0.0))
        lines.append(f"{region} | {category} | {total_cost:,.2f} | {hours:.1f}")

    table_md = "\n".join(lines)

    top = max(aggregated, key=lambda x: x["total_cost"])
    top_region = top["region"]
    top_category = top["category"]
    top_cost = top["total_cost"]

    aircraft_total = sum(
        r["total_cost"] for r in aggregated if r["category"] == "aircraft"
    )
    personnel_total = sum(
        r["total_cost"] for r in aggregated if r["category"] == "personnel"
    )
    equipment_total = sum(
        r["total_cost"] for r in aggregated if r["category"] == "equipment"
    )

    summary_lines = [
        "Here's a summary of the wildfire costs based on the synthetic data:\n",
        "**Key Insights:**",
        f"- **Largest Single Bucket:** {top_region} – {top_category} at ${top_cost:,.2f}.",
        f"- **By Category:** Aircraft (${aircraft_total:,.2f}), "
        f"Personnel (${personnel_total:,.2f}), "
        f"Equipment (${equipment_total:,.2f}).",
        "- Aircraft is the dominant cost driver across regions, "
        "with personnel generally higher than equipment.",
    ]

    final_summary = table_md + "\n\n" + "\n".join(summary_lines)

    mem = _get_session_memory(session_id)
    mem["last_summary"] = final_summary

    logger.info(
        "Built cost table summary (rows=%d, summary_chars=%d, session_id=%s)",
        len(aggregated),
        len(final_summary),
        session_id,
    )
    return final_summary


def get_last_summary(session_id: str = "default") -> str:
    """
    Retrieve the last cost summary built in this session.

    Demonstrates session/stateful behavior: users can say things like
    "Continue from the previous analysis" and the agent can call this
    tool instead of recomputing everything.
    """
    mem = _get_session_memory(session_id)
    summary = mem.get("last_summary")

    if not summary:
        logger.info(
            "get_last_summary called but no summary found (session_id=%s)",
            session_id,
        )
        return "I don't have a previous summary stored yet in this session."

    logger.info(
        "Retrieved last summary from session memory (chars=%d, session_id=%s)",
        len(summary),
        session_id,
    )
    return summary


def google_search(query: str, session_id: str = "default") -> str:
    """
    Call Google Custom Search to fetch top results and return a short summary.

    Requires environment variables:
      - GOOGLE_SEARCH_API_KEY (preferred) or GOOGLE_API_KEY
      - GOOGLE_SEARCH_CX (preferred) or GOOGLE_CSE_ID

    Observability:
      - Logs each query and whether it succeeded.
    Memory:
      - Stores last query and bullet summaries in SESSION_MEMORY.
    """
    if not SEARCH_API_KEY or not SEARCH_CSE_ID:
        logger.warning(
            "Google search missing credentials (session_id=%s)", session_id
        )
        return (
            "Google Custom Search is not configured. "
            "Set GOOGLE_SEARCH_API_KEY (or GOOGLE_API_KEY) and "
            "GOOGLE_SEARCH_CX (or GOOGLE_CSE_ID) in wildfire_agent/.env."
        )

    params = {
        "key": SEARCH_API_KEY,
        "cx": SEARCH_CSE_ID,
        "q": query,
        "num": 5,
        "safe": "off",
    }

    logger.info("Calling Google Custom Search (query=%r, session_id=%s)", query, session_id)

    try:
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error("Error calling Google Custom Search: %s", e)
        return f"Error calling Google Custom Search: {e}"

    items = data.get("items", [])[:3]
    if not items:
        logger.info("Google search returned no items (session_id=%s)", session_id)
        return "No search results found."

    bullets = []
    for item in items:
        title = item.get("title", "Untitled result")
        snippet = item.get("snippet", "").replace("\n", " ").strip()
        link = item.get("link", "")
        bullets.append(f"- **{title}** – {snippet} ({link})")

    result_text = "Top results from Google Search:\n\n" + "\n".join(bullets)

    mem = _get_session_memory(session_id)
    mem["last_search_query"] = query
    mem["last_search_results"] = result_text

    logger.info(
        "Google search succeeded (results=%d, session_id=%s)",
        len(bullets),
        session_id,
    )
    return result_text


# -------------------------------------------------------------------
# Wrap tools for ADK
# -------------------------------------------------------------------

load_mock_wildfire_costs_tool = FunctionTool(load_mock_wildfire_costs)
aggregate_costs_tool = FunctionTool(aggregate_costs)
compact_aggregated_costs_tool = FunctionTool(compact_aggregated_costs)
build_cost_table_tool = FunctionTool(build_cost_table)
get_last_summary_tool = FunctionTool(get_last_summary)
google_search_tool = FunctionTool(google_search)

# -------------------------------------------------------------------
# Root agent
# -------------------------------------------------------------------

root_agent = LlmAgent(
    model=MODEL_NAME,
    name="WildfireCostInsightsAgent",
    description=(
        "Analyzes synthetic wildfire suppression costs and, if configured, "
        "compares them with real-world trends via Google Search. "
        "Maintains lightweight per-session memory and logs key operations "
        "for observability."
    ),
    instruction=(
        "You are a wildfire cost analysis assistant.\n"
        "\n"
        "Core workflow:\n"
        "- When the user asks for a wildfire cost summary for a year, first call\n"
        "  `load_mock_wildfire_costs`, then `aggregate_costs`.\n"
        "- If the user only needs a high-level view or context is large, call\n"
        "  `compact_aggregated_costs` to keep only the top buckets.\n"
        "- Then call `build_cost_table` to present the results as a table plus insights.\n"
        "\n"
        "Real-world comparison:\n"
        "- If the user asks to compare with real-world trends or external data,\n"
        "  call `google_search` with an appropriate query and include those findings\n"
        "  after the synthetic summary.\n"
        "\n"
        "Session & memory:\n"
        "- Tools accept an optional `session_id`. Use the same session_id within a\n"
        "  conversation so state stays consistent.\n"
        "- When the user says things like 'continue from the previous analysis',\n"
        "  call `get_last_summary` instead of recomputing everything from scratch.\n"
        "\n"
        "Always return clear, concise explanations suitable for non-technical wildfire\n"
        "managers who want quick insight into cost drivers."
    ),
    tools=[
        load_mock_wildfire_costs_tool,
        aggregate_costs_tool,
        compact_aggregated_costs_tool,
        build_cost_table_tool,
        get_last_summary_tool,
        google_search_tool,
    ],
)
