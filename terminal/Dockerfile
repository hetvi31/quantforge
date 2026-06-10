# Stage 1: Build React static assets
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency configs
COPY package.json ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source code
COPY . .

# Build assets
RUN npm run build

# Stage 2: Serve using Nginx
FROM nginx:alpine

# Copy assets from build stage to Nginx public html
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration if any, else use default port 80
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
