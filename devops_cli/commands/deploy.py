"""Deployment commands."""

import subprocess
import time
from typing import Optional

import typer
import requests
from rich.console import Console
from rich.prompt import Confirm

from devops_cli.config.settings import load_config
from devops_cli.utils.output import (
    success, error, warning, info, header,
    create_table, status_badge, console as out_console
)

app = typer.Typer(help="Deployment commands")
console = Console()


def run_git(args: list[str]) -> tuple[bool, str]:
    """Run a git command."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode == 0, (result.stdout + result.stderr).strip()
    except FileNotFoundError:
        return False, "Git not installed"


def get_github_headers(token: str) -> dict:
    """Get GitHub API headers."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }


@app.command("status")
def deploy_status():
    """Show deployment status across environments."""
    config = load_config()
    envs = config.get("environments", {})

    if not envs:
        warning("No environments configured")
        return

    header("Deployment Status")

    # Get repo info
    ok, remote_url = run_git(["remote", "get-url", "origin"])
    if not ok or "github.com" not in remote_url:
        error("Could not determine GitHub repository")
        return

    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.replace(":", "/").split("/")
    repo = f"{parts[-2]}/{parts[-1]}"

    token = config.get("github", {}).get("token")

    table = create_table(
        "",
        [("Environment", "cyan"), ("Branch", ""), ("Latest Commit", "dim"), ("Status", "")]
    )

    for env_name, env_config in envs.items():
        branch = env_config.get("branch", "main")

        # Get latest commit on branch
        if token:
            try:
                resp = requests.get(
                    f"https://api.github.com/repos/{repo}/branches/{branch}",
                    headers=get_github_headers(token)
                )
                if resp.ok:
                    data = resp.json()
                    commit = data["commit"]["sha"][:7]
                    message = data["commit"]["commit"]["message"].split("\n")[0][:30]
                    commit_info = f"{commit} - {message}"
                else:
                    commit_info = "Could not fetch"
            except Exception:
                commit_info = "Error"
        else:
            ok, commit = run_git(["rev-parse", f"origin/{branch}"])
            commit_info = commit[:7] if ok else "Unknown"

        # Get workflow status for branch
        workflow_status = "unknown"
        if token:
            try:
                resp = requests.get(
                    f"https://api.github.com/repos/{repo}/actions/runs",
                    params={"branch": branch, "per_page": 1},
                    headers=get_github_headers(token)
                )
                if resp.ok:
                    runs = resp.json().get("workflow_runs", [])
                    if runs:
                        conclusion = runs[0].get("conclusion") or runs[0].get("status")
                        workflow_status = conclusion
            except Exception:
                pass

        table.add_row(
            env_name.upper(),
            branch,
            commit_info,
            status_badge(workflow_status)
        )

    console.print(table)


@app.command("trigger")
def trigger_deploy(
    environment: str = typer.Argument(..., help="Environment to deploy to (dev, staging, prod)"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Override branch to deploy"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation for prod"),
):
    """Trigger a deployment to an environment."""
    config = load_config()
    envs = config.get("environments", {})

    if environment not in envs:
        error(f"Environment '{environment}' not configured")
        info(f"Available: {', '.join(envs.keys())}")
        return

    env_config = envs[environment]
    deploy_branch = branch or env_config.get("branch", "main")
    auto_deploy = env_config.get("auto_deploy", False)

    # Safety check for production
    if environment == "prod" and not force:
        console.print()
        warning("You are about to deploy to PRODUCTION!")
        info(f"Branch: {deploy_branch}")
        if not Confirm.ask("Are you sure you want to continue?"):
            info("Deployment cancelled")
            return

    header(f"Deploying to {environment.upper()}")
    info(f"Branch: {deploy_branch}")

    # Get repo info
    ok, remote_url = run_git(["remote", "get-url", "origin"])
    if not ok or "github.com" not in remote_url:
        error("Could not determine GitHub repository")
        return

    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.replace(":", "/").split("/")
    repo = f"{parts[-2]}/{parts[-1]}"

    token = config.get("github", {}).get("token")
    if not token:
        error("GitHub token required for deployment")
        return

    # Look for deploy workflow
    workflow_names = ["deploy.yml", "deploy.yaml", f"deploy-{environment}.yml", f"deploy-{environment}.yaml"]

    deployed = False
    for workflow in workflow_names:
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
        data = {
            "ref": deploy_branch,
            "inputs": {
                "environment": environment
            }
        }

        try:
            resp = requests.post(url, json=data, headers=get_github_headers(token))
            if resp.status_code == 204:
                success(f"Deployment triggered via {workflow}")
                info(f"View at: https://github.com/{repo}/actions")
                deployed = True
                break
        except Exception:
            continue

    if not deployed:
        warning("No deploy workflow found with workflow_dispatch")
        info("Trying to trigger via repository_dispatch...")

        # Try repository dispatch
        url = f"https://api.github.com/repos/{repo}/dispatches"
        data = {
            "event_type": f"deploy-{environment}",
            "client_payload": {
                "environment": environment,
                "branch": deploy_branch
            }
        }

        try:
            resp = requests.post(url, json=data, headers=get_github_headers(token))
            if resp.status_code == 204:
                success(f"Repository dispatch sent: deploy-{environment}")
            else:
                error("Failed to trigger deployment")
                info("Make sure you have a workflow listening for repository_dispatch events")
        except Exception as e:
            error(f"Error: {e}")


@app.command("promote")
def promote(
    source: str = typer.Argument(..., help="Source environment"),
    target: str = typer.Argument(..., help="Target environment"),
):
    """Promote deployment from one environment to another (merge branches)."""
    config = load_config()
    envs = config.get("environments", {})

    if source not in envs:
        error(f"Source environment '{source}' not configured")
        return
    if target not in envs:
        error(f"Target environment '{target}' not configured")
        return

    source_branch = envs[source].get("branch")
    target_branch = envs[target].get("branch")

    header(f"Promoting: {source} -> {target}")
    info(f"Merge: {source_branch} -> {target_branch}")

    # Safety for prod
    if target == "prod":
        console.print()
        warning("You are about to promote to PRODUCTION!")
        if not Confirm.ask("Continue?"):
            info("Promotion cancelled")
            return

    # Get repo
    ok, remote_url = run_git(["remote", "get-url", "origin"])
    if not ok or "github.com" not in remote_url:
        error("Could not determine GitHub repository")
        return

    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.replace(":", "/").split("/")
    repo = f"{parts[-2]}/{parts[-1]}"

    token = config.get("github", {}).get("token")
    if not token:
        error("GitHub token required")
        return

    # Create PR for promotion
    url = f"https://api.github.com/repos/{repo}/pulls"
    data = {
        "title": f"Promote {source} to {target}",
        "body": f"Automated promotion from {source} ({source_branch}) to {target} ({target_branch})",
        "head": source_branch,
        "base": target_branch,
    }

    try:
        resp = requests.post(url, json=data, headers=get_github_headers(token))
        if resp.status_code == 201:
            pr = resp.json()
            success(f"Promotion PR created: #{pr['number']}")
            console.print(f"\n[link={pr['html_url']}]{pr['html_url']}[/link]")

            if Confirm.ask("Merge PR now?", default=False):
                merge_url = f"https://api.github.com/repos/{repo}/pulls/{pr['number']}/merge"
                merge_resp = requests.put(
                    merge_url,
                    json={"merge_method": "merge"},
                    headers=get_github_headers(token)
                )
                if merge_resp.ok:
                    success("PR merged successfully!")
                else:
                    error(f"Merge failed: {merge_resp.json().get('message', 'Unknown error')}")
        elif resp.status_code == 422:
            result = resp.json()
            if "No commits" in str(result):
                info("Branches are already in sync, nothing to promote")
            else:
                error(f"Could not create PR: {result}")
        else:
            error(f"API error: {resp.status_code}")
    except Exception as e:
        error(f"Error: {e}")


@app.command("rollback")
def rollback(
    environment: str = typer.Argument(..., help="Environment to rollback"),
    commits: int = typer.Option(1, "--commits", "-c", help="Number of commits to rollback"),
):
    """Trigger a rollback in an environment."""
    config = load_config()
    envs = config.get("environments", {})

    if environment not in envs:
        error(f"Environment '{environment}' not configured")
        return

    # Safety
    console.print()
    warning(f"You are about to rollback {environment.upper()} by {commits} commit(s)")
    if not Confirm.ask("Are you sure?"):
        info("Rollback cancelled")
        return

    header(f"Rolling back {environment.upper()}")

    # Get repo info
    ok, remote_url = run_git(["remote", "get-url", "origin"])
    if not ok or "github.com" not in remote_url:
        error("Could not determine GitHub repository")
        return

    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.replace(":", "/").split("/")
    repo = f"{parts[-2]}/{parts[-1]}"

    token = config.get("github", {}).get("token")
    if not token:
        error("GitHub token required")
        return

    # Trigger rollback workflow
    workflow_names = ["rollback.yml", "rollback.yaml"]

    for workflow in workflow_names:
        url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches"
        branch = envs[environment].get("branch", "main")
        data = {
            "ref": branch,
            "inputs": {
                "environment": environment,
                "commits": str(commits)
            }
        }

        try:
            resp = requests.post(url, json=data, headers=get_github_headers(token))
            if resp.status_code == 204:
                success(f"Rollback triggered for {environment}")
                info(f"View at: https://github.com/{repo}/actions")
                return
        except Exception:
            continue

    error("No rollback workflow found")
    info("Create a rollback.yml workflow with workflow_dispatch trigger")


@app.command("history")
def deploy_history(
    environment: Optional[str] = typer.Option(None, "--env", "-e", help="Filter by environment"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of deployments to show"),
):
    """Show deployment history from GitHub Actions."""
    config = load_config()

    # Get repo info
    ok, remote_url = run_git(["remote", "get-url", "origin"])
    if not ok or "github.com" not in remote_url:
        error("Could not determine GitHub repository")
        return

    if remote_url.endswith(".git"):
        remote_url = remote_url[:-4]
    parts = remote_url.replace(":", "/").split("/")
    repo = f"{parts[-2]}/{parts[-1]}"

    token = config.get("github", {}).get("token")
    if not token:
        error("GitHub token required")
        return

    header("Deployment History")

    try:
        # Get deployment workflow runs
        url = f"https://api.github.com/repos/{repo}/actions/runs"
        params = {"per_page": limit * 2}  # Get extra to filter
        resp = requests.get(url, params=params, headers=get_github_headers(token))

        if resp.ok:
            runs = resp.json().get("workflow_runs", [])

            # Filter for deploy workflows
            deploy_runs = [
                r for r in runs
                if "deploy" in r["name"].lower()
            ][:limit]

            if not deploy_runs:
                info("No deployment runs found")
                return

            table = create_table(
                "",
                [("Date", "dim"), ("Workflow", "cyan"), ("Branch", ""), ("Status", ""), ("By", "dim")]
            )

            for run in deploy_runs:
                date = run["created_at"][:16].replace("T", " ")
                name = run["name"][:25]
                branch = run["head_branch"][:15]
                conclusion = run.get("conclusion") or run.get("status")
                actor = run["actor"]["login"][:12]

                table.add_row(date, name, branch, status_badge(conclusion), actor)

            console.print(table)
        else:
            error(f"Failed to fetch history: {resp.status_code}")
    except Exception as e:
        error(f"Error: {e}")
