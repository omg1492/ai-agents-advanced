# Build stage
FROM node:22-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application (using npx to ensure proper execution)
RUN npx tsc && npx vite build

# Production stage
FROM nginx:alpine

# Install envsubst for config generation
RUN apk add --no-cache gettext

# Copy built app to nginx
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy config template and generation script
COPY --from=build /app/public/config.js.template /usr/share/nginx/html/config.js.template
COPY --from=build /app/scripts/generate-config.sh /usr/local/bin/generate-config.sh

# Make script executable
RUN chmod +x /usr/local/bin/generate-config.sh

# Set default environment variables
ENV REACT_APP_BACKEND_URL=http://localhost:8001
ENV REACT_APP_API_VERSION=v1
ENV REACT_APP_KEYCLOAK_URL=http://localhost:8080
ENV REACT_APP_KEYCLOAK_REALM=dreamfarm
ENV REACT_APP_KEYCLOAK_CLIENT_ID=dreamfarm-frontend
ENV REACT_APP_KEYCLOAK_REDIRECT_URI=http://localhost:3000/

# Expose port
EXPOSE 80

# Use our script as entrypoint
ENTRYPOINT ["/usr/local/bin/generate-config.sh"]
CMD ["nginx", "-g", "daemon off;"]
