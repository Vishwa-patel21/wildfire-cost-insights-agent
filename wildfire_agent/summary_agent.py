from google.adk.agents import LlmAgent

summary_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="SummaryAgent",
    description="Produces human-readable summaries of wildfire cost tables.",
    instruction=(
        "You take a markdown cost table and produce a short "
        "2–4 sentence readable explanation for a general audience."
    )
)
