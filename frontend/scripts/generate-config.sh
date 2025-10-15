#!/bin/sh
# Docker startup script to generate runtime configuration
# Replace environment variables in config template
envsubst < /usr/share/nginx/html/config.js.template > /usr/share/nginx/html/config.js
# Start the web server
exec "$@"
