#!/bin/bash

# Jinja App Deployment Script
# Usage: ./deploy.sh <version-tag> [description]
# Example: ./deploy.sh v1.0 "Working version with preview feature"

set -e

VERSION=$1
DESCRIPTION=$2
REMOTE_HOST="172.16.20.201"
CONTAINER_NAME="jinja-template-app"
IMAGE_NAME="jinja-app"
MAX_VERSIONS=5  # Keep last 5 versions

if [ -z "$VERSION" ]; then
    echo "Error: Version tag is required"
    echo "Usage: ./deploy.sh <version-tag> [description]"
    echo "Example: ./deploy.sh v1.0 'Working version with preview'"
    exit 1
fi

if [ -z "$DESCRIPTION" ]; then
    DESCRIPTION="Deployment version $VERSION"
fi

echo "=========================================="
echo "Deploying Jinja App - Version: $VERSION"
echo "Description: $DESCRIPTION"
echo "=========================================="

# Step 1: Commit current changes to Git
echo ""
echo "[1/7] Committing changes to Git..."
git add -A
git commit -m "$DESCRIPTION

Version: $VERSION

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>" || echo "No changes to commit"

# Step 2: Create Git tag
echo ""
echo "[2/7] Creating Git tag: $VERSION..."
git tag -a "$VERSION" -m "$DESCRIPTION" -f
git push origin main --tags -f

# Step 3: Build Docker image with version tag
echo ""
echo "[3/7] Building Docker image: $IMAGE_NAME:$VERSION..."
ssh $REMOTE_HOST "cd /root/jinja && docker build -t $IMAGE_NAME:$VERSION -t $IMAGE_NAME:latest ."

# Step 4: Stop current container
echo ""
echo "[4/7] Stopping current container..."
ssh $REMOTE_HOST "docker stop $CONTAINER_NAME || true"
ssh $REMOTE_HOST "docker rm $CONTAINER_NAME || true"

# Step 5: Start new container with version tag
echo ""
echo "[5/7] Starting new container with version $VERSION..."
ssh $REMOTE_HOST "docker run -d --name $CONTAINER_NAME \
    -p 80:80 \
    -v /root/jinja/templates:/app/templates \
    -v /root/jinja/static:/app/static \
    -v /root/jinja/database.db:/app/database.db \
    $IMAGE_NAME:$VERSION"

# Step 6: Clean up old Docker images (keep last MAX_VERSIONS)
echo ""
echo "[6/7] Cleaning up old Docker images (keeping last $MAX_VERSIONS versions)..."
ssh $REMOTE_HOST "docker images $IMAGE_NAME --format '{{.Tag}}' | grep -v latest | sort -V -r | tail -n +$((MAX_VERSIONS + 1)) | xargs -r -I {} docker rmi $IMAGE_NAME:{} || true"

# Step 7: Verify deployment
echo ""
echo "[7/7] Verifying deployment..."
sleep 3
if ssh $REMOTE_HOST "docker ps | grep -q $CONTAINER_NAME"; then
    echo ""
    echo "=========================================="
    echo "✅ Deployment successful!"
    echo "Version: $VERSION"
    echo "Container: $CONTAINER_NAME"
    echo "URL: http://$REMOTE_HOST"
    echo "=========================================="
    echo ""
    echo "Available versions:"
    ssh $REMOTE_HOST "docker images $IMAGE_NAME --format 'table {{.Tag}}\t{{.CreatedAt}}' | head -n $((MAX_VERSIONS + 2))"
else
    echo ""
    echo "❌ Deployment failed! Container is not running."
    echo "Check logs with: ssh $REMOTE_HOST 'docker logs $CONTAINER_NAME'"
    exit 1
fi
