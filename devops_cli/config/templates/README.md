# DevOps CLI Configuration Templates

This folder contains YAML templates for all configuration types supported by the DevOps CLI.

## Quick Start

1. Copy the template you need to your working directory
2. Edit with your actual values
3. **Validate your config** (recommended)
4. Import using the appropriate command

```bash
# Copy a template
cp /path/to/templates/apps-template.yaml ./my-apps.yaml

# Edit with your values
nano ./my-apps.yaml

# Validate before importing (NEW!)
devops admin validate ./my-apps.yaml

# Import
devops admin import --file ./my-apps.yaml
```

## Available Templates

| Template | Description | Import Command | Developer Features |
|----------|-------------|----------------|-------------------|
| `apps-template.yaml` | Application configurations | `devops admin import --file apps.yaml` | View logs, health checks |
| `servers-template.yaml` | SSH server configurations | `devops admin import --file servers.yaml` | SSH access, run commands |
| `websites-template.yaml` | Website health monitoring | `devops admin import --file websites.yaml` | Check website status |
| `teams-template.yaml` | Team access control | `devops admin import --file teams.yaml` | Team-based permissions |
| `repos-template.yaml` | GitHub repositories | `devops admin import --file repos.yaml` | **CI/CD history, commit info, pipeline status** |
| `aws-roles-template.yaml` | AWS IAM roles | `devops admin aws-roles-import --file aws-roles.yaml` | AWS access |
| `aws-credentials-template.yaml` | AWS credentials | `devops admin aws-import --file aws-credentials.yaml` | AWS access |
| `users-template.yaml` | Bulk user registration | `devops admin users-import --file users.yaml` | User authentication |

## Repository Features for Developers

After repos are configured, developers get powerful Git/CI features:

### View Configured Repos
```bash
# List all repos
devops git repos

# Show with latest commits
devops git repos --commits

# Example output:
Name      Owner/Repo          Commit   Message
backend   myorg/api-backend   a1b2c3d  Fix authentication bug
frontend  myorg/web-app       d4e5f6g  Update dashboard UI
```

### View Repo Details
```bash
# Show full repo info with current commit
devops git repo-info --repo backend

# Example output:
Repository: myorg/api-backend

Configuration:
  Name:        backend
  Description: Backend API Service
  Language:    Python
  Branch:      main

Latest Commit (main):
  Commit ID:   a1b2c3d (full: a1b2c3d4e5f6g7h8i9j0)
  Message:     Fix authentication bug in login flow
  Author:      John Developer
  Time:        2 hours ago
  URL:         https://github.com/myorg/api-backend/commit/a1b2c3d
```

### View CI/CD Pipeline History
```bash
# View pipeline runs
devops git pipeline --repo backend

# Example output:
CI/CD Pipeline: myorg/api-backend
Branch: main

Latest Commit:
  ID:      a1b2c3d
  Message: Fix authentication bug
  Author:  John Developer
  Time:    2 hours ago

Pipeline History:
   Workflow              Status   Commit   Time
✓  Build and Test        success  a1b2c3d  2 hours ago
✗  Build and Test        failure  b2c3d4e  5 hours ago
✓  Deploy to Staging     success  c3d4e5f  1 day ago

● Build passed successfully

Total runs shown: 10
```

### Handle Build Failures
```bash
# When build fails, see details
devops git pipeline --repo backend

# Shows:
✗ Build failed - check logs for details

Failure Details:
  Workflow: Build and Test
  Run ID:   123456789
  URL:      https://github.com/myorg/api-backend/actions/runs/123456789

  Failed Jobs:
    - unit-tests
    - integration-tests
```

## Config Management Strategies

Choose between **LOCAL** or **CENTRALIZED** config management based on your needs:

### Local Secrets Management (Simple)
Good for: Development, small teams, simple setups

```yaml
# Use environment variables
api_key: ${MY_API_KEY}
password: ${DB_PASSWORD}

# Use local file paths
ssh_key: ~/.ssh/id_rsa
config_file: /etc/myapp/config.json
```

### Centralized Config Management (Advanced)
Good for: Production, teams, compliance requirements

```yaml
# AWS Secrets Manager
secret_key: ${AWS_SECRET:devops-cli/aws-secret-key}
api_token: ${AWS_SECRET:myapp/api-tokens/production}
ssh_key: ${AWS_SECRET:ssh-keys/prod-server}

# GitHub Secrets (CI/CD)
access_key: ${GITHUB_SECRET:AWS_ACCESS_KEY_ID}
token: ${GITHUB_SECRET:GH_TOKEN}
```

### Hybrid Approach
Mix both strategies as needed:

```yaml
# Local for dev, centralized for prod
api_url: ${APP_URL}                              # Local env var
api_key: ${AWS_SECRET:prod/api-key}              # Centralized secret
ssh_key: ~/.ssh/id_rsa                           # Local file
```

## Security Best Practices

1. **Never commit credentials** - Add `*-credentials*.yaml` to `.gitignore`
2. **Delete after import** - Remove credential files after importing
3. **Use secrets managers** - Store sensitive values in AWS Secrets Manager or similar
4. **Rotate regularly** - Update credentials periodically
5. **Least privilege** - Use read-only permissions when possible

## Export Existing Configuration

You can export your current configuration as a starting point:

```bash
# Export all configuration
devops admin export --output my-config.yaml

# Export specific types
devops admin aws-roles-export --output aws-roles.yaml
devops admin users-export --output users.yaml

# Export templates (placeholder values)
devops admin aws-export-template --output aws-credentials.yaml
devops admin aws-roles-export-template --output aws-roles.yaml
devops admin users-export-template --output users.yaml
```

## CLI Commands for Templates

```bash
# Copy templates to current directory
devops admin templates --copy

# List available templates
devops admin templates --list

# Show template location
devops admin templates --path

# Validate a config file before importing (NEW!)
devops admin validate apps.yaml
devops admin validate servers.yaml --type servers
```

## Validation Command

Before importing any config, validate it to catch errors:

```bash
# Auto-detect config type from filename/content
devops admin validate my-apps.yaml

# Specify type explicitly
devops admin validate myconfig.yaml --type servers

# Example output:
✓ Configuration is valid!

Information:
  - Found 3 app(s)
  - Local file path found at ecs.region: ap-south-1

Secret References Found:
  AWS_SECRET:
    - api-tokens/health-check
  ENV_VAR:
    - AWS_REGION
    - WEB_SERVER_URL
```

The validator checks:
- ✓ YAML syntax
- ✓ Required fields
- ✓ Field formats and types
- ✓ Secret reference syntax
- ✓ Local vs centralized config patterns
