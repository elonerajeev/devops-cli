#!/bin/bash
# admin.sh - Run this only as the first-time Admin
set -e

echo "👑 DevOps CLI - Admin Initial Setup"

# 1. Install CLI
chmod +x ./install.sh
./install.sh

# 2. Initialize Config
echo "⚙️  Initializing organization config..."
devops admin init

# 3. Create First Admin
read -p "Enter your Admin Email: " ADMIN_EMAIL
devops admin user-add --email "$ADMIN_EMAIL" --role admin

# 4. Push to Private Config Repo
echo ""
read -p "Enter your PRIVATE Config Repo URL (e.g. https://github.com/org/private-config): " REPO_URL
if [ ! -z "$REPO_URL" ]; then
    cd ~/.devops-cli
    
    # Initialize git if not already
    if [ ! -d ".git" ]; then
        git init
    fi
    
    # Ensure we don't push sessions or sensitive auth data by accident
    echo "auth/.session" > .gitignore
    echo "auth/sessions.json" >> .gitignore
    echo "auth/audit.log" >> .gitignore
    echo "secrets/" >> .gitignore
    
    git add .
    git commit -m "Initial organization setup"
    git branch -M main
    
    # Add remote if it doesn't exist, otherwise update it
    if git remote | grep -q origin; then
        git remote set-url origin "$REPO_URL"
    else
        git remote add origin "$REPO_URL"
    fi
    
    git push -u origin main
    echo "✅ Configuration pushed to private repo!"
fi

echo ""
echo "🎉 Admin setup complete! You are ready to manage the org."