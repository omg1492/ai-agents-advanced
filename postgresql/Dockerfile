# Postgres 17 with pgvector (from base image) + Apache AGE built from source
# Base image provides pgvector; this layer adds AGE binaries and extension files.

FROM pgvector/pgvector:pg17

LABEL org.opencontainers.image.title="PostgreSQL 17 with pgvector + Apache AGE" \
      org.opencontainers.image.description="Custom Postgres image including pgvector and Apache AGE extension for graph queries" \
      org.opencontainers.image.source="https://github.com/tkubica12/advanced-ai-applications" \
      org.opencontainers.image.licenses="Apache-2.0"

ARG AGE_REF=master
ENV DEBIAN_FRONTEND=noninteractive

# Install build dependencies and PostgreSQL server headers, build and install AGE, then clean up
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        build-essential \
        postgresql-server-dev-17; \
    update-ca-certificates; \
    \
    # Clone AGE and checkout requested ref (tag/branch/commit). Use full clone to support arbitrary refs.
    git clone https://github.com/apache/age.git /tmp/age; \
    cd /tmp/age; \
    (git checkout "${AGE_REF}" || true); \
    make; \
    make install; \
    cd /; \
    rm -rf /tmp/age; \
    \
    # Remove build deps to keep image small
    apt-get purge -y --auto-remove git build-essential postgresql-server-dev-17; \
    rm -rf /var/lib/apt/lists/*

# Optional: document where AGE installs its files on Debian-based images
#  - Library: /usr/lib/postgresql/17/lib/age.so
#  - Extension: /usr/share/postgresql/17/extension/age.control, age--*.sql

# Usage reminder:
#  In your database, enable extensions (as superuser):
#    CREATE EXTENSION IF NOT EXISTS vector;  -- already present from base image
#    CREATE EXTENSION IF NOT EXISTS age;
#    LOAD 'age';
#  Then create a graph:
#    SELECT create_graph('dreamfarm');
