# Port Registry

Keep track of all running applications and their ports.

## Active Applications

| Port | Application | Container Name | Status | URL |
|------|-------------|----------------|--------|-----|
| 8080 | Jinja2 Config Tool | jinja-template-app | Active | http://localhost:8080 |
| 8081 | - | - | Available | - |
| 8082 | - | - | Available | - |
| 3000 | - | - | Available | - |
| 5000 | - | - | Available | - |

## Quick Commands

### Check Running Containers
```bash
docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"
```

### Check Port Usage
```bash
lsof -i :8080
```

### Start Jinja App
```bash
docker start jinja-template-app
```

### Stop Jinja App
```bash
docker stop jinja-template-app
```

### Change Jinja App Port
```bash
# Stop and remove current
docker stop jinja-template-app
docker rm jinja-template-app

# Run on new port (example: 8081)
docker run -d -p 8081:80 --name jinja-template-app jinja-app
```

## Port Conflict Resolution

If you get "port already allocated" error:

1. **Find what's using the port:**
   ```bash
   lsof -i :8080
   ```

2. **Stop the conflicting service:**
   ```bash
   # If it's a Docker container
   docker stop <container-name>

   # If it's another process
   kill <PID>
   ```

3. **Or use a different port**

## Reserved Ports (Don't Use)

- 22: SSH
- 80: HTTP (requires sudo)
- 443: HTTPS (requires sudo)
- 3306: MySQL default
- 5432: PostgreSQL default

## Recommended Available Ports

Safe ports to use for your apps:
- 8080-8089: Web applications
- 3000-3009: API services
- 9000-9009: Development/testing
