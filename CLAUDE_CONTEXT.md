# DevOps CLI - Context for Development

This document provides context for continuing development on the DevOps CLI.

---

## Project Overview

**DevOps CLI** is a Python CLI tool built with Typer + Rich designed as a **template** for organizations to manage their DevOps workflows.

### Key Design Principles
- **Template-based**: No hardcoded org data - admins configure everything
- **Role-based access**: Admin configures, developers use
- **Friendly errors**: Clear messages when things aren't configured
- **Scalable**: Works for 5 or 500 developers

---

## Project Structure

```
devops-cli/
├── devops_cli/
│   ├── __init__.py          # Version info
│   ├── main.py              # Entry point, CLI app
│   ├── commands/            # Command modules
│   │   ├── admin.py         # Admin: user/app/server management
│   │   ├── app.py           # Developer: app logs, health
│   │   ├── auth.py          # Authentication commands
│   │   ├── monitor.py       # Real-time monitoring dashboard
│   │   ├── git.py           # Git & CI/CD operations
│   │   ├── deploy.py        # Deployment commands
│   │   ├── ssh.py           # SSH server management
│   │   ├── secrets.py       # Secrets management
│   │   ├── health.py        # Health checks
│   │   ├── logs.py          # Log viewing
│   │   └── aws_logs.py      # AWS CloudWatch integration
│   ├── auth/
│   │   └── manager.py       # Token-based auth system
│   ├── config/
│   │   ├── settings.py      # Config management
│   │   ├── repos.py         # Repository config
│   │   └── aws_credentials.py
│   ├── monitoring/          # Monitoring module
│   │   ├── config.py        # Monitor configuration
│   │   ├── checker.py       # Health checkers
│   │   └── dashboard.py     # Rich Live dashboard
│   └── utils/
│       ├── output.py        # Pretty printing
│       └── config_validator.py  # Config validation & friendly errors
├── tests/                   # Test files
├── pyproject.toml          # Project config
├── requirements.txt        # Dependencies
└── README.md               # Documentation
```

---

## Configuration Location

All runtime config stored at: `~/.devops-cli/`

```
~/.devops-cli/
├── apps.yaml           # Applications config
├── servers.yaml        # SSH servers config
├── aws.yaml            # AWS roles config
├── teams.yaml          # Team permissions
├── monitoring.yaml     # Monitoring resources
├── config.yaml         # General config
├── auth/               # Authentication data (secured)
│   ├── users.json      # Registered users (hashed tokens)
│   ├── sessions.json   # Active sessions
│   └── audit.log       # Auth audit log
└── secrets/            # Encrypted secrets
```

---

## How It Works

### For New Organizations

1. **Admin initializes CLI:**
   ```bash
   devops admin init
   ```

2. **Admin adds applications:**
   ```bash
   devops admin app-add
   ```

3. **Admin adds servers:**
   ```bash
   devops admin server-add
   ```

4. **Admin registers developers:**
   ```bash
   devops admin user-add --email dev@company.com
   # Returns a token for the developer
   ```

5. **Developer logs in:**
   ```bash
   devops auth login
   # Enter email and token
   ```

6. **Developer uses CLI:**
   ```bash
   devops app list
   devops app logs <app-name>
   devops monitor
   ```

---

## Commands Reference

### General
```bash
devops status           # Show configuration status
devops doctor           # Check CLI health
devops version          # Show version
```

### For Developers
```bash
devops auth login       # Login with token
devops auth status      # Check session
devops auth logout      # End session

devops app list         # List available apps
devops app logs <app>   # View logs (requires auth)
devops app health <app> # Check app health
devops app info <app>   # Show app details

devops monitor          # Real-time dashboard
devops monitor --once   # Single check
```

### For Admins/Cloud Engineers
```bash
devops admin init                    # Initialize for org
devops admin user-add --email X      # Register user
devops admin user-list               # List users
devops admin app-add                 # Add application
devops admin server-add              # Add SSH server
devops admin aws-add-role            # Add AWS IAM role
devops admin audit-logs              # View auth logs
```

### Monitoring
```bash
devops monitor                       # Live dashboard
devops monitor add-website -n X -u Y # Add website
devops monitor add-app -n X -t Y -i Z# Add application
devops monitor add-server -n X -H Y  # Add server
devops monitor list                  # List resources
devops monitor remove <name>         # Remove resource
```

---

## Key Features

1. **Authentication System**
   - Token-based auth (SHA-256 hashed)
   - 8-hour session expiry
   - Rate limiting & lockout
   - Audit logging

2. **Dynamic Configuration**
   - Admin configures everything
   - Developers just use
   - No hardcoded values

3. **Real-time Monitoring**
   - PM2 monit-like dashboard
   - Websites, apps, servers
   - Concurrent health checks
   - Color-coded status

4. **Friendly Error Messages**
   - "Not configured" messages
   - Clear admin contact hints
   - No cryptic errors

---

## Testing

```bash
cd /home/elonerajeev/devops-cli
source venv/bin/activate
pytest tests/ -v
```

---

## Development Notes

- Use `ConfigValidator` for checking if things are configured
- Use `print_not_configured()` for friendly error messages
- All config validation in `utils/config_validator.py`
- Monitoring dashboard uses Rich Live display
- Health checks are async for concurrency

---

## Potential Next Steps

- [ ] Slack/Discord alerts for monitoring
- [ ] AI incident assistant (RAG-based)
- [ ] Team-based access control
- [ ] More AWS services (S3, Lambda logs)
- [ ] Installer script for distribution
- [ ] CI/CD pipeline for the CLI
