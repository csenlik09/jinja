#!/bin/bash

# Jinja2 Network Config Tool - Local Deployment Script
# This script will build and run the application in Docker on your local machine

set -e  # Exit on any error

echo "======================================"
echo "Jinja2 Network Config Tool Deployment"
echo "======================================"
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker Desktop from: https://www.docker.com/products/docker-desktop"
    exit 1
fi

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Error: Docker is not running"
    echo "Please start Docker Desktop and try again"
    exit 1
fi

echo "✅ Docker is installed and running"
echo ""

# Stop and remove existing container if it exists
if docker ps -a | grep -q jinja-template-app; then
    echo "🔄 Removing existing container..."
    docker stop jinja-template-app 2>/dev/null || true
    docker rm jinja-template-app 2>/dev/null || true
fi

# Build Docker image
echo "🔨 Building Docker image..."
docker build -t jinja-app . || {
    echo "❌ Failed to build Docker image"
    exit 1
}

echo ""
echo "🚀 Starting application..."

# Run Docker container
docker run -d \
    -p 8080:80 \
    --name jinja-template-app \
    --restart unless-stopped \
    jinja-app || {
    echo "❌ Failed to start container"
    exit 1
}

echo ""
echo "✅ Deployment successful!"
echo ""
echo "📱 Application is running at: http://localhost:8080"
echo ""
echo "Useful commands:"
echo "  - View logs:        docker logs jinja-template-app"
echo "  - Stop app:         docker stop jinja-template-app"
echo "  - Start app:        docker start jinja-template-app"
echo "  - Restart app:      docker restart jinja-template-app"
echo "  - Update app:       ./local-update.sh"
echo ""
echo "Opening browser..."
sleep 2

# Open browser (works on macOS, Linux, and Windows)
if command -v open &> /dev/null; then
    open http://localhost:8080
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:8080
elif command -v start &> /dev/null; then
    start http://localhost:8080
else
    echo "Please open http://localhost:8080 in your browser"
fi
