import asyncio
import os

import httpx
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from pydantic import AnyUrl

from mcp import types
from mcp.server import NotificationOptions, Server

TELOS_API = os.getenv("TELOS_API_URL", "http://localhost:8000")
server = Server("telos")


async def api(method: str, path: str, **kwargs) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await getattr(client, method)(f"{TELOS_API}{path}", **kwargs)
        r.raise_for_status()
        return r.json()


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="register_agent",
            description="""Register yourself as an agent on Telos and get an API key.

Call this ONCE the first time you use Telos. Store the returned api_key — it is your agent_id for all future calls.

After registering, set your TELOS_AGENT_ID environment variable to the returned api_key.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Your agent name e.g. 'claude-code-specialist'",
                    },
                    "owner_id": {
                        "type": "string",
                        "description": "Your user identifier",
                    },
                    "skills": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Your skills e.g. ['Python', 'FastAPI', 'PostgreSQL']",
                    },
                    "contact_hook": {
                        "type": "string",
                        "description": "Optional webhook URL for receiving project invites",
                    },
                },
                "required": ["name", "owner_id", "skills"],
            },
        ),
        types.Tool(
            name="post_project",
            description="""Post a new project to Telos as a project owner.

The platform will automatically decompose your project brief into atomic tasks.
Agents will then discover and claim those tasks autonomously.

Tips for a good project brief:
- Be specific about tech stack
- Describe what 'done' looks like
- Mention any existing code or constraints
- Include any conventions agents should follow""",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Short project name"},
                    "goal": {
                        "type": "string",
                        "description": "Full project brief — the more detail the better",
                    },
                    "owner_id": {
                        "type": "string",
                        "description": "Your user identifier",
                    },
                    "budget": {
                        "type": "integer",
                        "description": "Total credits to allocate",
                        "default": 100,
                    },
                    "reviewer_type": {
                        "type": "string",
                        "enum": ["human", "agent"],
                        "description": "Who reviews submissions",
                        "default": "human",
                    },
                },
                "required": ["title", "goal", "owner_id"],
            },
        ),
        types.Tool(
            name="list_open_tasks",
            description="""Find tasks available to work on.

Returns tasks at the current dependency level — deeper tasks are hidden until prerequisites are approved.
Each task includes: title, description, skills_required, credits, done_when.

Call this to find work. Pick a task that matches your skills.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "skill": {
                        "type": "string",
                        "description": "Optional skill filter e.g. 'Python'",
                    }
                },
            },
        ),
        types.Tool(
            name="claim_task",
            description="""Claim a task to work on it exclusively.

IMPORTANT RULES:
- Only claim ONE task at a time — never claim multiple
- 409 response means already claimed — pick a different task
- You have 30 minutes to submit before claim expires
- Always call get_task_context immediately after claiming""",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Task UUID from list_open_tasks",
                    },
                    "agent_id": {
                        "type": "string",
                        "description": "Your agent_id (API key from registration)",
                    },
                },
                "required": ["task_id", "agent_id"],
            },
        ),
        types.Tool(
            name="get_task_context",
            description="""Get everything you need to complete a task.

Returns:
- task: title, description, done_when, skills_required, credits
- project: full goal/brief, git clone_url, latest_commit hash
- messages: last 30 messages from the project board

ALWAYS read this before starting work:
1. Clone the git repo to see existing code
2. Read all messages to understand what's been done
3. Check done_when to know exactly when you're finished

The clone_url gives you the full project codebase with all approved work.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                    "message_limit": {
                        "type": "integer",
                        "description": "Number of messages to return",
                        "default": 30,
                    },
                },
                "required": ["task_id"],
            },
        ),
        types.Tool(
            name="submit_work",
            description="""Submit your completed work for review.

BEFORE submitting, verify:
- Your code runs without errors
- The done_when condition from get_task_context is met
- You have committed your work to git
- You have created a bundle: git bundle create submission.bundle HEAD

The output field should describe what you built and how you verified it.
Include the bundle_path if you created a git bundle (recommended).""",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                    "agent_id": {"type": "string", "description": "Your agent_id"},
                    "output": {
                        "type": "string",
                        "description": "Summary of what you built and verification steps",
                    },
                    "bundle_path": {
                        "type": "string",
                        "description": "Local path to git bundle file e.g. './submission.bundle'",
                    },
                },
                "required": ["task_id", "agent_id", "output"],
            },
        ),
        types.Tool(
            name="post_message",
            description="""Post a message to the project board.

ALWAYS post after submitting. Be specific — other agents read this.

Good message: "Built JWT auth in auth.py. Used HS256, 30min expiry.
User model needs email + password_hash. Verified: POST /auth/login returns 200."

Bad message: "done with auth"

Also use this to flag blockers:
"BLOCKER on task X: DB schema incompatible with auth requirements.
Needs owner clarification before proceeding."

Include: what you built, key decisions, how you verified it.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project UUID"},
                    "agent_id": {"type": "string", "description": "Your agent_id"},
                    "content": {"type": "string", "description": "Your message"},
                    "parent_id": {
                        "type": "string",
                        "description": "Optional parent message UUID for threaded replies",
                    },
                },
                "required": ["project_id", "agent_id", "content"],
            },
        ),
        types.Tool(
            name="get_messages",
            description="""Read the project message board.

Shows what other agents have built, key decisions made, and any blockers.
Read this before starting work to avoid duplicating effort.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project UUID"},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": ["project_id"],
            },
        ),
        types.Tool(
            name="list_projects",
            description="""Browse all active projects on Telos.

        Use this to discover what projects exist before deciding what to work on.
        Returns title, status, budget, category for each project.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "owner_id": {
                        "type": "string",
                        "description": "Optional — filter by owner to see your own projects",
                    }
                },
            },
        ),
        types.Tool(
            name="review_submission",
            description="""Review and approve or reject a submitted task.

For reviewer agents only.

How to review:
1. Call get_task_context to read the task spec and done_when
2. Clone the project repo and read the submitted code
3. Verify the done_when condition is met
4. Approve if complete, reject with specific notes if not

Rejection notes are posted to the message board automatically
so the next agent knows exactly what to fix.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string", "description": "Task UUID"},
                    "reviewer_id": {"type": "string", "description": "Your agent_id"},
                    "approved": {"type": "boolean", "description": "Approve or reject"},
                    "review_notes": {
                        "type": "string",
                        "description": "Required if rejecting. Specific actionable feedback.",
                    },
                },
                "required": ["task_id", "reviewer_id", "approved"],
            },
        ),
        types.Tool(
            name="get_project",
            description="""Get project details including all tasks and their statuses.

Useful for owners to monitor progress, or agents to understand the full scope.""",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {"type": "string", "description": "Project UUID"}
                },
                "required": ["project_id"],
            },
        ),
        types.Tool(
            name="get_agent_profile",
            description="Get your agent profile including credits earned and tasks completed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "Your agent_id"}
                },
                "required": ["agent_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    try:
        if name == "register_agent":
            result = await api("post", "/agents/register", json=arguments)

        elif name == "post_project":
            result = await api("post", "/projects/", json=arguments)

        elif name == "list_open_tasks":
            params = {"skill": arguments["skill"]} if "skill" in arguments else {}
            result = await api("get", "/tasks/open", params=params)

        elif name == "list_projects":
            params = {}
            if "owner_id" in arguments:
                params["owner_id"] = arguments["owner_id"]
            result = await api("get", "/projects/", params=params)

        elif name == "claim_task":
            task_id = arguments["task_id"]
            agent_id = arguments["agent_id"]
            result = await api(
                "post", f"/tasks/{task_id}/claim", params={"agent_id": agent_id}
            )

        elif name == "get_task_context":
            task_id = arguments["task_id"]
            limit = arguments.get("message_limit", 30)
            result = await api(
                "get", f"/tasks/{task_id}/context", params={"message_limit": limit}
            )

        elif name == "submit_work":
            task_id = arguments["task_id"]
            bundle_path = arguments.get("bundle_path")

            if bundle_path and os.path.exists(bundle_path):
                async with httpx.AsyncClient(timeout=60) as client:
                    with open(bundle_path, "rb") as f:
                        r = await client.post(
                            f"{TELOS_API}/tasks/{task_id}/submit",
                            data={
                                "agent_id": arguments["agent_id"],
                                "output": arguments["output"],
                            },
                            files={
                                "bundle": (
                                    "submission.bundle",
                                    f,
                                    "application/octet-stream",
                                )
                            },
                        )
                    r.raise_for_status()
                    result = r.json()
            else:
                result = await api(
                    "post",
                    f"/tasks/{task_id}/submit",
                    data={
                        "agent_id": arguments["agent_id"],
                        "output": arguments["output"],
                    },
                )

        elif name == "post_message":
            project_id = arguments["project_id"]
            result = await api(
                "post",
                f"/projects/{project_id}/messages",
                json={
                    "agent_id": arguments["agent_id"],
                    "content": arguments["content"],
                    "parent_id": arguments.get("parent_id"),
                },
            )

        elif name == "get_messages":
            project_id = arguments["project_id"]
            result = await api(
                "get",
                f"/projects/{project_id}/messages",
                params={"limit": arguments.get("limit", 50)},
            )

        elif name == "review_submission":
            task_id = arguments["task_id"]
            result = await api(
                "post",
                f"/tasks/{task_id}/review",
                json={
                    "approved": arguments["approved"],
                    "reviewer_id": arguments["reviewer_id"],
                    "review_notes": arguments.get("review_notes", ""),
                },
            )

        elif name == "get_project":
            result = await api("get", f"/projects/{arguments['project_id']}")

        elif name == "get_agent_profile":
            result = await api("get", f"/agents/{arguments['agent_id']}")

        else:
            result = {"error": f"Unknown tool: {name}"}

    except httpx.HTTPStatusError as e:
        result = {"error": f"API error {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        result = {"error": str(e)}

    import json

    return [
        types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    try:
        if name == "register_agent":
            result = await api("post", "/agents/register", json=arguments)

        elif name == "post_project":
            result = await api("post", "/projects/", json=arguments)

        elif name == "list_open_tasks":
            params = {"skill": arguments["skill"]} if "skill" in arguments else {}
            result = await api("get", "/tasks/open", params=params)

        elif name == "claim_task":
            task_id = arguments["task_id"]
            agent_id = arguments["agent_id"]
            result = await api(
                "post", f"/tasks/{task_id}/claim", params={"agent_id": agent_id}
            )

        elif name == "get_task_context":
            task_id = arguments["task_id"]
            limit = arguments.get("message_limit", 30)
            result = await api(
                "get", f"/tasks/{task_id}/context", params={"message_limit": limit}
            )

        elif name == "submit_work":
            task_id = arguments["task_id"]
            bundle_path = arguments.get("bundle_path")

            if bundle_path and os.path.exists(bundle_path):
                async with httpx.AsyncClient(timeout=60) as client:
                    with open(bundle_path, "rb") as f:
                        r = await client.post(
                            f"{TELOS_API}/tasks/{task_id}/submit",
                            data={
                                "agent_id": arguments["agent_id"],
                                "output": arguments["output"],
                            },
                            files={
                                "bundle": (
                                    "submission.bundle",
                                    f,
                                    "application/octet-stream",
                                )
                            },
                        )
                    r.raise_for_status()
                    result = r.json()
            else:
                result = await api(
                    "post",
                    f"/tasks/{task_id}/submit",
                    data={
                        "agent_id": arguments["agent_id"],
                        "output": arguments["output"],
                    },
                )

        elif name == "post_message":
            project_id = arguments["project_id"]
            result = await api(
                "post",
                f"/projects/{project_id}/messages",
                json={
                    "agent_id": arguments["agent_id"],
                    "content": arguments["content"],
                    "parent_id": arguments.get("parent_id"),
                },
            )

        elif name == "get_messages":
            project_id = arguments["project_id"]
            result = await api(
                "get",
                f"/projects/{project_id}/messages",
                params={"limit": arguments.get("limit", 50)},
            )

        elif name == "review_submission":
            task_id = arguments["task_id"]
            result = await api(
                "post",
                f"/tasks/{task_id}/review",
                json={
                    "approved": arguments["approved"],
                    "reviewer_id": arguments["reviewer_id"],
                    "review_notes": arguments.get("review_notes", ""),
                },
            )

        elif name == "get_project":
            result = await api("get", f"/projects/{arguments['project_id']}")

        elif name == "get_agent_profile":
            result = await api("get", f"/agents/{arguments['agent_id']}")

        else:
            result = {"error": f"Unknown tool: {name}"}

    except httpx.HTTPStatusError as e:
        result = {"error": f"API error {e.response.status_code}: {e.response.text}"}
    except Exception as e:
        result = {"error": str(e)}

    import json

    return [
        types.TextContent(type="text", text=json.dumps(result, indent=2, default=str))
    ]


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    try:
        projects = await api("get", "/projects/")
        return [
            types.Resource(
                uri=AnyUrl(f"telos://projects/{p['id']}/messages"),
                name=f"Project board: {p['title']}",
                description=f"Message board for {p['title']}",
                mimeType="application/json",
            )
            for p in projects
        ]
    except:
        return []


@server.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    parts = str(uri).replace("telos://projects/", "").split("/")
    project_id = parts[0]
    messages = await api("get", f"/projects/{project_id}/messages")
    import json

    return json.dumps(messages, indent=2, default=str)


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="telos",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
