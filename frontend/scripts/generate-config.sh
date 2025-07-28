#!/bin/sh
# Docker startup script to generate runtime configuration
# Replace environment variables in config template
envsubst < /app/public/config.js.template > /app/public/config.js
# Start the web server
exec "$@"
