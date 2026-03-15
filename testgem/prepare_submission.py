import json

with open('Dockerfile', 'r') as f:
    dockerfile_content = f.read()
with open('requirements.txt', 'r') as f:
    reqs_content = f.read()

output_dict = {
    "files": {
        "Dockerfile": dockerfile_content,
        "requirements.txt": reqs_content
    },
    "summary": "Created a Dockerfile for the FastAPI app using python:3.11-slim. Included necessary system and Python dependencies for PostgreSQL and bcrypt.",
    "notes": "Uses uvicorn as the entrypoint."
}

submission_data = {
    "agent_id": "jOvKZ8FA2ImLvraZ4rTijCEkPwLMthINNkhHo_6OYo",
    "output": json.dumps(output_dict),
    "commit_hash": None,
    "parent_hash": None
}

with open('submission.json', 'w') as f:
    json.dump(submission_data, f)
