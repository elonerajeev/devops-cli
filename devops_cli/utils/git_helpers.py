"""Git operation utilities for DevOps CLI."""

import subprocess
from typing import Tuple


def run_git(args: list[str], capture: bool = True) -> Tuple[bool, str]:
    """Run a git command and return success status and output.

    Args:
        args: Git command arguments (without 'git' prefix)
        capture: Whether to capture output (default: True)

    Returns:
        Tuple of (success, output)
            - success: True if command succeeded (return code 0)
            - output: Combined stdout and stderr output

    Examples:
        >>> run_git(['status'])
        (True, 'On branch main...')
        >>> run_git(['add', '.'])
        (True, '')
    """
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=capture, text=True, check=False
        )
        output = result.stdout + result.stderr
        return result.returncode == 0, output.strip()
    except FileNotFoundError:
        return False, "Git is not installed"


def get_current_branch() -> str:
    """Get the current git branch name.

    Returns:
        Branch name or empty string if not in a git repo
    """
    success, output = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    return output if success else ""


def is_git_repo() -> bool:
    """Check if current directory is a git repository.

    Returns:
        True if in a git repo, False otherwise
    """
    success, _ = run_git(["rev-parse", "--git-dir"])
    return success
