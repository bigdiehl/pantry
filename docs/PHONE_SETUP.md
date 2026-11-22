# Phone Setup

Install the app on a phone so it works like a normal app, offline included.

The app only installs from its HTTPS address, `https://frank.tail2844c6.ts.net`.
Tailscale provides that address and the connection to frank. `http://frank.local:5000`
works in a browser at home but cannot install, work offline, use the mic, or get notifications.

## 1. Server (once)

On frank, after `scripts/install_service.sh`:

```bash
scripts/setup_tailscale.sh
```

It installs Tailscale if needed, signs in (open the link it prints), and runs
`tailscale serve --bg 5000`. That setting survives reboots.

If it fails with a certificate error: in the [Tailscale admin console](https://login.tailscale.com/admin/dns),
turn on **MagicDNS** and **HTTPS Certificates**, then run it again.

Check: `tailscale serve status` shows `https://frank.<tailnet>.ts.net` proxying to `127.0.0.1:5000`.

## 2. Phone

1. Install **Tailscale** from the Play Store / App Store. Sign in with the same account
   and switch it on.
2. Open the app address in the browser:
   - Android: **Chrome**
   - iPhone: **Safari** (other browsers can't install apps on iOS)
3. Install:
   - Android: menu **⋮** > **Install app** (or **Add to Home screen** > **Install**)
   - iPhone: **Share** > **Add to Home Screen**
4. Open **The Diehl Menu** from the home screen.

Delete any older home screen shortcut made from `frank.local`.

## 3. First run

- **Offline recipes**: open the Recipes tab once while connected. Every recipe and photo
  is saved for offline use.
- **Weekly reminders**: Manage > Weekly plan > **Turn on for this device**, allow
  notifications, then **Send test**. On iPhone this only works from the installed app.
- **Voice input** in Chat: allow the microphone when asked.

## Day to day

- Tailscale needs to be on to open the app or change anything. Notifications arrive
  without it.
- Offline: the shopping list (last loaded) and all recipes still work. Selecting recipes,
  editing, chat, and import need a connection.
- Updates install themselves. If the app looks out of date after a change, close and
  reopen it twice.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Page won't load | Tailscale off on the phone, or frank down. Check the Tailscale app shows frank |
| No "Install app" option | Not on the `https://...ts.net` address, or not in Chrome/Safari |
| Notifications don't arrive | Re-do "Turn on for this device"; check Android notification settings for the app |
| Old version after update | Close and reopen the app twice |
