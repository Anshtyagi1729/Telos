# api/services/decomposer.py
import json

from api.services.llm import get_completion

PROMPT = """
You are a technical project planner for an AI agent marketplace.

Read this project brief and break it into atomic tasks for AI agents.

Rules:
- Each task completable by one agent independently in under 2 hours
- Specific: "Build POST /users endpoint" not "Build API"
- Never create tasks for installing dependencies or environment setup
- Agents write code only — environment is already configured
- Order index rules:
  - Assign order_index based on dependencies only
  - order_index 0 = needs nothing else to exist first
  - order_index 1 = needs at least one order_index 0 task done first
  - order_index 2 = needs at least one order_index 1 task done first
  - Same order_index = can run in parallel
  - Ask yourself: what would fail if this task ran before its dependencies?
- done_when must be objectively verifiable by another agent
- credits: simple=10, medium=20, complex=30

Return ONLY a JSON array, no markdown, no explanation:
[
  {{
    "title": "verb-first task name",
    "description": "exactly what to build, be specific about inputs/outputs/conventions",
    "skills_required": ["Python"],
    "done_when": "measurable completion condition",
    "credits": 10,
    "order_index": 0
  }}
]

Project brief:
{goal}
"""


def decompose_project(goal: str) -> list[dict[str, str]]:
    raw = get_completion(PROMPT.format(goal=goal))
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())
