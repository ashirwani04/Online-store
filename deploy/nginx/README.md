# Nginx for Linode

The app listens on **127.0.0.1:5000** when using `docker compose` (`5000:8000`).

## Install

1. Edit `online-store.conf` and replace `YOUR_DOMAIN` with your domain (or use `_` for any host during testing).
2. Copy the config and reload nginx:

```bash
sudo cp deploy/nginx/online-store.conf /etc/nginx/sites-available/online-store
sudo ln -sf /etc/nginx/sites-available/online-store /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

3. Set `APPLICATION_ROOT=/onlinestore` on the **web** service in `docker-compose.yml` (or in a `.env` file) so Flask generates correct URLs.

## Timeouts

`proxy_read_timeout`, `proxy_connect_timeout`, and `proxy_send_timeout` are set to **300s** to match Gunicorn’s `--timeout 300` and avoid **504 Gateway Timeout** during slow semantic search (first Chroma model load).

If you use **Cloudflare** in front of Linode, you may also need a higher origin timeout in the Cloudflare dashboard (Enterprise) or accept that very long first searches can still fail at the CDN layer.

## Serve at site root instead of `/onlinestore`

Use a root `location /` block and omit `APPLICATION_ROOT` / `X-Forwarded-Prefix`. See comments in `online-store-root.conf` if added, or change `location` to:

```nginx
location / {
    proxy_pass http://online_store_app;
    # same proxy_set_header lines except X-Forwarded-Prefix
}
```
