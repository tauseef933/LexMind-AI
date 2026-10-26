# LexMind AI frontend — built with Vite, served by nginx.
# Build:  docker build -t lexmind-frontend --build-arg VITE_API_URL=http://localhost:8000 frontend
# VITE_* values are compiled into the bundle, so they are build arguments.
# VITE_API_KEY therefore ends up public in the browser: it is a demo guard,
# not a secret (Docker's SecretsUsedInArgOrEnv warning is expected).

FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
ARG VITE_API_URL=http://localhost:8000
ARG VITE_API_KEY=
ENV VITE_API_URL=$VITE_API_URL \
    VITE_API_KEY=$VITE_API_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
