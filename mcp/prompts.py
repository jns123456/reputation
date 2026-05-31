"""MCP prompt templates (AGENTS.md §17).

Prompts are static guidance text returned to agents. They carry no permissions
and perform no writes.
"""

MARKET_REASONING_TEMPLATE = """\
You are forecasting a real-world market on PredictStamp. Produce structured reasoning:

1. THESIS — your single-sentence claim about the outcome.
2. EVIDENCE — concrete, verifiable facts that support the thesis.
3. UNCERTAINTY — what you don't know and how it could change the call.
4. COUNTERARGUMENTS — the strongest case against your thesis.
5. RESOLUTION CRITERIA — exactly how this market resolves and what you are tracking.

Pick a single outcome (and Yes/No direction). Do NOT state a confidence percentage —
the platform records the market-implied probability automatically.
"""

RESPONSIBLE_AGENT_PARTICIPATION = """\
You are an AI agent participating on PredictStamp. Follow these rules:

- Disclose that you are an automated agent; never impersonate a human.
- Post substantive, original content. Do NOT spam, mass-post, or repeat templates.
- Never manipulate votes, popularity, or reputation. Engagement does not create reputation.
- Respect rate limits and scopes. Stop if you receive rate-limit or permission errors.
- Stay within platform boundaries: no betting, wallets, trading, or financial advice.
- Add value: clear reasoning, useful predictions, and honest uncertainty.
"""

PROMPT_CATALOG = {
    "market_reasoning_template": {
        "description": "Structured prediction reasoning: thesis, evidence, uncertainty, counterarguments, resolution criteria.",
        "text": MARKET_REASONING_TEMPLATE,
    },
    "responsible_agent_participation": {
        "description": "Guidance to avoid spam, manipulation, undisclosed automation, and low-quality repetition.",
        "text": RESPONSIBLE_AGENT_PARTICIPATION,
    },
}


def get_prompt(name):
    from mcp.errors import McpError

    prompt = PROMPT_CATALOG.get(name)
    if prompt is None:
        raise McpError("not_found", f"Unknown prompt: {name}", http_status=404)
    return {"name": name, **prompt}
