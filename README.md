# DevOps CLI

A powerful, template-based command-line tool for DevOps workflows. Built for startups and teams who need a unified CLI for managing applications, servers, deployments, and monitoring.

## Features

- **Real-time Monitoring Dashboard** - PM2 monit-like dashboard for websites, apps, and servers
- **Authentication System** - Token-based auth with role separation (Admin/Developer)
- **Dynamic Configuration** - Admin configures once, developers just use
- **AWS Integration** - CloudWatch logs, ECS, EC2 with IAM role assumption
- **Git & CI/CD** - PR creation, pipeline status, workflow triggers
- **SSH Management** - Multi-server commands, secure connections
- **Health Checks** - HTTP, TCP, Docker, Kubernetes health monitoring
- **Secrets Management** - Encrypted storage, .env file management

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/devops-cli.git
cd devops-cli

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS

# Install
pip install -e .

# Verify
devops --help
```

### For Admins (First-time Setup)

```bash
# Initialize CLI for your organization
devops admin init

# Check status
devops status

# Register a developer
devops admin user-add --email developer@company.com
# Save the token and share with developer

# Add applications
devops admin app-add

# Add servers
devops admin server-add
```

### For Developers

```bash
# Login with token from admin
devops auth login

# List available apps
devops app list

# View app logs
devops app logs my-app

# Real-time monitoring dashboard
devops monitor
```

## Commands Overview

### General
```bash
devops status           # Show configuration status
devops doctor           # Diagnose CLI health
devops version          # Show version
```

### Authentication
```bash
devops auth login       # Login with token
devops auth status      # Check session
devops auth logout      # End session
```

### Applications
```bash
devops app list         # List available apps
devops app logs <app>   # View app logs
devops app health <app> # Check app health
devops app info <app>   # Show app details
```

### Monitoring Dashboard
```bash
devops monitor                    # Live dashboard (like PM2 monit)
devops monitor --once             # Single check
devops monitor add-website -n mysite -u https://example.com
devops monitor add-app -n myapp -t docker -i container-name
devops monitor add-server -n web1 -H 10.0.1.10
devops monitor list               # List monitored resources
```

### Admin (Cloud Engineers)
```bash
devops admin init                 # Initialize for organization
devops admin user-add --email X   # Register developer
devops admin user-list            # List all users
devops admin app-add              # Add application
devops admin server-add           # Add SSH server
devops admin aws-add-role         # Configure AWS IAM role
devops admin audit-logs           # View auth audit logs
```

### Git & CI/CD
```bash
devops git status                 # Enhanced git status
devops git pr create              # Create pull request
devops git pipeline               # Check CI/CD status
```

### SSH & Servers
```bash
devops ssh list                   # List configured servers
devops ssh connect <server>       # SSH to server
devops ssh exec <server> "cmd"    # Run command on server
```

### AWS Logs
```bash
devops aws logs <app>             # View CloudWatch logs
devops aws logs <app> --follow    # Tail logs
```

## Configuration

All configuration is stored at `~/.devops-cli/`:

```
~/.devops-cli/
├── apps.yaml           # Applications
├── servers.yaml        # SSH servers
├── aws.yaml            # AWS roles
├── monitoring.yaml     # Monitoring resources
└── auth/               # Authentication data
```

## Monitoring Dashboard

The monitoring dashboard provides real-time status of your infrastructure:

```
╔═══════════════════════════════════════════════════════════════════╗
║              DEVOPS MONITOR                                       ║
║              ↻ Checks: 5  │  Uptime: 00:05:23  │  🌐 2  📦 1  🖥 3 ║
║              ✓ 5 Online    ⚠ 0 Degraded    ✗ 1 Offline            ║
╚═══════════════════════════════════════════════════════════════════╝

╭─  🌐 WEBSITES (2) ────────────────────────────────────────────────╮
│   STATUS     NAME              ⏱ RESPONSE   📈 UPTIME   MESSAGE   │
│   ✓ ONLINE   production-web        245ms      99.9%     HTTP 200  │
│   ✗ OFFLINE  staging-api             --          --     Timeout   │
╰───────────────────────────────────────────────────────────────────╯
```

## Security

- Tokens are hashed (SHA-256 + salt) - never stored in plain text
- Sessions expire after 8 hours
- Rate limiting on failed login attempts
- Audit logging for all auth events
- Auth directory secured with proper permissions

## Requirements

- Python 3.9+
- Git
- Docker (optional)
- AWS CLI (optional, for AWS features)

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.
