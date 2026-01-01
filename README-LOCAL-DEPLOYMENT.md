# Jinja2 Network Config Tool - Local Deployment Guide

## Quick Start (3 Steps)

### Prerequisites
- **Docker Desktop** - [Download here](https://www.docker.com/products/docker-desktop)
- **Git** - Already installed on Mac/Linux

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/csenlik09/jinja.git
   cd jinja
   ```

2. **Make scripts executable (Mac/Linux):**
   ```bash
   chmod +x local-deploy.sh local-update.sh
   ```

3. **Deploy:**
   ```bash
   ./local-deploy.sh
   ```

That's it! The application will open in your browser at `http://localhost`

---

## Updating to Latest Version

When a new version is released, simply run:

```bash
./local-update.sh
```

This will:
- Pull the latest code from GitHub
- Rebuild the Docker image
- Restart the application
- Show you the current version

---

## Manual Deployment (If scripts don't work)

```bash
# 1. Clone repository
git clone https://github.com/csenlik09/jinja.git
cd jinja

# 2. Build Docker image
docker build -t jinja-app .

# 3. Run container
docker run -d -p 80:80 --name jinja-template-app jinja-app

# 4. Open browser
open http://localhost  # macOS
# or
start http://localhost  # Windows
```

---

## Useful Commands

### View Application Logs
```bash
docker logs jinja-template-app
```

### View Live Logs (follow mode)
```bash
docker logs -f jinja-template-app
```

### Stop Application
```bash
docker stop jinja-template-app
```

### Start Application
```bash
docker start jinja-template-app
```

### Restart Application
```bash
docker restart jinja-template-app
```

### Remove Application
```bash
docker stop jinja-template-app
docker rm jinja-template-app
```

### Check if Application is Running
```bash
docker ps | grep jinja-template-app
```

---

## Troubleshooting

### Docker not running
**Error:** `Cannot connect to the Docker daemon`

**Solution:** Start Docker Desktop and wait for it to fully start

### Port 80 already in use
**Error:** `Bind for 0.0.0.0:80 failed: port is already allocated`

**Solution:** Use a different port:
```bash
docker run -d -p 8080:80 --name jinja-template-app jinja-app
```
Then access at: `http://localhost:8080`

### Permission denied on scripts
**Error:** `Permission denied: ./local-deploy.sh`

**Solution:**
```bash
chmod +x local-deploy.sh local-update.sh
```

### Container already exists
**Error:** `The container name "/jinja-template-app" is already in use`

**Solution:**
```bash
docker stop jinja-template-app
docker rm jinja-template-app
./local-deploy.sh
```

---

## Features

- **Config Generator** - Upload Excel files and generate network configurations
- **Template Manager** - Create and manage Jinja2 templates with versioning
- **Jinja Tester** - Test templates with sample data
- **Logs** - View application logs with advanced filtering

---

## Database

Your local database is stored inside the Docker container. If you want to persist data:

### Export Database
1. Open the app at `http://localhost`
2. Go to **Manage Templates** tab
3. Click **Backup** button
4. Save the `.db` file

### Import Database
1. Click **Restore** button
2. Select your `.db` file

---

## Support

For issues or questions:
- Check the **Logs** tab in the application
- View Docker logs: `docker logs jinja-template-app`
- Contact: [Your contact info]

---

## Version Information

Current version is displayed in the application header.

To check version from command line:
```bash
git describe --tags
```

---

## System Requirements

- **macOS:** 10.15 or later
- **Windows:** Windows 10 64-bit or later
- **Linux:** Any modern distribution with Docker support
- **RAM:** 2GB minimum
- **Disk Space:** 500MB

---

## What's New

### v1.5 (Current)
- ✅ Application logging system with advanced filtering
- ✅ Search logs by keyword
- ✅ Filter logs by date/time range and level
- ✅ Dynamic version display
- ✅ US date format with UTC timezone

### v1.4
- ✅ Template versioning system
- ✅ Database backup/restore
- ✅ Port cleaning (auto-remove "Port-" prefix)

### v1.3
- ✅ Preview error highlighting
- ✅ Accurate row counts
- ✅ UI improvements

---

## License

[Your license here]
