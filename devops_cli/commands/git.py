"""Git and CI/CD commands."""

import subprocess
import typer
import requests
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from devops_cli.config.settings import load_config
from devops_cli.config.repos import load_repos, get_repo_config
from devops_cli.utils.output import (
    success, error, warning, info, header,
    create_table, status_badge, console as out_console
)

app = typer.Typer(help="Git & CI/CD operations")
console = Console()


def run_git(args: list[str], capture: bool = True) -> tuple[bool, str]:
    """Run a git command and return success status and output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=capture,
            text=True,
            check=False
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, "Git is not installed"


def get_github_headers(token: str) -> dict:
    """Get GitHub API headers."""
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }


def resolve_repo(repo_name: Optional[str] = None) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Resolve repository owner and name.

    Returns: (success, owner, repo)

    If repo_name is provided, looks it up in repos.yaml.
    Otherwise, tries to detect from local git remote.
    """
    if repo_name:
        # Look up in configured repos
        repo_config = get_repo_config(repo_name)
        if not repo_config:
            return False, None, None

        return True, repo_config["owner"], repo_config["repo"]

    else:
        # Fallback to local git repo
        ok, remote_url = run_git(["remote", "get-url", "origin"])
        if not ok or "github.com" not in remote_url:
            return False, None, None

        # Parse owner/repo from URL
        if remote_url.endswith(".git"):
            remote_url = remote_url[:-4]

        parts = remote_url.replace(":", "/").split("/")
        owner, repo = parts[-2], parts[-1]

        return True, owner, repo


@app.command("status")
def git_status():
    """Show current git status with style."""
    header("Git Repository Status")

    # Current branch
    ok, branch = run_git(["branch", "--show-current"])
    if ok:
        info(f"Branch: [bold]{branch}[/]")
    else:
        error("Not a git repository")
        return

    # Check if ahead/behind
    run_git(["fetch", "--quiet"])
    ok, status = run_git(["status", "-sb"])
    if ok:
        lines = status.split("\n")
        if len(lines) > 0:
            branch_info = lines[0]
            if "ahead" in branch_info:
                warning("You have unpushed commits")
            if "behind" in branch_info:
                warning("Remote has new commits (run git pull)")

    # Changed files
    ok, diff = run_git(["diff", "--stat", "--name-only"])
    ok2, staged = run_git(["diff", "--cached", "--name-only"])
    ok3, untracked = run_git(["ls-files", "--others", "--exclude-standard"])

    modified = [f for f in diff.split("\n") if f] if diff else []
    staged_files = [f for f in staged.split("\n") if f] if staged else []
    untracked_files = [f for f in untracked.split("\n") if f] if untracked else []

    if staged_files:
        console.print(f"\n[green]Staged ({len(staged_files)}):[/]")
        for f in staged_files[:5]:
            console.print(f"  [green]+[/] {f}")
        if len(staged_files) > 5:
            console.print(f"  ... and {len(staged_files) - 5} more")

    if modified:
        console.print(f"\n[yellow]Modified ({len(modified)}):[/]")
        for f in modified[:5]:
            console.print(f"  [yellow]~[/] {f}")
        if len(modified) > 5:
            console.print(f"  ... and {len(modified) - 5} more")

    if untracked_files:
        console.print(f"\n[dim]Untracked ({len(untracked_files)}):[/]")
        for f in untracked_files[:3]:
            console.print(f"  [dim]?[/] {f}")
        if len(untracked_files) > 3:
            console.print(f"  ... and {len(untracked_files) - 3} more")

    if not (modified or staged_files or untracked_files):
        success("Working directory clean")


@app.command("pr")
def create_pr(
    repo_name: Optional[str] = typer.Option(None, "--repo", "-r", help="Configured repository name"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="PR title"),
    body: Optional[str] = typer.Option(None, "--body", "-b", help="PR description"),
    from_branch: Optional[str] = typer.Option(None, "--from", help="Source branch (required if using --repo)"),
    base: str = typer.Option("main", "--base", help="Base branch"),
    draft: bool = typer.Option(False, "--draft", "-d", help="Create as draft PR"),
):
    """Create a pull request on GitHub.

    Run inside a git repo to auto-detect, or use --repo for configured repos.
    """
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        info("Set GITHUB_TOKEN env var or add to config: devops init")
        return

    # Resolve repository
    ok, owner, repo = resolve_repo(repo_name)

    if not ok:
        if repo_name:
            error(f"Repository '{repo_name}' not found in configuration")
            info("List repos: devops admin repo-list")
        else:
            error("Not in a git repository. Use --repo flag.")
            info("Example: devops git pr --repo backend --from feature-branch")
        return

    # Get branch
    if repo_name:
        # Using configured repo - require --from flag
        if not from_branch:
            error("When using --repo, you must specify --from <branch>")
            info("Example: devops git pr --repo backend --from feature-branch --base main")
            return
        branch = from_branch
    else:
        # Using local repo - get current branch
        ok, branch = run_git(["branch", "--show-current"])
        if not ok or branch == base:
            error(f"Cannot create PR from '{branch}' to '{base}'")
            return

    # If using local repo, push branch
    if not repo_name:
        # Push branch if needed
        info(f"Pushing branch '{branch}' to origin...")
        ok, output = run_git(["push", "-u", "origin", branch])
        if not ok and "rejected" in output:
            error("Failed to push branch. Pull latest changes first.")
            return

    # If using local repo, push branch
    if not repo_name:
        # Push branch if needed
        info(f"Pushing branch '{branch}' to origin...")
        ok, output = run_git(["push", "-u", "origin", branch])
        if not ok and "rejected" in output:
            error("Failed to push branch. Pull latest changes first.")
            return

    # Get PR title from last commit if not provided
    if not title:
        if not repo_name:
            ok, last_commit = run_git(["log", "-1", "--format=%s"])
            title = Prompt.ask("PR Title", default=last_commit if ok else branch)
        else:
            title = Prompt.ask("PR Title", default=f"Merge {branch} into {base}")

    # Get PR body
    if not body:
        if not repo_name:
            ok, commits = run_git(["log", f"{base}..HEAD", "--format=- %s"])
            default_body = f"## Changes\n{commits}\n" if ok and commits else ""
            body = Prompt.ask("PR Description (or press Enter)", default=default_body)
        else:
            body = Prompt.ask("PR Description (optional)", default="")

    # Create PR via GitHub API
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    data = {
        "title": title,
        "body": body,
        "head": branch,
        "base": base,
        "draft": draft,
    }

    try:
        resp = requests.post(url, json=data, headers=get_github_headers(token))

        if resp.status_code == 201:
            pr = resp.json()
            success(f"Pull request created: #{pr['number']}")
            console.print(f"\n[link={pr['html_url']}]{pr['html_url']}[/link]")
        elif resp.status_code == 422:
            result = resp.json()
            if "already exists" in str(result.get("errors", [])):
                warning("A pull request already exists for this branch")
                # Get existing PR
                prs_resp = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/pulls",
                    params={"head": f"{owner}:{branch}"},
                    headers=get_github_headers(token)
                )
                if prs_resp.ok and prs_resp.json():
                    pr = prs_resp.json()[0]
                    console.print(f"[link={pr['html_url']}]{pr['html_url']}[/link]")
            else:
                error(f"Failed to create PR: {result}")
        else:
            error(f"GitHub API error: {resp.status_code}")
    except requests.RequestException as e:
        error(f"Request failed: {e}")


@app.command("pipeline")
def pipeline_status(
    repo_name: Optional[str] = typer.Option(None, "--repo", "-r", help="Configured repository name"),
    branch: Optional[str] = typer.Option(None, "--branch", "-b", help="Branch name"),
):
    """Check CI/CD pipeline status (GitHub Actions).

    Use --repo to specify a configured repository, or run inside a git repo.
    """
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        info("Set GITHUB_TOKEN env var or add to config: devops init")
        return

    # Resolve repository
    ok, owner, repo = resolve_repo(repo_name)

    if not ok:
        if repo_name:
            error(f"Repository '{repo_name}' not found in configuration")
            info("List repos: devops admin repo-list")
            info("Add repo: devops admin repo-add")
        else:
            error("Not in a git repository. Use --repo flag to specify a configured repo.")
            info("Example: devops git pipeline --repo backend")
        return

    repo_full = f"{owner}/{repo}"

    # Get branch
    if not branch:
        if repo_name:
            # Use default branch from config
            repo_config = get_repo_config(repo_name)
            branch = repo_config.get("default_branch", "main")
        else:
            # Try to get current branch from local git
            ok, branch = run_git(["branch", "--show-current"])
            if not ok:
                branch = "main"

    header(f"Pipeline Status: {repo_full}")
    info(f"Branch: {branch}")

    try:
        # Get workflow runs
        url = f"https://api.github.com/repos/{repo_full}/actions/runs"
        params = {"branch": branch, "per_page": 5}
        resp = requests.get(url, params=params, headers=get_github_headers(token))

        if resp.status_code == 200:
            runs = resp.json().get("workflow_runs", [])
            if not runs:
                warning("No workflow runs found")
                return

            table = create_table(
                "Recent Workflow Runs",
                [("Workflow", "cyan"), ("Status", ""), ("Conclusion", ""), ("Started", "dim")]
            )

            for run in runs:
                status = run["status"]
                conclusion = run.get("conclusion") or "running"
                started = run["created_at"][:16].replace("T", " ")

                status_str = status_badge(conclusion if status == "completed" else status)
                table.add_row(run["name"], status, status_str, started)

            console.print(table)

            # Show latest run details
            latest = runs[0]
            if latest["status"] != "completed":
                info(f"\nLatest run in progress: {latest['html_url']}")
            elif latest.get("conclusion") == "failure":
                error(f"\nLatest run failed: {latest['html_url']}")
        else:
            error(f"Failed to fetch workflow runs: {resp.status_code}")
    except requests.RequestException as e:
        error(f"Request failed: {e}")


@app.command("prs")
def list_prs(
    repo_name: Optional[str] = typer.Option(None, "--repo", "-r", help="Configured repository name"),
    state: str = typer.Option("open", "--state", "-s", help="PR state: open, closed, all"),
    limit: int = typer.Option(10, "--limit", "-l", help="Number of PRs to show"),
):
    """List pull requests.

    Use --repo to specify a configured repository, or run inside a git repo.
    """
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        info("Set GITHUB_TOKEN env var or add to config: devops init")
        return

    # Resolve repository
    ok, owner, repo = resolve_repo(repo_name)

    if not ok:
        if repo_name:
            error(f"Repository '{repo_name}' not found in configuration")
            info("List repos: devops admin repo-list")
        else:
            error("Not in a git repository. Use --repo flag.")
            info("Example: devops git prs --repo backend")
        return

    repo_full = f"{owner}/{repo}"

    header(f"Pull Requests: {repo_full}")

    try:
        url = f"https://api.github.com/repos/{repo_full}/pulls"
        params = {"state": state, "per_page": limit}
        resp = requests.get(url, params=params, headers=get_github_headers(token))

        if resp.status_code == 200:
            prs = resp.json()
            if not prs:
                info(f"No {state} pull requests")
                return

            table = create_table(
                f"{state.title()} PRs",
                [("#", "cyan"), ("Title", ""), ("Author", "dim"), ("Branch", "dim")]
            )

            for pr in prs:
                table.add_row(
                    str(pr["number"]),
                    pr["title"][:50] + ("..." if len(pr["title"]) > 50 else ""),
                    pr["user"]["login"],
                    pr["head"]["ref"][:20]
                )

            console.print(table)
        else:
            error(f"Failed to fetch PRs: {resp.status_code}")
    except requests.RequestException as e:
        error(f"Request failed: {e}")


@app.command("trigger")
def trigger_workflow(
    workflow: str = typer.Argument(..., help="Workflow file name or ID"),
    repo_name: Optional[str] = typer.Option(None, "--repo", "-r", help="Configured repository name"),
    branch: str = typer.Option("main", "--branch", "-b", help="Branch to run on"),
):
    """Trigger a GitHub Actions workflow.

    Use --repo to specify a configured repository, or run inside a git repo.
    """
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        info("Set GITHUB_TOKEN env var or add to config: devops init")
        return

    # Resolve repository
    ok, owner, repo = resolve_repo(repo_name)

    if not ok:
        if repo_name:
            error(f"Repository '{repo_name}' not found in configuration")
            info("List repos: devops admin repo-list")
        else:
            error("Not in a git repository. Use --repo flag.")
            info("Example: devops git trigger deploy.yml --repo backend")
        return

    repo_full = f"{owner}/{repo}"

    # Trigger workflow
    url = f"https://api.github.com/repos/{repo_full}/actions/workflows/{workflow}/dispatches"
    data = {"ref": branch}

    try:
        resp = requests.post(url, json=data, headers=get_github_headers(token))

        if resp.status_code == 204:
            success(f"Workflow '{workflow}' triggered on branch '{branch}'")
            info(f"View at: https://github.com/{repo_full}/actions")
        elif resp.status_code == 404:
            error(f"Workflow '{workflow}' not found. Make sure workflow_dispatch is enabled.")
        else:
            error(f"Failed to trigger workflow: {resp.status_code}")
    except requests.RequestException as e:
        error(f"Request failed: {e}")


@app.command("repos")
def list_repos_command():
    """List all configured repositories.

    Shows repositories configured by admin for Git/CI operations.
    """
    repos = load_repos()

    if not repos:
        warning("No repositories configured")
        info("Ask your admin to configure repos with: devops admin repo-discover")
        return

    header("Available Repositories")

    table = create_table(
        "",
        [("Name", "cyan"), ("Owner/Repo", ""), ("Branch", "dim"), ("Description", "dim")]
    )

    for name, repo in repos.items():
        owner_repo = f"{repo['owner']}/{repo['repo']}"
        branch = repo.get("default_branch", "main")
        description = repo.get("description", "")[:50]

        table.add_row(
            name,
            owner_repo,
            branch,
            description
        )

    console.print(table)
    info(f"\nTotal: {len(repos)} repositories")
    console.print()
    info("Use --repo flag with any git command:")
    info("  devops git pipeline --repo backend")
    info("  devops git prs --repo frontend")
    info("  devops git pr --repo api --from feature-x --base main")


@app.command("quick-commit")
def quick_commit(
    message: str = typer.Argument(..., help="Commit message"),
    push: bool = typer.Option(True, "--push/--no-push", "-p", help="Push after commit"),
):
    """Quick add, commit, and push."""
    # Add all changes
    ok, _ = run_git(["add", "-A"])
    if not ok:
        error("Failed to stage changes")
        return

    # Check if there are changes to commit
    ok, status = run_git(["status", "--porcelain"])
    if not status:
        warning("No changes to commit")
        return

    # Commit
    ok, output = run_git(["commit", "-m", message])
    if not ok:
        error(f"Commit failed: {output}")
        return
    success("Changes committed")

    # Push
    if push:
        info("Pushing to remote...")
        ok, output = run_git(["push"])
        if ok:
            success("Pushed to remote")
        else:
            error(f"Push failed: {output}")
            info("Try: git push -u origin <branch>")
