#!/bin/bash

# Jinja App Rollback Script
# Usage: ./rollback.sh [version-tag]
# Example: ./rollback.sh v1.0

set -e

VERSION=$1
REMOTE_HOST="172.16.20.201"
CONTAINER_NAME="jinja-template-app"
IMAGE_NAME="jinja-app"

echo "=========================================="
echo "Jinja App Rollback Tool"
echo "=========================================="

# If no version specified, show available versions
if [ -z "$VERSION" ]; then
    echo ""
    echo "Available versions:"
    echo ""
    ssh $REMOTE_HOST "docker images $IMAGE_NAME --format 'table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}'"
    echo ""
    echo "Usage: ./rollback.sh <version-tag>"
    echo "Example: ./rollback.sh v1.0"
    exit 0
fi

# Check if version exists
echo ""
echo "Checking if version $VERSION exists..."
if ! ssh $REMOTE_HOST "docker images $IMAGE_NAME:$VERSION --format '{{.Tag}}' | grep -q $VERSION"; then
    echo "❌ Error: Version $VERSION not found!"
    echo ""
    echo "Available versions:"
    ssh $REMOTE_HOST "docker images $IMAGE_NAME --format 'table {{.Tag}}\t{{.CreatedAt}}'"
    exit 1
fi

echo "✅ Version $VERSION found!"

# Confirm rollback
echo ""
read -p "⚠️  Rollback to version $VERSION? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Rollback cancelled."
    exit 0
fi

# Step 1: Stop current container
echo ""
echo "[1/4] Stopping current container..."
ssh $REMOTE_HOST "docker stop $CONTAINER_NAME || true"
ssh $REMOTE_HOST "docker rm $CONTAINER_NAME || true"

# Step 2: Start container with specified version
echo ""
echo "[2/4] Starting container with version $VERSION..."
ssh $REMOTE_HOST "docker run -d --name $CONTAINER_NAME \
    -p 80:80 \
    -v /root/jinja/templates:/app/templates \
    -v /root/jinja/static:/app/static \
    -v /root/jinja/database.db:/app/database.db \
    $IMAGE_NAME:$VERSION"

# Step 3: Update latest tag to point to this version
echo ""
echo "[3/4] Updating latest tag..."
ssh $REMOTE_HOST "docker tag $IMAGE_NAME:$VERSION $IMAGE_NAME:latest"

# Step 4: Verify rollback
echo ""
echo "[4/4] Verifying rollback..."
sleep 3
if ssh $REMOTE_HOST "docker ps | grep -q $CONTAINER_NAME"; then
    echo ""
    echo "=========================================="
    echo "✅ Rollback successful!"
    echo "Version: $VERSION"
    echo "Container: $CONTAINER_NAME"
    echo "URL: http://$REMOTE_HOST"
    echo "=========================================="

    # Optionally rollback git as well
    echo ""
    read -p "Do you want to rollback Git to tag $VERSION as well? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Rolling back Git to $VERSION..."
        git checkout $VERSION
        echo "✅ Git rolled back to $VERSION"
        echo "⚠️  You are now in detached HEAD state. To work on this version:"
        echo "   git checkout -b fix-$VERSION"
    fi
else
    echo ""
    echo "❌ Rollback failed! Container is not running."
    echo "Check logs with: ssh $REMOTE_HOST 'docker logs $CONTAINER_NAME'"
    exit 1
fi
