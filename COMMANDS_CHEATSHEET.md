# DevOps CLI - Commands Cheatsheet

Quick reference for all commands.

---

## Admin Commands (Cloud Engineers Only)

```bash
# ══════════════════════════════════════════════════════════════
#                         INITIALIZATION
# ══════════════════════════════════════════════════════════════

devops admin init                              # Initialize CLI for org

# ══════════════════════════════════════════════════════════════
#                        USER MANAGEMENT
# ══════════════════════════════════════════════════════════════

devops admin user-add --email x --role admin   # Create admin user
devops admin user-add --email x --role developer  # Create developer
devops admin user-list                         # List all users
devops admin user-remove <email>               # Delete user permanently
devops admin user-deactivate <email>           # Disable user temporarily
devops admin user-activate <email>             # Re-enable user
devops admin user-reset-token <email>          # Generate new token
devops admin audit-logs                        # View auth audit logs

# ══════════════════════════════════════════════════════════════
#                      APP MANAGEMENT
# ══════════════════════════════════════════════════════════════

devops admin app-add                           # Add app (interactive)
devops admin app-list                          # List all apps
devops admin app-show <name>                   # View app config
devops admin app-edit <name>                   # Edit in $EDITOR
devops admin app-remove <name>                 # Remove app

# ══════════════════════════════════════════════════════════════
#                     SERVER MANAGEMENT
# ══════════════════════════════════════════════════════════════

devops admin server-add                        # Add SSH server
devops admin server-list                       # List servers
devops admin server-remove <name>              # Remove server

# ══════════════════════════════════════════════════════════════
#                       AWS MANAGEMENT
# ══════════════════════════════════════════════════════════════

devops admin aws-configure                     # Set AWS credentials
devops admin aws-add-role -n name -a arn       # Add IAM role
devops admin aws-list-roles                    # List roles
devops admin aws-remove-role <name>            # Remove role
devops admin aws-show                          # Show credentials (masked)
devops admin aws-test                          # Test credentials
devops admin aws-remove                        # Remove credentials

# ══════════════════════════════════════════════════════════════
#                      TEAM MANAGEMENT
# ══════════════════════════════════════════════════════════════

devops admin team-add --name <name>            # Create team
devops admin team-list                         # List teams
devops admin team-remove <name>                # Remove team

# ══════════════════════════════════════════════════════════════
#                    REPO MANAGEMENT
# ══════════════════════════════════════════════════════════════

devops admin repo-discover --source org --name x  # Auto-discover repos
devops admin repo-add --owner x --repo y       # Add single repo
devops admin repo-list                         # List repos
devops admin repo-show <name>                  # View repo config
devops admin repo-remove <name>                # Remove repo
devops admin repo-refresh <name>               # Sync from GitHub

# ══════════════════════════════════════════════════════════════
#                      EXPORT/IMPORT
# ══════════════════════════════════════════════════════════════

devops admin export -o config.yaml             # Export config
devops admin import config.yaml                # Import config
devops admin status                            # Show config status
```

---

## Developer Commands

```bash
# ══════════════════════════════════════════════════════════════
#                       AUTHENTICATION
# ══════════════════════════════════════════════════════════════

devops auth login                              # Login (interactive)
devops auth login --email x --token y          # Login with flags
devops auth logout                             # End session
devops auth status                             # Check login status
devops auth whoami                             # Show current user
devops auth refresh                            # Extend session (+8h)

# ══════════════════════════════════════════════════════════════
#                       APPLICATIONS
# ══════════════════════════════════════════════════════════════

devops app list                                # List available apps
devops app logs <name>                         # View logs
devops app logs <name> --follow                # Tail logs (live)
devops app logs <name> --lines 100             # Last 100 lines
devops app health <name>                       # Check health
devops app info <name>                         # Show app details

# ══════════════════════════════════════════════════════════════
#                          SSH
# ══════════════════════════════════════════════════════════════

devops ssh list                                # List servers
devops ssh connect <name>                      # SSH to server
devops ssh exec <name> "command"               # Run remote command

# ══════════════════════════════════════════════════════════════
#                          AWS
# ══════════════════════════════════════════════════════════════

devops aws logs <app>                          # CloudWatch logs
devops aws logs <app> --follow                 # Tail CloudWatch
devops aws cloudwatch <log-group>              # Direct log group

# ══════════════════════════════════════════════════════════════
#                          GIT
# ══════════════════════════════════════════════════════════════

devops git status                              # Enhanced status
devops git pr create                           # Create PR
devops git pr list                             # List open PRs
devops git pipeline                            # CI/CD status

# ══════════════════════════════════════════════════════════════
#                       MONITORING
# ══════════════════════════════════════════════════════════════

devops monitor                                 # Live dashboard
devops monitor --once                          # Single check
devops monitor list                            # List resources
devops monitor add-website -n x -u url         # Add website
devops monitor add-app -n x -t docker -i name  # Add app
devops monitor add-server -n x -H host         # Add server
devops monitor remove <name>                   # Remove resource

# ══════════════════════════════════════════════════════════════
#                        GENERAL
# ══════════════════════════════════════════════════════════════

devops status                                  # Configuration status
devops doctor                                  # Diagnose issues
devops version                                 # Show version
devops --help                                  # All commands
```

---

## Common Workflows

### Daily Developer Workflow
```bash
devops auth login                    # Start of day
devops app logs backend --follow     # Watch logs while working
devops app health backend            # Quick health check
devops auth logout                   # End of day
```

### Debugging an Issue
```bash
devops app logs backend --lines 500  # Recent logs
devops app health backend            # Health check
devops ssh connect web-prod-1        # SSH if needed
devops monitor                       # Check all services
```

### Admin Adding New Developer
```bash
devops admin user-add --email new@co.com --role developer
# Share token with developer securely
# Developer runs: devops auth login --email new@co.com --token DVC-xxx
```

### Admin Adding New App
```bash
devops admin app-add                 # Interactive setup
devops app list                      # Verify added
devops app logs new-app              # Test logs work
```

---

## Access Control Summary

| Command Group | Admin | Developer |
|---------------|:-----:|:---------:|
| `devops admin *` | ✅ | ❌ |
| `devops auth *` | ✅ | ✅ |
| `devops app *` | ✅ | ✅ |
| `devops ssh *` | ✅ | ✅ |
| `devops aws *` | ✅ | ✅ |
| `devops git *` | ✅ | ✅ |
| `devops monitor *` | ✅ | ✅ |
| `devops status` | ✅ | ✅ |
| `devops doctor` | ✅ | ✅ |

---

## Error Messages Quick Fix

| Error | Fix |
|-------|-----|
| "CLI not initialized" | `devops admin init` |
| "Login required" | `devops auth login` |
| "Access denied" | You need admin role |
| "Invalid token" | Check token or get new one |
| "No apps configured" | Ask admin to add apps |
| "Session expired" | `devops auth login` again |

---

*Keep this cheatsheet handy for quick reference!*
