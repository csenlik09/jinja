# Jinja App - Version Control Guide

This guide explains how to manage different versions of the Jinja application using the provided scripts.

## 📋 Quick Start

### 1. Deploy a New Version

```bash
./deploy.sh v1.1 "Added resizable preview feature"
```

This will:
- Commit your changes to Git with the description
- Create a Git tag (v1.1)
- Build a Docker image tagged with v1.1
- Deploy the new version
- Keep the last 5 versions automatically

### 2. List Available Versions

```bash
./list-versions.sh
```

Shows:
- Currently running version
- All available Docker images
- Recent Git tags

### 3. Rollback to Previous Version

```bash
./rollback.sh v1.0
```

This will:
- Stop the current container
- Start a container with the v1.0 image
- Optionally rollback Git to that tag

### 4. Backup Database

```bash
./backup-db.sh v1.0-stable
```

Creates a backup before major changes.

## 📚 Detailed Usage

### Version Naming Convention

Recommended version format:
- `v1.0` - Major stable release
- `v1.1` - Feature addition
- `v1.1.1` - Bug fix
- `v1.0-stable` - Stable version tag
- `v1.2-preview` - Preview/testing version

### Common Workflows

#### Workflow 1: Testing New Features

```bash
# 1. Make your changes
# 2. Deploy as a test version
./deploy.sh v1.2-test "Testing new feature"

# 3. If something breaks, rollback
./rollback.sh v1.1

# 4. If it works, deploy as stable
./deploy.sh v1.2 "New feature working"
```

#### Workflow 2: Creating a Stable Release

```bash
# 1. Backup database first
./backup-db.sh v1.0-stable

# 2. Deploy the stable version
./deploy.sh v1.0-stable "Stable release with preview and templates"

# 3. Verify it's working
# 4. This version is now tagged and saved
```

#### Workflow 3: Emergency Rollback

```bash
# 1. Check what versions you have
./list-versions.sh

# 2. Rollback to last known working version
./rollback.sh v1.0-stable

# 3. Fix the issue in code
# 4. Deploy as new version
./deploy.sh v1.1 "Fixed critical bug"
```

## 🔧 Advanced Usage

### Manual Docker Operations

```bash
# SSH to server
ssh 172.16.20.201

# List all images
docker images jinja-app

# Run specific version manually
docker stop jinja-template-app
docker rm jinja-template-app
docker run -d --name jinja-template-app \
    -p 80:80 \
    -v /root/jinja/templates:/app/templates \
    -v /root/jinja/static:/app/static \
    -v /root/jinja/database.db:/app/database.db \
    jinja-app:v1.0

# Delete old images
docker rmi jinja-app:v0.9
```

### Git Operations

```bash
# View all tags
git tag -l

# View tag details
git show v1.0

# Delete a tag (local and remote)
git tag -d v1.0
git push origin :refs/tags/v1.0

# Checkout a specific version
git checkout v1.0
```

## 📊 Version History Tracking

The system automatically keeps:
- **Git History**: All commits and tags in GitHub
- **Docker Images**: Last 5 versions on the server
- **Database Backups**: Manual backups in `./backups/` directory

## 🚨 Troubleshooting

### Container won't start after rollback

```bash
# Check logs
ssh 172.16.20.201 'docker logs jinja-template-app'

# Verify image exists
ssh 172.16.20.201 'docker images jinja-app'

# Try starting manually with more verbose output
ssh 172.16.20.201 'docker run -it jinja-app:v1.0 python app.py'
```

### Lost the working version

```bash
# List all available versions
./list-versions.sh

# Check Git history
git log --oneline --graph --decorate --all

# Try each recent version until you find the working one
./rollback.sh v1.0
# Test it, if not working:
./rollback.sh v0.9
# And so on...
```

### Disk space issues from too many images

```bash
# SSH to server and clean up
ssh 172.16.20.201

# Remove all old images except last 3
docker images jinja-app --format '{{.Tag}}' | grep -v latest | sort -V -r | tail -n +4 | xargs -I {} docker rmi jinja-app:{}

# Remove dangling images
docker image prune -f
```

## 💡 Best Practices

1. **Always backup before major changes**: Run `./backup-db.sh` first
2. **Use descriptive version tags**: `v1.1-fixed-preview` is better than `v1.1`
3. **Test new versions**: Use `-test` suffix before making it stable
4. **Keep stable versions**: Mark working versions with `-stable` suffix
5. **Document changes**: Use detailed descriptions in deploy commands
6. **Regular cleanup**: Old versions are auto-cleaned, but check occasionally

## 📝 Example Session

```bash
# Starting work on a new feature
./backup-db.sh v1.0-before-resize

# Deploy new feature
./deploy.sh v1.1-test "Testing resizable panels"

# Oops, something broke!
./rollback.sh v1.0-stable

# Fix the issue, deploy again
./deploy.sh v1.1 "Resizable panels working correctly"

# Mark as stable
./deploy.sh v1.1-stable "Stable version with resizable panels"

# Check current state
./list-versions.sh
```

## 🔐 Security Notes

- Scripts use SSH to connect to 172.16.20.201
- Ensure your SSH keys are properly configured
- Database backups are stored locally (not encrypted)
- Don't commit sensitive data to Git

## 📞 Support

If you encounter issues:
1. Check `./list-versions.sh` to see what's available
2. Review logs: `ssh 172.16.20.201 'docker logs jinja-template-app'`
3. Try rolling back to the last known working version
4. Check Git history for what changed: `git log --oneline`
