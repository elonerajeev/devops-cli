#!/bin/bash
# Setup Script for Developer Read-Only AWS Access
# Run this as an AWS admin to create secure read-only access for developers

set -e

POLICY_NAME="DevOpsCliDeveloperReadOnly"
GROUP_NAME="DevOpsCLIDevelopers"
PROFILE=${1:-default}

echo "========================================="
echo "  Developer AWS Access Setup"
echo "========================================="
echo ""
echo "AWS Profile: $PROFILE"
echo "Policy Name: $POLICY_NAME"
echo "Group Name: $GROUP_NAME"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI not installed"
    exit 1
fi

# Verify credentials
echo "[1/4] Verifying AWS credentials..."
aws sts get-caller-identity --profile "$PROFILE" || {
    echo "Error: Could not authenticate with AWS"
    exit 1
}

ACCOUNT_ID=$(aws sts get-caller-identity --profile "$PROFILE" --query Account --output text)
echo "Account ID: $ACCOUNT_ID"
echo ""

# Create IAM policy
echo "[2/4] Creating IAM policy..."
POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${POLICY_NAME}"

# Check if policy exists
if aws iam get-policy --policy-arn "$POLICY_ARN" --profile "$PROFILE" 2>/dev/null; then
    echo "Policy already exists, updating..."
    # Get current version
    VERSIONS=$(aws iam list-policy-versions --policy-arn "$POLICY_ARN" --profile "$PROFILE" --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text)
    # Delete old versions if at limit
    for v in $VERSIONS; do
        aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$v" --profile "$PROFILE" 2>/dev/null || true
    done
    # Create new version
    aws iam create-policy-version \
        --policy-arn "$POLICY_ARN" \
        --policy-document file://developer-readonly-policy.json \
        --set-as-default \
        --profile "$PROFILE"
else
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document file://developer-readonly-policy.json \
        --description "Read-only access for DevOps CLI developers to view logs" \
        --profile "$PROFILE"
fi
echo "Policy ARN: $POLICY_ARN"
echo ""

# Create IAM group
echo "[3/4] Creating IAM group..."
aws iam create-group --group-name "$GROUP_NAME" --profile "$PROFILE" 2>/dev/null || echo "Group already exists"

# Attach policy to group
aws iam attach-group-policy \
    --group-name "$GROUP_NAME" \
    --policy-arn "$POLICY_ARN" \
    --profile "$PROFILE" 2>/dev/null || echo "Policy already attached"
echo "Group '$GROUP_NAME' created with policy attached"
echo ""

# Instructions
echo "[4/4] Setup complete!"
echo ""
echo "========================================="
echo "  Next Steps"
echo "========================================="
echo ""
echo "For each developer:"
echo ""
echo "1. Create IAM user (or use existing):"
echo "   aws iam create-user --user-name developer-name --profile $PROFILE"
echo ""
echo "2. Add user to the group:"
echo "   aws iam add-user-to-group --user-name developer-name --group-name $GROUP_NAME --profile $PROFILE"
echo ""
echo "3. Create access keys for the user:"
echo "   aws iam create-access-key --user-name developer-name --profile $PROFILE"
echo ""
echo "4. Developer configures their CLI:"
echo "   aws configure --profile dev-readonly"
echo "   # Enter the access key and secret key"
echo ""
echo "5. Developer tests access:"
echo "   devops aws groups --profile dev-readonly"
echo ""
echo "========================================="
