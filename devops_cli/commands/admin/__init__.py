"""Admin commands package for Cloud Engineers.

This package provides commands for cloud engineers/DevOps to:
- Add/remove applications (EC2, ECS, Lambda, etc.)
- Add/remove servers for SSH access
- Configure AWS IAM roles and credentials
- Manage team access and permissions
- Set up log sources and health checks

Organized into submodules for maintainability.
"""

import typer

from devops_cli.commands.admin.base import (
    check_admin_access,
    console,
    auth,
    TEMPLATES_DIR,
    ADMIN_CONFIG_DIR,
    # Re-export for backward compatibility
    load_apps_config,
    save_apps_config,
    load_servers_config,
    save_servers_config,
    load_aws_config,
    save_aws_config,
    load_teams_config,
    save_teams_config,
    load_websites_config,
    save_websites_config,
    SECRETS_DIR,
)

# Import submodules
from devops_cli.commands.admin import apps as apps_module
from devops_cli.commands.admin import servers as servers_module
from devops_cli.commands.admin import websites as websites_module
from devops_cli.commands.admin import teams as teams_module
from devops_cli.commands.admin import aws as aws_module
from devops_cli.commands.admin import users as users_module
from devops_cli.commands.admin import repos as repos_module
from devops_cli.commands.admin import core as core_module

# Create main admin app
app = typer.Typer(help="Admin commands for Cloud Engineers to configure the CLI")


@app.callback()
def admin_callback(ctx: typer.Context):
    """Verify admin access before running admin commands."""
    check_admin_access(ctx)


# ==================== Register All Commands ====================

# Init
app.command("init")(core_module.admin_init)

# Apps
app.command("app-add")(apps_module.add_app)
app.command("app-list")(apps_module.list_apps)
app.command("app-show")(apps_module.show_app)
app.command("app-remove")(apps_module.remove_app)
app.command("app-edit")(apps_module.edit_app)

# Servers
app.command("server-add")(servers_module.add_server)
app.command("server-list")(servers_module.list_servers)
app.command("server-show")(servers_module.show_server)
app.command("server-remove")(servers_module.remove_server)
app.command("server-edit")(servers_module.edit_server)

# Websites
app.command("website-add")(websites_module.add_website)
app.command("website-list")(websites_module.list_websites)
app.command("website-show")(websites_module.show_website)
app.command("website-remove")(websites_module.remove_website)
app.command("website-edit")(websites_module.edit_website)

# Teams
app.command("team-add")(teams_module.add_team)
app.command("team-list")(teams_module.list_teams)
app.command("team-show")(teams_module.show_team)
app.command("team-remove")(teams_module.remove_team)
app.command("team-edit")(teams_module.edit_team)

# AWS Role Management
app.command("aws-add-role")(aws_module.add_aws_role)
app.command("aws-list-roles")(aws_module.list_aws_roles)
app.command("aws-remove-role")(aws_module.remove_aws_role)
app.command("aws-roles-import")(aws_module.import_aws_roles)
app.command("aws-roles-export-template")(aws_module.export_aws_roles_template)
app.command("aws-roles-export")(aws_module.export_aws_roles)
app.command("aws-set-credentials")(aws_module.set_aws_credentials)

# AWS Credentials Management
app.command("aws-configure")(aws_module.configure_aws_credentials)
app.command("aws-show")(aws_module.show_aws_credentials)
app.command("aws-test")(aws_module.test_aws_credentials)
app.command("aws-remove")(aws_module.remove_aws_credentials)
app.command("aws-import")(aws_module.import_aws_credentials)
app.command("aws-export-template")(aws_module.export_aws_template)

# User Management
app.command("user-add")(users_module.add_user)
app.command("user-list")(users_module.list_users)
app.command("user-remove")(users_module.remove_user)
app.command("user-deactivate")(users_module.deactivate_user)
app.command("user-activate")(users_module.activate_user)
app.command("user-reset-token")(users_module.reset_user_token)
app.command("users-import")(users_module.import_users)
app.command("users-export-template")(users_module.export_users_template)
app.command("users-export")(users_module.export_users)
app.command("audit-logs")(users_module.view_audit_logs)

# Repository Management
app.command("repo-discover")(repos_module.discover_repos)
app.command("repo-add")(repos_module.add_repository)
app.command("repo-list")(repos_module.list_repositories)
app.command("repo-show")(repos_module.show_repository)
app.command("repo-remove")(repos_module.remove_repository)
app.command("repo-refresh")(repos_module.refresh_repository)
app.command("repo-edit")(repos_module.edit_repository)

# Export/Import
app.command("export")(core_module.export_config)
app.command("import")(core_module.import_config)

# Status
app.command("status")(core_module.admin_status)

# Templates
app.command("templates")(core_module.manage_templates)

# Validation
app.command("validate")(core_module.validate_config)
