# Wildfire Cost Insights Agent (ADK + Gemini)

This project implements a **multi-agent wildfire cost analysis system** using the **Google Agent Development Kit (ADK)** and Gemini.

It analyzes **synthetic wildfire suppression costs** (aircraft, personnel, equipment) across regions and can optionally compare them with real-world information via Google Search.

The project is built for the *Agents Intensive – Capstone Project* and demonstrates several required concepts:

- Multi-agent system (root agent + summary agent)
- Custom tools and a search tool
- Memory / session state
- Context engineering (compaction)
- Observability via the ADK UI
- Agent evaluation
- ADK web deployment (local)

---

## Features and ADK Concepts

### 1. Multi-Agent System

- **Root agent** (`WildfireCostInsightsAgent`)
  - Orchestrates the workflow
  - Calls tools: load → aggregate → summarize
- **Summary agent**
  - Takes intermediate outputs and rewrites them into a human-friendly explanation
- Uses ADK’s `transfer_to_agent` pattern so the root can delegate to the summary agent and then respond back to the user.

### 2. Tools

Custom tools implemented in `tools.py`:

- `load_mock_wildfire_costs(year: int = 2024)`  
  Loads a small synthetic dataset with wildfire costs by region and category.

- `aggregate_costs(records)`  
  Aggregates cost and hours per (region, category).

- `build_cost_table(aggregated)`  
  Builds a Markdown table plus “Key Insights”.

- `compact_aggregated_costs(aggregated, top_n=4)`  
  Context-engineering tool – keeps only the top cost buckets (used for compaction).

- `get_last_summary()` / `store_last_summary(summary)`  
  Simple in-memory state for the “last summary” so the agent can recall previous analysis.

External / built-in style tool:

- `google_search(query: str)`  
  Uses Google Custom Search (API key + CX from environment) to bring in real-world wildfire/aviation cost context.

These tools are wrapped with `FunctionTool` and registered on the root agent.

### 3. Memory and Session State

- The project stores the **last generated cost summary** in an in-memory variable.
- The `get_last_summary` tool returns this without recomputing.
- In ADK, this works inside a session so the agent can answer follow-ups like:
  > “Continue from the previous analysis and repeat the last summary from memory.”

### 4. Context Engineering (Compaction)

- `compact_aggregated_costs` reduces the full aggregated table down to the **top N cost buckets** (e.g., top 4 by total cost).
- This lets the agent:
  - Keep only the most important information
  - Re-summarize shorter context for follow-up questions

Example prompt:

> “Compact the results to the top 4 buckets and re-summarize.”

### 5. Observability

When running with `adk web`, you can see:

- Each tool call (`load_mock_wildfire_costs`, `aggregate_costs`, etc.)
- Inputs and outputs
- Traces and logs for debugging

This satisfies the observability requirement (logging/tracing visible in the ADK Dev UI).

### 6. Evaluation

An evaluation set file (e.g. `evalsetXXXX.evalset.json`) is included.  
It defines one or more test cases, for example:

- Input: *“Give me a wildfire cost summary for 2024.”*  
- Expected: Model should call the cost tools and return a table with key insights.

You can run evaluation from the ADK UI under the **Eval** tab.
### 7. Deployment (Local)
- Runs with:  `adk web`
---

## Project Structure

```text
wildfire_agent/
│
├── __init__.py                # Exposes root_agent to ADK
├── main_agent.py              # Root agent + summary agent wiring
├── tools.py                   # All tool implementations
├── evalsetXXXX.evalset.json   # Evaluation cases
│
└── README.md
requirements.txt               # Dependencies for adk web
```
---
## Installation and Local Run

### 1. Clone the repository: 
`
git clone https://github.com/<YOUR_USERNAME>/wildfire-cost-insights-agent.git`
`cd wildfire-cost-insights-agent`

### 2.Install dependencies:
`pip install -r requirements.txt`

### 3.Set environment variables (for Gemini and optional search):
```text
export GOOGLE_API_KEY="your_api_key_here"
 #Optional search config:
export GOOGLE_SEARCH_API_KEY="your_search_key_here"
export GOOGLE_SEARCH_CX="your_cse_id_here"
```
(On Windows PowerShell, use: \$env:GOOGLE_API_KEY="...".)
### 4.Start ADK web: 
`adk web`
### 5.Open the Dev UI (default):
`http://localhost:8000
`

---
## Example Prompts
- **Base summary**
  - Give me a wildfire cost summary for 2024.

- **Context compaction**
  - Compact the results to the top 4 wildfire cost buckets and re-summarize.

- **Use memory**
  - Continue from the previous analysis and just repeat the last summary from memory.

- **Real-world comparison**
  - Compare the synthetic wildfire cost data with real-world aviation and personnel wildfire spending.
 ---
## Notes for the Capstone Write-Up

- This project fits the Enterprise Agents or Agents for Good track:

- **Problem:** Understanding cost drivers for wildfire suppression (aircraft, personnel, equipment).

- **Solution**: An agent that can:

  - Load and aggregate synthetic costs

  - Summarize and compact the results

  - Compare against real-world trends via Google Search

  - Maintain memory across turns

- You can reference the sections above when writing your Kaggle capstone description.

  ---
  ## License

- Open-source for educational use.
- Do NOT upload any API keys or secrets.
