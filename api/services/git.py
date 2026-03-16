import os
import subprocess
import tempfile


def init_project_repo(project_id: str) -> tuple[str, str]:
    repo_path = f"/data/repos/{project_id}.git"
    os.makedirs("/data/repos", exist_ok=True)

    _ = subprocess.run(
        ["git", "init", "--bare", repo_path], check=True, capture_output=True
    )

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
            capture_output=True,
        )
        _ = subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=tmp,
            check=True,
            env=env,
            capture_output=True,
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


def get_commit_info(bundle_path: str) -> tuple[str | None, str | None]:
    with tempfile.TemporaryDirectory() as tmp:
        # init temp repo and fetch from bundle
        _ = subprocess.run(["git", "init", tmp], capture_output=True)
        _ = subprocess.run(
            [
                "git",
                "--git-dir",
                f"{tmp}/.git",
                "fetch",
                bundle_path,
                "HEAD:refs/heads/incoming",
            ],
            capture_output=True,
        )
        commit_result = subprocess.run(
            ["git", "--git-dir", f"{tmp}/.git", "rev-parse", "incoming"],
            capture_output=True,
            text=True,
        )
        commit_hash = commit_result.stdout.strip() or None

        parent_result = subprocess.run(
            ["git", "--git-dir", f"{tmp}/.git", "log", "--pretty=%P", "-1", "incoming"],
            capture_output=True,
            text=True,
        )
        parent_hash = parent_result.stdout.strip() or None

    return commit_hash, parent_hash
