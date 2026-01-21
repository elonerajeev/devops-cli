#!/bin/bash
# New Server Setup Script (Ubuntu/Debian)
# Usage: sudo ./setup-server.sh

set -e

echo "========================================="
echo "       Server Setup Script              "
echo "========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./setup-server.sh)"
    exit 1
fi

# Update system
echo "[1/8] Updating system packages..."
apt-get update
apt-get upgrade -y

# Install essential packages
echo ""
echo "[2/8] Installing essential packages..."
apt-get install -y \
    curl \
    wget \
    git \
    vim \
    htop \
    tmux \
    unzip \
    jq \
    tree \
    ncdu \
    net-tools \
    dnsutils \
    ca-certificates \
    gnupg \
    lsb-release \
    software-properties-common \
    apt-transport-https

# Install Docker
echo ""
echo "[3/8] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "Docker installed successfully"
else
    echo "Docker already installed"
fi

# Install Docker Compose
echo ""
echo "[4/8] Installing Docker Compose..."
if ! command -v docker-compose &> /dev/null; then
    COMPOSE_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | jq -r .tag_name)
    curl -L "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "Docker Compose installed: $COMPOSE_VERSION"
else
    echo "Docker Compose already installed"
fi

# Setup firewall
echo ""
echo "[5/8] Configuring firewall..."
apt-get install -y ufw
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow http
ufw allow https
ufw --force enable
echo "Firewall configured (SSH, HTTP, HTTPS allowed)"

# Setup automatic security updates
echo ""
echo "[6/8] Enabling automatic security updates..."
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

# Create deploy user
echo ""
echo "[7/8] Creating deploy user..."
if ! id "deploy" &>/dev/null; then
    useradd -m -s /bin/bash deploy
    usermod -aG docker deploy
    mkdir -p /home/deploy/.ssh
    chmod 700 /home/deploy/.ssh
    touch /home/deploy/.ssh/authorized_keys
    chmod 600 /home/deploy/.ssh/authorized_keys
    chown -R deploy:deploy /home/deploy/.ssh
    echo "Deploy user created (add SSH keys to /home/deploy/.ssh/authorized_keys)"
else
    echo "Deploy user already exists"
fi

# Setup basic monitoring
echo ""
echo "[8/8] Setting up basic monitoring..."
# Install and configure fail2ban
apt-get install -y fail2ban
systemctl enable fail2ban
systemctl start fail2ban

echo ""
echo "========================================="
echo "       Setup Complete!                  "
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Add SSH keys to /home/deploy/.ssh/authorized_keys"
echo "2. Configure your applications"
echo "3. Set up SSL certificates (certbot)"
echo "4. Configure monitoring (optional)"
echo ""
echo "Installed:"
echo "  - Docker: $(docker --version 2>/dev/null || echo 'not found')"
echo "  - Docker Compose: $(docker-compose --version 2>/dev/null || echo 'not found')"
echo "  - UFW Firewall: enabled"
echo "  - Fail2ban: enabled"
echo "  - Automatic updates: enabled"
