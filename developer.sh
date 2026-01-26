#!/bin/bash
# developer.sh - Run this to join an organization
set -e

echo "🚀 DevOps CLI - Developer Onboarding"

# 1. Install CLI
chmod +x ./install.sh
./install.sh

# 2. Clone the Admin's Private Config
read -p "Enter Organization Private Config Repo URL: " CONFIG_URL
if [ ! -d "$HOME/.devops-cli" ]; then
    echo "📂 Cloning organization configuration..."
    git clone "$CONFIG_URL" "$HOME/.devops-cli"
else
    echo "✅ Configuration already exists. Updating..."
    cd "$HOME/.devops-cli" && git pull && cd -
fi

# 3. Handle GITHUB_TOKEN Secret
if [ -z "$GITHUB_TOKEN" ]; then
    echo "🔐 GITHUB_TOKEN not found in environment."
    read -sp "Enter your GitHub PAT (token): " GH_TOKEN
    echo ""
    # Detect shell profile
    PROFILE_FILE="$HOME/.bashrc"
    if [ -f "$HOME/.zshrc" ]; then
        PROFILE_FILE="$HOME/.zshrc"
    fi
    
    echo "export GITHUB_TOKEN=$GH_TOKEN" >> "$PROFILE_FILE"
    export GITHUB_TOKEN=$GH_TOKEN
    echo "✅ Token added to $PROFILE_FILE."
fi

# 4. Login
echo "🔐 Authenticating with your organization..."
devops auth login