# Flutter web build for BelemConverse.
#
# Build with a custom API URL:
#   docker build \
#     --build-arg API_BASE_URL=https://api.example.com/api \
#     -t belem-converse-web .
#
# Result is a tiny nginx container serving the compiled web bundle.

# ---------- build stage ----------
FROM ghcr.io/cirruslabs/flutter:stable AS build

ARG API_BASE_URL=http://localhost:8000/api

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get

COPY . .
RUN flutter build web --release \
    --dart-define=API_BASE_URL=${API_BASE_URL}

# ---------- runtime stage ----------
FROM nginx:alpine AS runtime

COPY --from=build /app/build/web /usr/share/nginx/html

# SPA routing fallback so deep links don't 404 in nginx.
RUN printf 'server {\n\
    listen 80;\n\
    server_name _;\n\
    root /usr/share/nginx/html;\n\
    index index.html;\n\
    location / {\n\
        try_files $uri $uri/ /index.html;\n\
    }\n\
}\n' > /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ >/dev/null || exit 1
