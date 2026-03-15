# api/services/git.py  ← new file
import os
import subprocess
import tempfile


def init_project_repo(project_id: str) -> tuple[str, str]:
    repo_path = f"/data/repos/{project_id}.git"
    os.makedirs("/data/repos", exist_ok=True)

    # init bare repo
    _ = subprocess.run(
        ["git", "init", "--bare", repo_path], check=True, capture_output=True
    )

    # create initial empty commit so agents can clone immediately
    with tempfile.TemporaryDirectory() as tmp:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "system",
            "GIT_AUTHOR_EMAIL": "system@telos.dev",
            "GIT_COMMITTER_NAME": "system",
            "GIT_COMMITTER_EMAIL": "system@telos.dev",
        }
        _ = subprocess.run(["git", "clone", repo_path, tmp], check=True)
        _ = subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init: project created"],
            cwd=tmp,
            check=True,
            env=env,
        )
        _ = subprocess.run(
            ["git", "push", "origin", "main"], cwd=tmp, check=True, env=env
        )

    # get initial commit hash
    result = subprocess.run(
        ["git", "--git-dir", repo_path, "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
    )
    return repo_path, result.stdout.strip()
