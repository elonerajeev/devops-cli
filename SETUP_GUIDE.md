# DevOps CLI - Complete Setup & Usage Guide

A comprehensive guide for Cloud Engineers (Admins) and Developers to set up and use the DevOps CLI tool.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Admin Commands Reference](#admin-commands-reference)
4. [Developer Commands Reference](#developer-commands-reference)
5. [Setup Guide - Admin](#setup-guide---admin)
6. [Setup Guide - Developer](#setup-guide---developer)
7. [Sharing Configuration](#sharing-configuration)
8. [Security Best Practices](#security-best-practices)
9. [Troubleshooting](#troubleshooting)

---

## Overview

### What is DevOps CLI?

A unified command-line tool for managing:
- Application logs (CloudWatch, Docker, Kubernetes)
- SSH server connections
- AWS resources with IAM role assumption
- Real-time monitoring dashboard
- Git & CI/CD operations
- Team access control

### User Roles

| Role | Description | Access |
|------|-------------|--------|
| **Admin** | Cloud Engineers, DevOps | All commands (admin + developer) |
| **Developer** | Software Engineers | Developer commands only |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DevOps CLI                                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ADMIN LAYER                    DEVELOPER LAYER                    │
│   ────────────                   ───────────────                    │
│   • User Management              • View App Logs                    │
│   • App Configuration            • Check App Health                 │
│   • Server Configuration         • SSH to Servers                   │
│   • AWS Role Setup               • Git Operations                   │
│   • Team Permissions             • Monitoring Dashboard             │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   CONFIG STORAGE: ~/.devops-cli/                                    │
│   ├── apps.yaml          # Application configurations               │
│   ├── servers.yaml       # SSH server details                       │
│   ├── aws.yaml           # AWS roles & credentials                  │
│   ├── teams.yaml         # Team access permissions                  │
│   ├── monitoring.yaml    # Monitoring resources                     │
│   └── auth/                                                         │
│       ├── users.yaml     # Registered users (hashed tokens)         │
│       ├── sessions/      # Active login sessions                    │
│       └── audit.log      # Authentication audit trail               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Admin Commands Reference

### Initialization

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `devops admin init` | Initialize CLI for organization | First-time setup only |

### User Management

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin user-add` | Register new user & generate token | `--email dev@co.com --role developer` |
| `devops admin user-list` | List all registered users | Shows email, role, status |
| `devops admin user-remove <email>` | Permanently delete a user | Removes all access |
| `devops admin user-deactivate <email>` | Temporarily disable user | User can't login |
| `devops admin user-activate <email>` | Re-enable disabled user | Restores access |
| `devops admin user-reset-token <email>` | Generate new token | Old token stops working |
| `devops admin audit-logs` | View authentication logs | Security monitoring |

### Application Management

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin app-add` | Add new application (interactive) | ECS, EC2, Lambda, Docker, K8s |
| `devops admin app-list` | List all configured apps | Shows type, log source |
| `devops admin app-show <name>` | View app configuration details | Full YAML config |
| `devops admin app-edit <name>` | Edit app config in editor | Opens in $EDITOR |
| `devops admin app-remove <name>` | Remove an application | Requires confirmation |

### Server Management

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin server-add` | Add SSH server (interactive) | Host, user, key, tags |
| `devops admin server-list` | List all servers | Shows host, user, tags |
| `devops admin server-remove <name>` | Remove a server | Requires confirmation |

### AWS Management

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin aws-configure` | Set AWS credentials | For CloudWatch access |
| `devops admin aws-add-role` | Add IAM role for assumption | Cross-account access |
| `devops admin aws-list-roles` | List configured roles | Shows ARN, region |
| `devops admin aws-remove-role <name>` | Remove an AWS role | Requires confirmation |
| `devops admin aws-show` | Show AWS credentials (masked) | Verify configuration |
| `devops admin aws-test` | Test AWS credentials | Validates permissions |
| `devops admin aws-remove` | Remove stored credentials | Clean up |

### Team Management

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin team-add` | Create a team | `--name backend` |
| `devops admin team-list` | List all teams | Shows access permissions |
| `devops admin team-remove <name>` | Delete a team | Can't remove default |

### Repository Management

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin repo-discover` | Auto-discover GitHub repos | From org or user |
| `devops admin repo-add` | Add single repository | `--owner org --repo name` |
| `devops admin repo-list` | List configured repos | Shows branch, visibility |
| `devops admin repo-show <name>` | View repo details | Full configuration |
| `devops admin repo-remove <name>` | Remove repository | Requires confirmation |
| `devops admin repo-refresh <name>` | Update repo from GitHub | Sync latest info |

### Export/Import

| Command | Purpose | Example |
|---------|---------|---------|
| `devops admin export` | Export configuration | `--output config.yaml` |
| `devops admin import <file>` | Import configuration | `--merge` or `--replace` |
| `devops admin status` | Show admin config status | Overview of all resources |

---

## Developer Commands Reference

### Authentication

| Command | Purpose | Example |
|---------|---------|---------|
| `devops auth login` | Login with token | `--email x --token DVC-xxx` |
| `devops auth logout` | End current session | Clears session |
| `devops auth status` | Check login status | Shows expiry time |
| `devops auth whoami` | Show current user | Email and role |
| `devops auth refresh` | Extend session | +8 hours |

### Application Operations

| Command | Purpose | Example |
|---------|---------|---------|
| `devops app list` | List available apps | Shows configured apps |
| `devops app logs <name>` | View application logs | `--follow` for live |
| `devops app health <name>` | Check app health | HTTP/TCP/Command check |
| `devops app info <name>` | Show app details | Type, log source, etc. |

### SSH Operations

| Command | Purpose | Example |
|---------|---------|---------|
| `devops ssh list` | List available servers | Shows accessible servers |
| `devops ssh connect <name>` | SSH to a server | Interactive session |
| `devops ssh exec <name> "cmd"` | Run command on server | Single command |

### AWS Operations

| Command | Purpose | Example |
|---------|---------|---------|
| `devops aws logs <app>` | View CloudWatch logs | `--follow` for live |
| `devops aws cloudwatch <group>` | Direct CloudWatch access | Specify log group |

### Git Operations

| Command | Purpose | Example |
|---------|---------|---------|
| `devops git status` | Enhanced git status | With branch info |
| `devops git pr create` | Create pull request | Interactive |
| `devops git pr list` | List open PRs | For current repo |
| `devops git pipeline` | Check CI/CD status | GitHub Actions |

### Monitoring Dashboard

| Command | Purpose | Example |
|---------|---------|---------|
| `devops monitor` | Live monitoring dashboard | Real-time updates |
| `devops monitor --once` | Single status check | No live updates |
| `devops monitor list` | List monitored resources | Websites, apps, servers |
| `devops monitor add-website` | Add website to monitor | `-n name -u url` |
| `devops monitor add-app` | Add app to monitor | `-n name -t type` |
| `devops monitor add-server` | Add server to monitor | `-n name -H host` |
| `devops monitor remove <name>` | Remove from monitoring | By resource name |

### General

| Command | Purpose |
|---------|---------|
| `devops status` | Show CLI configuration status |
| `devops doctor` | Diagnose CLI health |
| `devops version` | Show version |
| `devops --help` | Show all commands |

---

## Setup Guide - Admin

### Step 1: Install the CLI

```bash
# Clone the repository
git clone https://github.com/yourorg/devops-cli.git
cd devops-cli

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# OR: venv\Scripts\activate  # Windows

# Install
pip install -e .

# Verify
devops --help
```

### Step 2: Initialize for Your Organization

```bash
devops admin init
# Enter: Organization name
# Enter: Default AWS region
```

### Step 3: Create First Admin User

```bash
devops admin user-add --email admin@yourcompany.com --role admin
# IMPORTANT: Save the generated token! It's shown only once.
# Token format: DVC-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Step 4: Login as Admin

```bash
devops auth login --email admin@yourcompany.com --token DVC-xxxxx
```

### Step 5: Configure AWS Credentials

```bash
devops admin aws-configure
# Enter: AWS Access Key ID
# Enter: AWS Secret Access Key
# Enter: Region (e.g., ap-south-1)
```

### Step 6: Add Applications

```bash
devops admin app-add
# Follow interactive prompts:
# - App name (e.g., backend-api)
# - App type (ecs, ec2, lambda, docker, kubernetes)
# - Log configuration
# - Health check URL
```

### Step 7: Add SSH Servers (Optional)

```bash
devops admin server-add
# Enter: Server name (e.g., web-prod-1)
# Enter: Hostname/IP
# Enter: SSH user
# Enter: SSH key path
```

### Step 8: Create Developer Users

```bash
# For each developer:
devops admin user-add --email developer@yourcompany.com --role developer
# Share the token securely with the developer (Slack DM, 1Password, etc.)
```

### Step 9: Verify Setup

```bash
devops status
devops admin status
```

---

## Setup Guide - Developer

### Step 1: Get From Admin

Before starting, get these from your admin:
- [ ] Access to the CLI source code repository
- [ ] Access to the config repository (if using repo approach)
- [ ] Your personal access token (DVC-xxx format)
- [ ] Your registered email address

### Step 2: Install the CLI

```bash
# Clone the CLI source
git clone https://github.com/yourorg/devops-cli.git
cd devops-cli

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# OR: venv\Scripts\activate  # Windows

# Install
pip install -e .
```

### Step 3: Get Configuration

**Option A: Clone config repo (if admin set this up)**
```bash
git clone https://github.com/yourorg/devops-cli-config.git ~/.devops-cli
```

**Option B: Copy config files from admin**
```bash
# Admin exports and shares config file
# You import it:
devops admin import company-config.yaml
```

### Step 4: Login

```bash
devops auth login --email your@email.com --token DVC-your-token-here
```

### Step 5: Verify Access

```bash
# Check your status
devops auth status

# List available apps
devops app list

# Check CLI status
devops status
```

### Step 6: Start Using

```bash
# View logs
devops app logs backend-api
devops app logs backend-api --follow

# Check health
devops app health backend-api

# SSH to server
devops ssh list
devops ssh connect web-prod-1

# Monitoring dashboard
devops monitor
```

---

## Sharing Configuration

### Method 1: Private Git Repository (Recommended)

**Admin Setup:**
```bash
# Navigate to config directory
cd ~/.devops-cli

# Initialize git
git init

# Create .gitignore for sensitive files
cat > .gitignore << 'EOF'
# Don't commit these
.aws_credentials.enc
auth/sessions/
*.log
EOF

# Add safe files
git add apps.yaml servers.yaml aws.yaml teams.yaml monitoring.yaml auth/users.yaml .gitignore

# Commit
git commit -m "DevOps CLI configuration"

# Push to private repo
git remote add origin git@github.com:yourorg/devops-cli-config.git
git push -u origin main
```

**Developer Setup:**
```bash
# Clone config
git clone git@github.com:yourorg/devops-cli-config.git ~/.devops-cli

# Login with your token
devops auth login
```

**Keeping Config Updated:**
```bash
# Admin pushes updates
cd ~/.devops-cli
git add -A && git commit -m "Update config" && git push

# Developers pull updates
cd ~/.devops-cli
git pull
```

### Method 2: Export/Import

```bash
# Admin exports
devops admin export --output company-config.yaml

# Share file via secure channel

# Developer imports
devops admin import company-config.yaml
```

### Method 3: Shared Server

```bash
# All team members SSH to a shared server
# CLI is configured once on that server
ssh devops-server
devops app logs backend-api
```

---

## Security Best Practices

### For Admins

| Practice | Why | How |
|----------|-----|-----|
| **Use strong tokens** | Prevent brute force | Tokens are auto-generated (secure) |
| **Rotate tokens periodically** | Limit exposure | `devops admin user-reset-token` |
| **Deactivate departed users** | Revoke access immediately | `devops admin user-deactivate` |
| **Review audit logs** | Detect suspicious activity | `devops admin audit-logs` |
| **Use read-only AWS credentials** | Limit blast radius | Only CloudWatch read permissions |
| **Don't commit secrets** | Prevent leaks | Use .gitignore for credentials |
| **Use private repo for config** | Protect infrastructure details | Not public! |

### For Developers

| Practice | Why | How |
|----------|-----|-----|
| **Never share your token** | Personal access | Each user has unique token |
| **Logout when done** | Prevent unauthorized access | `devops auth logout` |
| **Don't commit ~/.devops-cli** | Contains sensitive data | Add to global .gitignore |
| **Report suspicious activity** | Security awareness | Contact admin |

### Token Security

```
┌─────────────────────────────────────────────────────────────────┐
│                      TOKEN SECURITY                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✓ Tokens are hashed (SHA-256 + salt) before storage            │
│  ✓ Plain tokens are NEVER stored                                │
│  ✓ Sessions expire after 8 hours                                │
│  ✓ Failed logins are rate-limited (5 attempts/15 min)           │
│  ✓ All auth events are logged for audit                         │
│                                                                 │
│  Token Format: DVC-<32 random characters>                       │
│  Example: DVC-Wb6yMlNEjUO8hay05zW9wobIKU3oGA9ENAhpKtZyOgo       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### AWS Credentials Security

```
┌─────────────────────────────────────────────────────────────────┐
│                  AWS CREDENTIALS SECURITY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ✓ Credentials are encrypted at rest                            │
│  ✓ Stored in ~/.devops-cli/.aws_credentials.enc                 │
│  ✓ File permissions: 600 (owner read/write only)                │
│  ✓ Use IAM user with MINIMAL permissions:                       │
│                                                                 │
│    Required Permissions:                                        │
│    - logs:DescribeLogGroups                                     │
│    - logs:FilterLogEvents                                       │
│    - logs:GetLogEvents                                          │
│    - ec2:DescribeInstances (optional)                           │
│                                                                 │
│  ✗ NEVER use root credentials                                   │
│  ✗ NEVER use admin/full-access credentials                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Config Directory Permissions

```bash
# Set proper permissions (Linux/macOS)
chmod 700 ~/.devops-cli
chmod 600 ~/.devops-cli/*.yaml
chmod 600 ~/.devops-cli/.aws_credentials.enc
chmod 700 ~/.devops-cli/auth
chmod 600 ~/.devops-cli/auth/*
```

---

## Troubleshooting

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "CLI not initialized" | First time setup | Run `devops admin init` |
| "Login required" | Session expired | Run `devops auth login` |
| "Access denied" | Developer trying admin command | Contact admin for access |
| "Invalid token" | Wrong token or typo | Check token, request reset |
| "User deactivated" | Account disabled | Contact admin |
| "Rate limit exceeded" | Too many failed logins | Wait 15 minutes |
| "No apps configured" | Admin hasn't added apps | Contact admin |
| "AWS credentials invalid" | Wrong keys or expired | Admin: `devops admin aws-configure` |

### Diagnostic Commands

```bash
# Check CLI health
devops doctor

# Check configuration status
devops status

# Check authentication
devops auth status

# View as admin
devops admin status
```

### Getting Help

```bash
# General help
devops --help

# Command-specific help
devops admin --help
devops app --help
devops auth --help

# Subcommand help
devops admin user-add --help
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────────┐
│                    QUICK REFERENCE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  FIRST TIME SETUP (Admin)                                       │
│  ────────────────────────                                       │
│  devops admin init                                              │
│  devops admin user-add --email admin@co.com --role admin        │
│  devops auth login --email admin@co.com --token DVC-xxx         │
│  devops admin aws-configure                                     │
│  devops admin app-add                                           │
│  devops admin user-add --email dev@co.com --role developer      │
│                                                                 │
│  DAILY USE (Developer)                                          │
│  ─────────────────────                                          │
│  devops auth login                                              │
│  devops app list                                                │
│  devops app logs <app-name>                                     │
│  devops app logs <app-name> --follow                            │
│  devops monitor                                                 │
│  devops ssh connect <server>                                    │
│  devops auth logout                                             │
│                                                                 │
│  USEFUL COMMANDS                                                │
│  ───────────────                                                │
│  devops status          - Check CLI configuration               │
│  devops doctor          - Diagnose issues                       │
│  devops auth status     - Check login status                    │
│  devops --help          - See all commands                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Support

- **Issues**: Report bugs at GitHub Issues
- **Questions**: Contact your organization's Cloud Engineering team
- **Security Issues**: Report privately to security@yourcompany.com

---

*Document Version: 1.0.0*
*Last Updated: January 2026*
