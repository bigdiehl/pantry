# Remote Access Options

How to safely access your recipe server from outside your home network.

## Recommended Options

### Tailscale (Best for Personal/Family)

**Secure VPN mesh network. No port forwarding needed.**

```bash
# On server
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Users install Tailscale app, join your network
# Access: http://server-name:5000
```

**Pros:** Very secure, zero config, free for personal use (100 devices)
**Cons:** Users need Tailscale app, not public
**Security:** ⭐⭐⭐⭐⭐

---

### Cloudflare Tunnel (Best for Public Access)

**Encrypted tunnel through Cloudflare. Gets you a public URL.**

```bash
# Install
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Setup
cloudflared tunnel login
cloudflared tunnel create recipes
cloudflared tunnel route dns recipes recipes.yourdomain.com
cloudflared tunnel run recipes --url http://localhost:5000
```

**Pros:** Public URL, HTTPS included, no ports opened, DDoS protection
**Cons:** Needs domain name ($10-15/year)
**Security:** ⭐⭐⭐⭐⭐

---

### WireGuard VPN (Self-Hosted)

**Modern VPN server. Users VPN in to access server.**

```bash
sudo apt install wireguard
# Configure server and clients (see WireGuard docs)
```

**Pros:** Fast, secure, full control, open source
**Cons:** Port forwarding required, complex setup, exposes home IP
**Security:** ⭐⭐⭐⭐⭐

---

### ngrok (Quick Testing)

**Instant public URL. Good for testing/demos.**

```bash
snap install ngrok
ngrok http 5000
# Use the https URL provided
```

**Pros:** Instant, no config, HTTPS included
**Cons:** Random URLs on free tier, paid for permanent ($8+/month)
**Security:** ⭐⭐⭐⭐

---

### Traditional Reverse Proxy (nginx/Caddy)

**Standard web hosting. Port forward 443, use reverse proxy with SSL.**

```bash
# Caddy (easiest)
sudo apt install caddy

# /etc/caddy/Caddyfile
recipes.yourdomain.com {
    reverse_proxy localhost:5000
}

# Port forward 80, 443 on router
```

**Pros:** Standard approach, free SSL (Let's Encrypt), full control
**Cons:** Exposes server to internet, requires security hardening, exposes home IP
**Security:** ⭐⭐⭐ (if properly hardened)

**Required security measures:**
- Firewall configured
- Regular updates
- fail2ban installed
- Strong authentication
- Rate limiting

---

## Quick Comparison

| Option | Best For | Security | Ease | Public | Cost |
|--------|----------|----------|------|--------|------|
| **Tailscale** | Personal/Family | Highest | Easy | No | Free |
| **Cloudflare Tunnel** | Public site | Highest | Medium | Yes | Domain |
| **WireGuard** | Tech users | Highest | Hard | No | Free |
| **ngrok** | Testing | High | Easiest | Yes | $8+/mo |
| **Reverse Proxy** | Traditional hosting | Medium | Medium | Yes | Free/Domain |

## Recommendations

**Personal use, family/friends:**
→ **Tailscale** - Most secure, easiest

**Public recipe sharing site:**
→ **Cloudflare Tunnel** - Secure, professional, no port forwarding

**Full control, self-hosted:**
→ **WireGuard** - Open source, very secure

**Quick test/demo:**
→ **ngrok** - Instant setup

## Security Rules

- ✅ Use HTTPS in production
- ✅ Keep server updated
- ✅ Use strong authentication if public
- ✅ Monitor access logs
- ❌ Never port forward Flask directly
- ❌ Never skip HTTPS for public access
- ❌ Never use default passwords

## PWA Requirements

For mobile PWA installation, you need HTTPS. Options:

**Development/Testing:**
- Tailscale (works without HTTPS for private access)
- ngrok (provides HTTPS)

**Production:**
- Cloudflare Tunnel (automatic HTTPS)
- Reverse proxy with Let's Encrypt
- Tailscale Funnel

## Next Steps

**Try Tailscale (5 minutes):**
```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

**Setup Cloudflare Tunnel:**
1. Get domain name
2. Point to Cloudflare DNS
3. Install cloudflared
4. Create tunnel

**Harden for Public Access:**
1. Setup firewall (ufw)
2. Install fail2ban
3. Add authentication
4. Enable rate limiting
5. Regular security updates

## Resources

- Tailscale: https://tailscale.com/kb
- Cloudflare Tunnel: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps
- WireGuard: https://www.wireguard.com/quickstart
- Caddy: https://caddyserver.com/docs
