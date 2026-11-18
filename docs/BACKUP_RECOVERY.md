# Hub backup and disaster recovery (alpha.9)

The Hub ledger is SQLite and contains **sensitive data**: print payloads, hashed agent credentials, administrator password records and browser session digests. Keep backups local in a private, encrypted volume. Do **not** upload them to GitHub, CI artifacts, a public bucket, or support chats.

The Hub can remain running during **backup**: this command uses SQLite's online backup API for a consistent snapshot. **Restore requires stopping the Hub before switching to the restored DB.**

## Back up

Set the real database path (or use `DEVICESHARE_DB`) and a **new** destination. Replace the example paths with locations on your machine:

```bash
deviceshare-hub --db "$HOME/Library/Application Support/DeviceShare/deviceshare.db" \
  --backup-db "$HOME/PrivateBackups/deviceshare-2026-11-18.db"
deviceshare-hub --verify-db "$HOME/PrivateBackups/deviceshare-2026-11-18.db"
```

On Linux, `--db /var/lib/deviceshare/deviceshare.db` may be appropriate depending on how you installed the Hub. On Windows, the same flags work in PowerShell with full quoted Windows paths:

```powershell
& 'C:\Program Files\DeviceShare\deviceshare-hub.exe' --db 'C:\DeviceShareData\deviceshare.db' --backup-db "$env:USERPROFILE\PrivateBackups\deviceshare-backup.db"
```

Determine the actual database path from your Hub's `DEVICESHARE_DB` configuration. No database directory or data should be assumed from these examples.

Both backup and restore **refuse to overwrite** an existing file. Select a unique destination for each backup. On Unix, backups are created with file mode `0600`; on Windows, protect the directory with your account's ACL and encryption. Backup errors fail closed without publishing a partial snapshot.

## Restore to a new database path

1. Make an additional verified backup of the current working DB if available.
2. Stop **every** Hub process or service using the DB; leave agents stopped until the restored Hub is ready.
3. Verify the backup, then restore to an **unused** path, never an existing DB:

   ```bash
   deviceshare-hub --verify-db /secure/backups/deviceshare-backup.db
   deviceshare-hub --restore-db /secure/backups/deviceshare-backup.db \
     --restore-to /secure/recovery/deviceshare-restored.db
   deviceshare-hub --verify-db /secure/recovery/deviceshare-restored.db
   ```

4. Set `DEVICESHARE_DB` or `--db` for the Hub service to the new path. **Do not delete or replace the original database.**
5. Restart the Hub, confirm administrator login and station connectivity, inspect the last job statuses, and send one deliberate test page per approved station.

Any job marked `sent` at the time of backup is marked `unknown` on Hub startup. It may have reached hardware: **do not automatically resend it**. Check physical output with the operator first. Previously queued jobs also merit manual review after recovery.

## Ongoing controls

- Keep at least one recent, encrypted, off-host backup under an approved confidential storage policy; verify and test a restore regularly.
- Rotate backup files under your retention policy without deleting the last verified recovery point.
- Back up before an installer upgrade, then test that the agent and Hub point to the expected persistent data directories afterward.
- If a backup is exposed, treat it as a credential-security incident. Rotate station credentials, administrator access, and connected secrets; invalidate existing sessions.
- A successful integrity check proves SQLite consistency and DeviceShare table presence, **not** printer functionality, recovery time objective, or database compatibility with a future release.
