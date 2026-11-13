# Account activation and email/password sign-in (alpha.5 and later)

DeviceShare has two different kinds of credentials:

- **Administrator account** — an email and password used for the web Console. Only one local owner account can be activated per Hub in this alpha.
- **Host integration key and station tokens** — machine credentials used internally for Hub/Agent provisioning and automation. Existing private files and station tokens remain valid after you create an account. You do **not** paste the host key into the web browser.

No third-party identity service or email account is connected. The email is the login identifier; it does not receive reset links or verification messages in this alpha.

## Recommended flow on your Mac mini

1. Install the new Apple Silicon PKG (it installs /Applications/DeviceShare.app).
2. Open DeviceShare.app and select **Overview**.
3. Under **1. Select the Hub**, start or restart the local Hub. It listens on 127.0.0.1:8765.
4. Under **2. Create your administrator account**, enter your email, a password of at least 12 characters and its confirmation; choose **Activate administrator**.
5. The Mac app requests a one-time 10-minute activation code from its local Hub internally, then creates the account. You never need to copy a host API key into Chrome.
6. Under **3. Configure this station**, keep your existing station ID if it was already paired (do not rotate it needlessly).
7. Under **4. Pair the station**, pair only if there is no valid saved agent token. Then start/restart the Agent from **Services** and confirm it connects.
8. In your browser, visit **http://127.0.0.1:8765/dashboard**, sign in with your email/password, and optionally enable **Remember this computer**.
9. Select a printer in **Printers** and use **Print Studio** to test one physical page. A CUPS-accepted job is not necessarily printed.

**Upgrading from alpha.4:** Your existing SQLite database, print history, station IDs, and agent tokens are preserved. The prior browser API-key login must be replaced by one-time admin activation. The native app's local host key stays in the private Application Support directory for machine provisioning.

## Windows or Linux setup without the Mac GUI

The person who controls the Hub computer can generate an activation code locally.

On Debian/Ubuntu, where the Hub database is in its default location:

```bash
deviceshare-hub --issue-activation-code
```

If the Hub was started with a custom database location, specify that exact same database path:

```bash
DEVICESHARE_DB="/private/path/deviceshare.db" deviceshare-hub --issue-activation-code
```

For an existing macOS local-Hub installation, this points to the same data file used by the app:

```bash
DEVICESHARE_DB="$HOME/Library/Application Support/DeviceShare/deviceshare.db" \
  /usr/local/bin/deviceshare-hub --issue-activation-code
```

Open the Hub in a browser and enter your email, password and short-lived code on the activation screen. Generating another code invalidates the earlier code. Five failed code attempts require generating a fresh code.

## Signing in

- Use your owner email and password, not the host key.
- A remembered login is an opaque, HttpOnly, SameSite=Strict browser cookie; the server stores only a token digest. Your raw password is never stored in the Hub database; it is salted and hashed using scrypt.
- Sessions survive Hub restart when the same DB and host key are used; changing a password revokes all existing browser sessions.
- The account locks further password attempts for 60 seconds after five failures.
- Remote Hub sign-in **requires HTTPS**. The default local installation is loopback-only, not public.
- Sign out from **Settings → Signed-in browsers**. Use **Revoke all** after using an unfamiliar computer.

## Forgot password / recovery

Password recovery is **local-host controlled**, not an unverified email reset. On your Mac, open **DeviceShare.app → Settings → Generate recovery code**. Alternatively, run:

```bash
DEVICESHARE_DB="$HOME/Library/Application Support/DeviceShare/deviceshare.db" \
  /usr/local/bin/deviceshare-hub --issue-recovery-code
```

Then in the web sign-in screen choose **Forgot password**, enter the admin email, recovery code and a new password. Recovery codes expire after 10 minutes and can be used once. Resetting the password revokes all active browser sessions.

## Security limitations

This is **single-owner local-first alpha authentication**, not enterprise SSO, multi-user RBAC, OAuth or an identity-provider integration. The native app and API integrations still have a separate private Host key; treat anyone who can access that file and the local Hub database as a trusted machine administrator. There is no email verification, automatic email delivery or backup of lost passwords. Keep physical and OS-level access to the Hub restricted.

Do not expose the Hub on an untrusted network. Keep your Mac's system account protected and the database, agent tokens and host key file private. Never share screenshots of setup/recovery codes, password fields or tokens.
