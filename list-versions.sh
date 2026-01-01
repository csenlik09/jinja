#!/bin/bash

# List all available versions of Jinja App
# Usage: ./list-versions.sh

REMOTE_HOST="172.16.20.201"
IMAGE_NAME="jinja-app"
CONTAINER_NAME="jinja-template-app"

echo "=========================================="
echo "Jinja App Version Information"
echo "=========================================="

# Show currently running version
echo ""
echo "📦 Currently Running:"
CURRENT_IMAGE=$(ssh $REMOTE_HOST "docker inspect $CONTAINER_NAME --format='{{.Config.Image}}' 2>/dev/null" || echo "None")
if [ "$CURRENT_IMAGE" != "None" ]; then
    echo "   Container: $CONTAINER_NAME"
    echo "   Image: $CURRENT_IMAGE"
    STARTED=$(ssh $REMOTE_HOST "docker inspect $CONTAINER_NAME --format='{{.State.StartedAt}}' 2>/dev/null")
    echo "   Started: $STARTED"
else
    echo "   No container running"
fi

# Show available Docker images
echo ""
echo "🐳 Available Docker Versions:"
echo ""
ssh $REMOTE_HOST "docker images $IMAGE_NAME --format 'table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}'"

# Show Git tags
echo ""
echo "📌 Git Tags:"
echo ""
git tag -l -n1 | tail -n 10

echo ""
echo "=========================================="
echo "Commands:"
echo "  Deploy new version:    ./deploy.sh v1.x 'description'"
echo "  Rollback to version:   ./rollback.sh v1.x"
echo "=========================================="
