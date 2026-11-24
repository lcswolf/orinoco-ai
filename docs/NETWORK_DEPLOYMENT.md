# Network and reverse-proxy deployment plan

**Status: configuration design and templates only. Nothing in this guide has been applied to the Leaseweb VPS yet.** The host address, Pterodactyl allocation, domain and actual Docker bridge addresses must be confirmed during the live deployment.

This design preserves three access paths without weakening Orinoco's secure session cookie:

1. Public subdomain: `https://ORINOCO_DOMAIN/` on TCP 443.
2. Public IP and port: `https://PUBLIC_IPV4:8443/`.
3. Private tailnet URL: the server's Tailscale DNS name on HTTPS port 8444.

All three terminate TLS before reaching Orinoco. Keep `ORINOCO_COOKIE_SECURE=true` (the default). Do not make the production session cookie available over plain HTTP just to support a raw-IP URL.

## Request path

```text
Public browser
  ├── https://ORINOCO_DOMAIN:443 ─────────────┐
  └── https://PUBLIC_IPV4:8443 ───────────────┤
                                               v
                                        Caddy (TLS)
                                               |
                                               v
                                  Nginx 127.0.0.1:8081
                                  - real client IP from Caddy
                                  - request-body limits
                                  - per-IP rate and connection limits
                                               |
                                               v
                                  Pterodactyl allocation on host
                                               |
                                               v
                                  Orinoco container / Uvicorn

Tailnet browser
  └── https://SERVER.TAILNET.ts.net:8444
          |
          v
       Tailscale Serve (tailnet only)
          |
          v
       Nginx 127.0.0.1:8081
```

Caddy is the public TLS endpoint. Nginx is deliberately placed behind it because stock Caddy does not provide the Nginx-style per-client HTTP request limiting used in this plan. Nginx listens on loopback only; it must not be reachable directly from the internet. Tailscale Serve is a separate tailnet-only ingress to that same local Nginx listener.

## 1. Nginx edge limits

Install Nginx on the VPS host, not inside the Orinoco container. The example below assumes:

- Nginx listens on `127.0.0.1:8081`.
- Caddy is the only public reverse proxy and connects from `127.0.0.1`.
- The Pterodactyl host allocation assigned to Orinoco is `28080`. Replace this with the actual allocation.
- Caddy overwrites/sets the forwarded client address; Nginx trusts forwarded addresses only from loopback.

Place the `limit_req_zone` and `limit_conn_zone` directives inside Nginx's `http` context (for example, in a file included from `/etc/nginx/conf.d/`):

```nginx
# Per-client edge limits. The application also has account-scoped limits.
limit_req_zone $binary_remote_addr zone=orinoco_login:10m rate=5r/m;
limit_req_zone $binary_remote_addr zone=orinoco_chat:10m rate=20r/m;
limit_req_zone $binary_remote_addr zone=orinoco_api:10m rate=60r/m;
limit_conn_zone $binary_remote_addr zone=orinoco_connections:10m;

upstream orinoco_app {
    server 127.0.0.1:28080; # Replace with the actual Pterodactyl allocation.
    keepalive 16;
}

server {
    listen 127.0.0.1:8081;
    server_name _;

    # Trust the forwarding header only from the local Caddy process.
    set_real_ip_from 127.0.0.1;
    real_ip_header X-Forwarded-For;
    real_ip_recursive on;

    client_max_body_size 12m;
    client_body_timeout 20s;
    limit_conn orinoco_connections 20;
    limit_req_status 429;
    limit_conn_status 429;

    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    # Replace any incoming chain with the address Nginx resolved from Caddy.
    proxy_set_header X-Forwarded-For $remote_addr;
    proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
    proxy_set_header Connection "";

    proxy_connect_timeout 5s;
    proxy_send_timeout 30s;
    # Local model generation can be slow on the planned small VPS.
    proxy_read_timeout 300s;
    send_timeout 300s;
    proxy_buffering off;

    location = /api/auth/login {
        limit_req zone=orinoco_api burst=20 nodelay;
        limit_req zone=orinoco_login burst=5 nodelay;
        proxy_pass http://orinoco_app;
    }

    location = /api/chat {
        limit_req zone=orinoco_api burst=30 nodelay;
        limit_req zone=orinoco_chat burst=10 nodelay;
        proxy_pass http://orinoco_app;
    }

    # Allow multipart overhead, but not an unbounded upload body.
    location ^~ /api/documents {
        client_max_body_size 11m;
        limit_req zone=orinoco_api burst=20 nodelay;
        proxy_pass http://orinoco_app;
    }

    location ^~ /api/admin/shared-documents {
        client_max_body_size 11m;
        limit_req zone=orinoco_api burst=20 nodelay;
        proxy_pass http://orinoco_app;
    }

    location ^~ /api/ {
        limit_req zone=orinoco_api burst=30 nodelay;
        proxy_pass http://orinoco_app;
    }

    location / {
        proxy_pass http://orinoco_app;
    }
}
```

The Nginx API and login/chat limits are intentionally conservative starting values. Review access logs and adjust them after a real test; do not remove the account-scoped Orinoco limits. The global 12 MiB limit matches the application's declared-body guard, while upload routes are capped at 11 MiB to leave room for multipart overhead above the 10 MiB file limit.

Validate the file before reload with `nginx -t`. Confirm the real client IP appears in Nginx's access log. If it always shows loopback, stop and fix the proxy chain rather than trusting arbitrary `X-Forwarded-For` values.

## 2. Caddy public HTTPS

Use a current Caddy 2.11 release from the official Caddy repository. Replace the example domain and public IPv4 address with the actual values. Keep Caddy's certificate and state directory persistent and protected.

Example Caddyfile:

```caddyfile
{
    email {$ACME_EMAIL}
    # Some clients omit SNI when connecting to a literal IP address.
    default_sni {$ORINOCO_PUBLIC_IPV4}
}

{$ORINOCO_DOMAIN} {
    reverse_proxy 127.0.0.1:8081 {
        # Do not preserve a client-supplied X-Forwarded-For value.
        header_up X-Forwarded-For {remote_host}
    }
}

https://{$ORINOCO_PUBLIC_IPV4}:8443 {
    tls {
        issuer acme {
            profile shortlived
        }
    }

    reverse_proxy 127.0.0.1:8081 {
        header_up X-Forwarded-For {remote_host}
    }
}
```

Use a DNS-only A record for the first deployment so Caddy sees the real
connecting client. If a CDN or DNS-provider HTTP proxy is later placed in front
of Caddy, configure Caddy's trusted-proxy CIDRs for that provider and test the
full forwarded-header chain; do not simply trust all forwarded headers.

The subdomain uses Caddy's normal automatic HTTPS. The IP listener uses a Let's Encrypt IP-address certificate with the `shortlived` ACME profile. These IP certificates are valid for 160 hours (a little over six days), so Caddy must be allowed to renew them automatically. Use the public static IPv4 address, Caddy 2.11 or newer, and ensure the host can receive ACME validation traffic on TCP 80 and 443. The browser URL is `https://PUBLIC_IPV4:8443/`; port 8443 is the user-facing Orinoco IP-access port, not the Pterodactyl allocation.

Do not assume IP certificate issuance has succeeded just because Caddy starts. Check Caddy's logs and verify the certificate from an external device with a normal browser or `curl`. If the certificate cannot be issued, do not silently fall back to HTTP or disable Secure cookies; use the subdomain or Tailscale path until the IP certificate issue is resolved.

## 3. Private Tailscale access

Install and authenticate Tailscale on the VPS, enable HTTPS certificates for the tailnet, and apply tailnet access-control rules so only approved devices/users can reach Orinoco.

The intended Serve target is the local Nginx listener on a separate tailnet HTTPS port:

```bash
sudo tailscale serve --bg --https=8444 http://127.0.0.1:8081
sudo tailscale serve status
sudo tailscale funnel status
```

Use the HTTPS tailnet DNS name shown by `tailscale serve status`, including port 8444. Confirm the Serve status is private to the tailnet and that Funnel has no active public listener. Do not run `tailscale funnel` for Orinoco. Tailscale Serve requires HTTPS certificates to be enabled in the tailnet; its access-control rules apply to served services. If the VPS is rebuilt, re-check the Serve configuration rather than assuming it persisted.

## 4. Network and firewall boundaries

The intended public inbound ports are:

| Port | Purpose | Public exposure |
| --- | --- | --- |
| TCP 80 | ACME HTTP validation and HTTPS redirect | Yes |
| TCP 443 | Subdomain HTTPS and ACME TLS-ALPN validation | Yes |
| TCP 8443 | HTTPS by public IP address | Yes |
| TCP 22 | SSH administration | Restricted source addresses or tailnet |
| UDP 41641 | Optional direct Tailscale connectivity | Only if required by the Tailscale setup |
| TCP 8081 | Local Nginx reverse-proxy listener | Loopback only |
| Pterodactyl allocation | Orinoco container web process | Host-local proxy access only; block direct public access |
| TCP 11434 | Ollama API | Container loopback only; never public |

Pterodactyl/Wings and Docker publish allocated ports through Docker networking. Do not assume a basic UFW deny rule blocks a published container port: Docker may route published traffic around UFW's normal INPUT path. On the live node, inspect Docker's published-port bindings and firewall chains (including `DOCKER-USER` where applicable), then test from a genuinely external host that the Orinoco allocation cannot be reached directly. Only the proxy path should be reachable. Keep the Panel and Wings management ports limited to the administrator's approved network.

Do not expose the Nginx listener, SQLite database, data directory, Ollama port, or backup storage. Do not create an allocation for Ollama.

## 5. Uvicorn forwarded-header policy

The container startup command explicitly uses `--no-proxy-headers`. This is deliberate: until the actual source address of the trusted host proxy is measured on the live Pterodactyl network, Orinoco must not accept client-supplied forwarded headers as identity or scheme information. Nginx performs the per-client IP limits at the edge. Application-level chat/login limits remain additional safeguards, but their observed client IP may be the container gateway behind this topology.

Do not change Uvicorn to trust `*` or all forwarded headers. If a later deployment needs the app to use forwarded client IPs, measure the exact proxy peer address from inside the container, allow-list only that address (or a narrowly scoped proxy subnet), and test spoofed `X-Forwarded-For` requests from an untrusted source before enabling proxy-header processing.

## 6. Live deployment verification checklist

- [ ] Confirm the Leaseweb public IPv4 address is static and the subdomain A record points to it.
- [ ] Confirm IPv6 only if the VPS, firewall, DNS and proxy are all configured for it; otherwise do not publish an AAAA record.
- [ ] Confirm the actual Pterodactyl allocation and that the container listens on that assigned port.
- [ ] Install Caddy 2.11+ and Nginx on the host; preserve their config and certificate state.
- [ ] Run `nginx -t` and Caddy's configuration validation before reloading either service.
- [ ] Verify subdomain HTTPS and public IP HTTPS from outside the VPS, including automatic certificate renewal behaviour.
- [ ] Verify Nginx sees the real public client IP and that login/chat/API rate limits return 429 when exceeded.
- [ ] Verify an oversized/chunked upload is rejected by Nginx before FastAPI multipart parsing.
- [ ] Verify the Pterodactyl allocation, Nginx 8081 and Ollama 11434 are not reachable directly from the public internet.
- [ ] Verify `orinoco_session` is marked Secure and sign-in persists on all three HTTPS access paths.
- [ ] Verify Tailscale Serve works from an authorised tailnet device and fails from a device outside the tailnet.
- [ ] Verify Funnel has no active listener.
- [ ] Reboot the VPS and confirm Caddy, Nginx, Tailscale and the Pterodactyl server return in the correct order.

## Official references

- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Caddy reverse-proxy forwarded-header behaviour](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy)
- [Let's Encrypt IP-address and 6-day certificates](https://letsencrypt.org/2026/01/15/6day-and-ip-general-availability/)
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
- [Tailscale Serve CLI reference](https://tailscale.com/docs/reference/tailscale-cli/serve)

No public deployment should proceed until these checks are completed on the actual Leaseweb/Pterodactyl host.
