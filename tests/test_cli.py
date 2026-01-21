"""Tests for CLI commands."""

import pytest
from typer.testing import CliRunner
from devops_cli.main import app

runner = CliRunner()


class TestCLI:
    """Test CLI basic functionality."""

    def test_version(self):
        """Test version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "DevOps CLI" in result.stdout

    def test_help(self):
        """Test help command."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "DevOps CLI" in result.stdout

    def test_status(self):
        """Test status command."""
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Status" in result.stdout


class TestGitCommands:
    """Test git command group."""

    def test_git_help(self):
        """Test git help."""
        result = runner.invoke(app, ["git", "--help"])
        assert result.exit_code == 0
        assert "Git" in result.stdout

    def test_git_status(self):
        """Test git status command."""
        result = runner.invoke(app, ["git", "status"])
        # May fail if not in git repo, that's ok
        assert result.exit_code in [0, 1]


class TestHealthCommands:
    """Test health command group."""

    def test_health_help(self):
        """Test health help."""
        result = runner.invoke(app, ["health", "--help"])
        assert result.exit_code == 0
        assert "Health" in result.stdout

    def test_health_check_no_config(self):
        """Test health check without config."""
        result = runner.invoke(app, ["health", "check"])
        assert result.exit_code == 0
        # Should warn about no services

    def test_health_port(self):
        """Test port check."""
        result = runner.invoke(app, ["health", "port", "localhost", "22"])
        # May succeed or fail depending on SSH being available
        assert result.exit_code == 0


class TestLogsCommands:
    """Test logs command group."""

    def test_logs_help(self):
        """Test logs help."""
        result = runner.invoke(app, ["logs", "--help"])
        assert result.exit_code == 0
        assert "logs" in result.stdout.lower()

    def test_logs_list(self):
        """Test logs list command."""
        result = runner.invoke(app, ["logs", "list"])
        assert result.exit_code == 0


class TestDeployCommands:
    """Test deploy command group."""

    def test_deploy_help(self):
        """Test deploy help."""
        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code == 0
        assert "Deployment" in result.stdout


class TestSSHCommands:
    """Test SSH command group."""

    def test_ssh_help(self):
        """Test SSH help."""
        result = runner.invoke(app, ["ssh", "--help"])
        assert result.exit_code == 0
        assert "SSH" in result.stdout

    def test_ssh_list_no_config(self):
        """Test SSH list without config."""
        result = runner.invoke(app, ["ssh", "list"])
        assert result.exit_code == 0


class TestSecretsCommands:
    """Test secrets command group."""

    def test_secrets_help(self):
        """Test secrets help."""
        result = runner.invoke(app, ["secrets", "--help"])
        assert result.exit_code == 0
        assert "Secrets" in result.stdout

    def test_secrets_init(self):
        """Test secrets init command."""
        result = runner.invoke(app, ["secrets", "init"])
        assert result.exit_code == 0


class TestAWSCommands:
    """Test AWS logs command group."""

    def test_aws_help(self):
        """Test AWS help."""
        result = runner.invoke(app, ["aws", "--help"])
        assert result.exit_code == 0
        assert "AWS" in result.stdout or "CloudWatch" in result.stdout

    def test_aws_configure(self):
        """Test AWS configure command."""
        result = runner.invoke(app, ["aws", "configure"])
        assert result.exit_code == 0
        assert "aws" in result.stdout.lower()


class TestAdminCommands:
    """Test admin command group (for Cloud Engineers)."""

    def test_admin_help(self):
        """Test admin help."""
        result = runner.invoke(app, ["admin", "--help"])
        assert result.exit_code == 0
        assert "Admin" in result.stdout or "Configure" in result.stdout

    def test_admin_status(self):
        """Test admin status."""
        result = runner.invoke(app, ["admin", "status"])
        assert result.exit_code == 0

    def test_admin_app_list(self):
        """Test admin app-list."""
        result = runner.invoke(app, ["admin", "app-list"])
        assert result.exit_code == 0

    def test_admin_server_list(self):
        """Test admin server-list."""
        result = runner.invoke(app, ["admin", "server-list"])
        assert result.exit_code == 0

    def test_admin_aws_list_roles(self):
        """Test admin aws-list-roles."""
        result = runner.invoke(app, ["admin", "aws-list-roles"])
        assert result.exit_code == 0


class TestAppCommands:
    """Test app command group (for Developers)."""

    def test_app_help(self):
        """Test app help."""
        result = runner.invoke(app, ["app", "--help"])
        assert result.exit_code == 0
        assert "Applications" in result.stdout or "logs" in result.stdout

    def test_app_list(self):
        """Test app list."""
        result = runner.invoke(app, ["app", "list"])
        assert result.exit_code == 0

    def test_app_health_no_apps(self):
        """Test app health without apps configured."""
        result = runner.invoke(app, ["app", "health"])
        assert result.exit_code == 0


class TestAuthCommands:
    """Test auth command group."""

    def test_auth_help(self):
        """Test auth help."""
        result = runner.invoke(app, ["auth", "--help"])
        assert result.exit_code == 0
        assert "login" in result.stdout.lower()

    def test_auth_status(self):
        """Test auth status command."""
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0

    def test_auth_whoami_not_logged_in(self):
        """Test whoami when not logged in."""
        result = runner.invoke(app, ["auth", "whoami"])
        # Should fail or show error when not logged in
        assert result.exit_code in [0, 1]

    def test_admin_user_list(self):
        """Test admin user-list command."""
        result = runner.invoke(app, ["admin", "user-list"])
        assert result.exit_code == 0

    def test_admin_audit_logs(self):
        """Test admin audit-logs command."""
        result = runner.invoke(app, ["admin", "audit-logs"])
        assert result.exit_code == 0
