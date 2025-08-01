# Local Development Environment

This directory contains Docker Compose configuration for local development.

## PostgreSQL Database

### Quick Start

1. Start PostgreSQL database:
   ```bash
   docker-compose up -d
   ```

2. Stop the database:
   ```bash
   docker-compose down
   ```

3. View logs:
   ```bash
   docker-compose logs postgres
   ```

### Database Configuration

- **Database Name**: `advanced_ai_db`
- **Username**: `admin`
- **Password**: `admin123`
- **Port**: `5432`
- **Host**: `localhost`

### Data Persistence

PostgreSQL data is persisted in `./data/postgres/` directory, which is mapped to the container's data directory. This ensures your data survives container restarts.

### Connection Examples

**Python (using psycopg2):**
```python
import psycopg2

conn = psycopg2.connect(
    host="localhost",
    database="advanced_ai_db",
    user="admin",
    password="admin123",
    port="5432"
)
```

**Connection String:**
```
postgresql://admin:admin123@localhost:5432/advanced_ai_db
```

### Health Check

The PostgreSQL container includes a health check that verifies the database is ready to accept connections. You can check the status with:

```bash
docker-compose ps
```