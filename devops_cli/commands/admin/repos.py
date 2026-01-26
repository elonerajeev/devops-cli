"""Repository management commands for admin."""

import os
import tempfile
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

import typer
import yaml
from rich.prompt import Prompt, Confirm

from devops_cli.commands.admin.base import (
    console,
    load_config,
    load_repos,
    save_repos,
    get_repo_config,
    add_repo,
    remove_repo,
    fetch_repo_from_github,
    discover_org_repos,
    discover_user_repos,
    validate_github_token,
    validate_repo_name,
    success,
    error,
    warning,
    info,
    header,
    create_table,
)

app = typer.Typer()


def discover_repos(
    source: str = typer.Option(
        ...,
        "--source",
        "-s",
        prompt="Source type (org/user)",
        help="Discover from org or user repos",
    ),
    name: str = typer.Option(
        ...,
        "--name",
        "-n",
        prompt="Organization or username",
        help="GitHub organization or username",
    ),
):
    """Auto-discover all repositories from GitHub org or user."""
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        info("Set GITHUB_TOKEN env var or add to config: devops init")
        return

    is_valid, err_msg = validate_github_token(token)
    if not is_valid:
        error(f"GitHub token validation failed: {err_msg}")
        info("Please check your token at: https://github.com/settings/tokens")
        info("Required scope: 'repo'")
        return

    header(f"Discovering repositories from {source}: {name}")

    if source.lower() in ["org", "organization"]:
        repos = discover_org_repos(name, token)
    elif source.lower() == "user":
        repos = discover_user_repos(name, token)
    else:
        error("Source must be 'org' or 'user'")
        return

    if not repos:
        warning("No repositories found or access denied")
        info("Make sure your GitHub token has 'repo' scope")
        return

    success(f"Found {len(repos)} repositories!")
    console.print()

    table = create_table(
        "Discovered Repositories",
        [
            ("Name", "cyan"),
            ("Owner", ""),
            ("Visibility", "yellow"),
            ("Language", "dim"),
        ],
    )

    for repo in repos[:20]:
        visibility = "[red]private[/]" if repo["private"] else "[green]public[/]"
        table.add_row(
            repo["name"], repo["owner"], visibility, repo.get("language", "Unknown")
        )

    console.print(table)

    if len(repos) > 20:
        console.print(f"\n... and {len(repos) - 20} more")

    console.print()

    add_all = Confirm.ask(
        "Add all discovered repositories to configuration?", default=False
    )

    if add_all:
        existing_repos = load_repos()
        added_count = 0

        for repo in repos:
            repo_name = repo["name"]

            if repo_name in existing_repos:
                repo_name = f"{repo['owner']}/{repo['name']}"

            existing_repos[repo_name] = {
                "owner": repo["owner"],
                "repo": repo["name"],
                "description": repo["description"],
                "default_branch": repo["default_branch"],
                "visibility": repo["visibility"],
                "private": repo["private"],
                "language": repo.get("language"),
                "url": repo["url"],
                "created_at": repo.get("created_at"),
                "added_at": datetime.now().isoformat(),
                "auto_discovered": True,
            }
            added_count += 1

        save_repos(existing_repos)
        success(f"Added {added_count} repositories to configuration!")
        info("\nDevelopers can now use: devops git repos")

    else:
        info("Add repositories individually with: devops admin repo-add")
        info("Example: devops admin repo-add --name myrepo --owner myorg --repo myrepo")


def add_repository(
    name: str = typer.Option(
        None, "--name", "-n", help="Friendly name for the repo (e.g., backend)"
    ),
    owner: str = typer.Option(None, "--owner", "-o", help="GitHub owner/org"),
    repo: str = typer.Option(None, "--repo", "-r", help="Repository name"),
    auto_fetch: bool = typer.Option(
        True, "--auto-fetch/--no-fetch", help="Auto-fetch details from GitHub"
    ),
):
    """Add a specific repository to configuration."""
    config = load_config()
    token = config.get("github", {}).get("token")

    if not name:
        name = Prompt.ask("Repository friendly name (e.g., backend, frontend)")
    if not owner:
        owner = Prompt.ask("GitHub owner/organization")
    if not repo:
        repo = Prompt.ask("Repository name", default=name)

    is_valid, err_msg = validate_repo_name(name)
    if not is_valid:
        error(f"Invalid repository name: {err_msg}")
        return

    existing_repos = load_repos()
    if name in existing_repos:
        error(f"Repository '{name}' already exists in configuration")
        info(f"Use: devops admin repo-show {name}")
        return

    if not token and auto_fetch:
        warning(
            "GitHub token not configured. Will add repo without auto-fetching details."
        )
        auto_fetch = False
    elif token and auto_fetch:
        is_valid, err_msg = validate_github_token(token)
        if not is_valid:
            warning(f"GitHub token validation failed: {err_msg}")
            warning("Will add repo without auto-fetching details.")
            auto_fetch = False

    header(f"Adding repository: {owner}/{repo}")

    repo_config = {
        "owner": owner,
        "repo": repo,
        "added_at": datetime.now().isoformat(),
    }

    if auto_fetch and token:
        info("Fetching repository details from GitHub...")
        github_data = fetch_repo_from_github(owner, repo, token)

        if github_data and "error" not in github_data:
            repo_config.update(
                {
                    "description": github_data.get("description", "No description"),
                    "default_branch": github_data.get("default_branch", "main"),
                    "visibility": github_data.get("visibility", "private"),
                    "private": github_data.get("private", True),
                    "language": github_data.get("language"),
                    "url": github_data.get("url"),
                    "created_at": github_data.get("created_at"),
                    "auto_fetched": True,
                }
            )
            success("Repository details fetched from GitHub!")
            console.print()
            console.print(f"  Description: {repo_config['description']}")
            console.print(f"  Default Branch: {repo_config['default_branch']}")
            console.print(f"  Language: {repo_config.get('language', 'Unknown')}")
            console.print(f"  Visibility: {repo_config['visibility']}")
        elif github_data and "error" in github_data:
            error(f"GitHub API error: {github_data.get('message', 'Unknown error')}")
            if github_data.get("error") == "rate_limit":
                info("GitHub rate limit exceeded. Try again later or use manual entry.")
            if not Confirm.ask("Add repository anyway (without GitHub data)?"):
                info("Cancelled")
                return
            repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
            repo_config["description"] = Prompt.ask(
                "Description (optional)", default=""
            )
        else:
            error("Could not fetch repo details from GitHub")
            info("Repository might not exist or token lacks access")
            if not Confirm.ask("Add repository anyway (without GitHub data)?"):
                info("Cancelled")
                return
            repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
            repo_config["description"] = Prompt.ask(
                "Description (optional)", default=""
            )
    else:
        repo_config["default_branch"] = Prompt.ask("Default branch", default="main")
        repo_config["description"] = Prompt.ask("Description (optional)", default="")

    add_repo(
        name,
        owner,
        repo,
        **{k: v for k, v in repo_config.items() if k not in ["owner", "repo"]},
    )

    success(f"Repository '{name}' added!")
    console.print()
    info("Developers can now use:")
    info(f"  devops git pipeline --repo {name}")
    info(f"  devops git pr --repo {name}")
    info(f"  devops git prs --repo {name}")


def list_repositories():
    """List all configured repositories."""
    repos = load_repos()

    if not repos:
        warning("No repositories configured")
        info("Discover repos: devops admin repo-discover")
        info("Or add manually: devops admin repo-add")
        return

    header("Configured Repositories")

    table = create_table(
        "",
        [
            ("Name", "cyan"),
            ("Owner/Repo", ""),
            ("Branch", "dim"),
            ("Language", "dim"),
            ("Visibility", "yellow"),
        ],
    )

    for name, repo in repos.items():
        owner_repo = f"{repo['owner']}/{repo['repo']}"
        branch = repo.get("default_branch", "main")
        language = repo.get("language", "Unknown")

        vis_color = (
            "[red]private[/]" if repo.get("private", True) else "[green]public[/]"
        )

        table.add_row(name, owner_repo[:40], branch, language, vis_color)

    console.print(table)
    info(f"\nTotal: {len(repos)} repositories")
    console.print()
    info("View details: devops admin repo-show <name>")


def show_repository(
    name: str = typer.Argument(..., help="Repository name"),
):
    """Show detailed configuration for a repository."""
    repo = get_repo_config(name)

    if not repo:
        error(f"Repository '{name}' not found")
        info("List repos: devops admin repo-list")
        return

    header(f"Repository: {name}")
    console.print()
    console.print(yaml.dump(repo, default_flow_style=False))


def remove_repository(
    name: str = typer.Argument(..., help="Repository name to remove"),
):
    """Remove a repository from configuration."""
    if not get_repo_config(name):
        error(f"Repository '{name}' not found")
        return

    if not Confirm.ask(f"Remove repository '{name}' from configuration?"):
        info("Cancelled")
        return

    if remove_repo(name):
        success(f"Repository '{name}' removed")
    else:
        error(f"Failed to remove repository '{name}'")


def refresh_repository(
    name: str = typer.Argument(..., help="Repository name to refresh"),
):
    """Refresh repository details from GitHub."""
    config = load_config()
    token = config.get("github", {}).get("token")

    if not token:
        error("GitHub token not configured")
        return

    repo = get_repo_config(name)
    if not repo:
        error(f"Repository '{name}' not found")
        return

    owner = repo["owner"]
    repo_name = repo["repo"]

    header(f"Refreshing: {owner}/{repo_name}")

    github_data = fetch_repo_from_github(owner, repo_name, token)

    if not github_data:
        error("Could not fetch repository details from GitHub")
        info("Repository might not exist or token lacks access")
        return

    repos = load_repos()
    repos[name].update(
        {
            "description": github_data.get("description", "No description"),
            "default_branch": github_data.get("default_branch", "main"),
            "visibility": github_data.get("visibility", "private"),
            "private": github_data.get("private", True),
            "language": github_data.get("language"),
            "url": github_data.get("url"),
            "created_at": github_data.get("created_at"),
            "last_refreshed": datetime.now().isoformat(),
        }
    )

    save_repos(repos)

    success(f"Repository '{name}' refreshed from GitHub!")
    console.print()
    console.print(f"  Description: {github_data['description']}")
    console.print(f"  Default Branch: {github_data['default_branch']}")
    console.print(f"  Language: {github_data.get('language', 'Unknown')}")
    console.print(f"  Visibility: {github_data['visibility']}")


def edit_repository(
    name: str = typer.Argument(..., help="Repository name to edit"),
):
    """Edit a repository configuration."""
    repo = get_repo_config(name)
    if not repo:
        error(f"Repository '{name}' not found")
        return

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(repo, f, default_flow_style=False)
        temp_file = f.name

    editor = os.environ.get("EDITOR", "nano")
    subprocess.run([editor, temp_file])

    with open(temp_file) as f:
        updated = yaml.safe_load(f)

    os.unlink(temp_file)

    if Confirm.ask("Save changes?"):
        repos = load_repos()
        repos[name] = updated
        save_repos(repos)
        success(f"Repository '{name}' updated")
    else:
        info("Changes discarded")
