#!/bin/bash

# Jinja2 Network Config Tool - Local Update Script
# This script will update your local installation to the latest version

set -e  # Exit on any error

echo "======================================"
echo "Jinja2 Network Config Tool - Update"
echo "======================================"
echo ""

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

# Pull latest changes from GitHub
echo "📥 Pulling latest changes from GitHub..."
git pull || {
    echo "❌ Failed to pull from GitHub"
    echo "Make sure you're connected to the internet and have no uncommitted changes"
    exit 1
}

echo ""
echo "🔨 Rebuilding Docker image..."
docker build -t jinja-app . || {
    echo "❌ Failed to build Docker image"
    exit 1
}

echo ""
echo "🔄 Restarting application..."

# Stop and remove existing container
docker stop jinja-template-app 2>/dev/null || true
docker rm jinja-template-app 2>/dev/null || true

# Start new container
docker run -d \
    -p 80:80 \
    --name jinja-template-app \
    --restart unless-stopped \
    jinja-app || {
    echo "❌ Failed to start container"
    exit 1
}

echo ""
echo "✅ Update successful!"
echo ""
echo "📱 Application is running at: http://localhost"
echo ""

# Show current version
if docker exec jinja-template-app test -d .git 2>/dev/null; then
    VERSION=$(docker exec jinja-template-app git describe --tags --always 2>/dev/null || echo "unknown")
    echo "Current version: $VERSION"
fi

echo ""
echo "Opening browser..."
sleep 2

# Open browser
if command -v open &> /dev/null; then
    open http://localhost
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost
elif command -v start &> /dev/null; then
    start http://localhost
fi
