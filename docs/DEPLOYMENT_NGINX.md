# Nginx reverse proxy setup for SHIOL-PLUS

This guide helps you proxy the FastAPI app with Nginx and avoid common 404s.

## 1) App process
- The app listens on 0.0.0.0:8000 by default (configurable via HOST/PORT envs).
- Health endpoints:
  - Simple: GET /health
  - Namespaced: GET /api/v1/health
  - Routes debug: GET /api/v1/debug/routes

Start locally (systemd or a process manager in prod):
- python main.py

## 2) Basic Nginx site config (root path)
Proxy everything at “/” to the app. This lets FastAPI serve static files from `frontend/`.

server {
    listen 80;
    server_name your-domain.example.com;  # update

    # Optional: increase default headers size for auth cookies
    large_client_header_buffers 4 16k;

    location / {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 60s;
        proxy_connect_timeout 5s;

        proxy_pass http://127.0.0.1:8000;
    }
}

Reload Nginx:
- sudo nginx -t && sudo systemctl reload nginx

Validate:
- curl -i http://your-domain/health
- curl -i http://your-domain/api/v1/health
- curl -i http://your-domain/api/v1/debug/routes

If these 200 OK, the app is reachable via Nginx.

## 3) If you need a subpath (e.g., /shiol)
Choose exactly one of these approaches.

A) Configure FastAPI root_path and Nginx location:
- Start Uvicorn with `--root-path /shiol` (or set `app = FastAPI(root_path="/shiol")`).
- Nginx:

server {
    listen 80;
    server_name your-domain.example.com;

    location /shiol/ {
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_buffering off;
        proxy_read_timeout 60s;
        proxy_connect_timeout 5s;

        proxy_pass http://127.0.0.1:8000/;
    }
}

B) Keep app at root and rewrite in Nginx (not recommended):
- Use `rewrite ^/shiol/(.*)$ /$1 break;` inside the location.

## 4) Common 404 causes and fixes
- You see Nginx’s default 404 page: your request didn’t match any `server_name`.
  - Fix: Ensure `server_name` matches the hostname, or add `default_server` on the right `server`.
- You see a 404 on `GET /` but API endpoints work: a separate `root`/`try_files` block is serving files instead of the proxy.
  - Fix: Remove `root`/`try_files` for `/` and just `proxy_pass` to the app.
- API 404s when deployed under a subpath: missing FastAPI `root_path` or wrong `location` prefix.
  - Fix: Set `--root-path` and use `location /<prefix>/`.
- 502/504: upstream not running or wrong port.
  - Fix: `curl http://127.0.0.1:8000/health` from the Nginx host.

## 5) TLS (optional)
Terminate TLS at Nginx and keep the same proxy settings. Make sure to set `secure=True` cookies in production (already handled by ENVIRONMENT=production in the app).

## 6) Static files
The app already serves the frontend from `frontend/` at `/`. Avoid adding a separate `alias`/`root` unless you know you want Nginx to serve static directly. If you do:

location /static/ {
    alias /path/to/SHIOL-PLUS/frontend/static/;
    expires 6h;
    add_header Cache-Control "public";
}

But prefer proxying to the app to keep PWA/service worker logic consistent.
