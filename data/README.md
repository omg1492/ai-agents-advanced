# PostgreSQL Docker Setup

This directory contains the Docker Compose configuration for running PostgreSQL with persistent data storage.

## Quick Start

1. **Copy environment variables:**
   ```bash
   cp .env.template .env
   ```

2. **Edit the `.env` file** and set a secure password:
   ```bash
   POSTGRES_PASSWORD=your_actual_secure_password
   ```

3. **Start PostgreSQL:**
   ```bash
   docker-compose up -d postgres
   ```

4. **Connect to the database:**
   ```bash
   # Using psql
   docker exec -it advanced-ai-postgres psql -U postgres -d advanced_ai_db
   
   # Or using any PostgreSQL client on localhost:5432
   ```

## Data Persistence

- **Data Location:** PostgreSQL data is stored in `./data/postgres/` directory
- **Initialization Scripts:** Place any `.sql` or `.sh` files in `./data/init/` to run them on first startup
- **Backup:** The `./data/postgres/` directory contains all your database data

## Management Commands

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Stop PostgreSQL
docker-compose down

# View logs
docker-compose logs postgres

# Restart PostgreSQL
docker-compose restart postgres

# Access PostgreSQL shell
docker exec -it advanced-ai-postgres psql -U postgres -d advanced_ai_db
```

## Backup and Restore

### Backup
```bash
# Create a SQL dump
docker exec advanced-ai-postgres pg_dump -U postgres advanced_ai_db > backup.sql

# Or backup the entire data directory
tar -czf postgres-backup-$(date +%Y%m%d_%H%M%S).tar.gz ./data/postgres/
```

### Restore
```bash
# Restore from SQL dump
cat backup.sql | docker exec -i advanced-ai-postgres psql -U postgres -d advanced_ai_db

# Or restore data directory (stop container first)
docker-compose down
tar -xzf postgres-backup-YYYYMMDD_HHMMSS.tar.gz
docker-compose up -d postgres
```

## Configuration

- **Database:** `advanced_ai_db`
- **User:** `postgres`
- **Port:** `5432` (mapped to host)
- **Data Directory:** `./data/postgres/`
- **Init Scripts Directory:** `./data/init/`

## Health Check

The container includes a health check that verifies PostgreSQL is ready:
```bash
# Check container health
docker inspect advanced-ai-postgres --format='{{.State.Health.Status}}'
```

## Troubleshooting

### Permission Issues
If you encounter permission issues on Linux/macOS:
```bash
sudo chown -R 999:999 ./data/postgres/
```

### Connection Issues
1. Ensure the container is running: `docker-compose ps`
2. Check logs: `docker-compose logs postgres`
3. Verify port 5432 is not used by another service

### Data Not Persisting
1. Verify the volume mount in `docker-compose.yml`
2. Check that `./data/postgres/` directory exists and has proper permissions
3. Ensure you're not accidentally using anonymous volumes

## Security Notes

- Change the default password in `.env` file
- Consider using secrets management for production
- The database is only accessible on localhost by default
- For production, consider enabling SSL/TLS
