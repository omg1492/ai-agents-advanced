# Advanced AI Applications

This repository contains advanced AI applications and services with a focus on practical implementations.

## Quick Start

### Database Setup (PostgreSQL)

1. Start PostgreSQL with Docker Compose:
   ```bash
   # Copy environment template
   cp .env.template .env
   
   # Edit .env and set secure password
   # Then start PostgreSQL
   docker-compose up -d postgres
   ```

2. The database will be available at `localhost:5432` with persistent data stored in `./data/postgres/`

For detailed database setup instructions, see [data/README.md](data/README.md).

## Project Structure

- `agents/` - AI agents and services
- `data/` - Database setup and data processing scripts
- `frontend/` - React-based user interface
- `deploy/` - Deployment configurations
- `docs/` - Project documentation 