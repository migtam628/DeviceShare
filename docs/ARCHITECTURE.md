# DeviceShare architecture (alpha)

```text
Storefront / ERP / POS / automation
          |
       HTTPS API (X-API-Key)
          |
  DeviceShare Hub + SQLite
          |
     outbound WSS
          |
    DeviceShare Agent
        /     |      \
    CUPS / Win32 Serial   USB inventory
    Printers        (USB writes disabled)
```

## Separation of responsibility

- **Hub:** authenticated API, per-agent hashed token registry with rotation/revocation, validated jobs, idempotency keys, durable SQLite queue, result audit trail, connected-agent registry, and web dashboard.
- **Agent:** outbound connection only, read-only device discovery, exact local allowlists, limited supported device operations.
- **Backends:** simulated printer, CUPS raw/PDF/PNG printing, Windows RAW spooler printing, and serial request/response.
- **USB:** listing only in alpha. USB bulk/control/HID commands are NOT implemented.

## Job states and reliability

`queued` means the hub has saved a job; `sent` means the hub attempted delivery; `accepted` means the agent accepted the operation (for print jobs this means OS spooler submission, **not** a physical print success); `failed` means agent execution failed; `unknown` means the connection was lost after attempted delivery, before confirmation.

**Unknown jobs are not automatically retried.** Blind retries can print duplicate shipping labels, trigger a duplicate cash-drawer action, or repeat another physical action. The caller should reconcile the device state first, then explicitly create a new job if safe.

The alpha hub uses a single-process, single-worker WebSocket registry. Paired agents use individual tokens, and rotation or revocation disconnects an active agent. SQLite persists jobs across restarts, but jobs in `sent` during an unexpected hub crash must be reconciled before replay. A production version needs startup recovery into `unknown`, service identity, delivery receipts and device-level dedupe when supported.

## Security boundaries

1. All API calls require `X-API-Key`. All agent sockets require `X-Agent-Token` validated for that exact registered agent ID.
2. Use distinct random secrets. The hub stores SHA-256 token digests for random, high-entropy per-agent credentials. A legacy shared-token mode can be explicitly enabled for migration only. Production also needs per-tenant permission scopes, expiry, credential audit and managed onboarding.
3. The hub listens on 127.0.0.1 by default. Remote agent connections require TLS/WSS by default. Keep public ingress behind a hardened reverse proxy, preferably with network restrictions.
4. Device writes are denied unless that exact printer or serial port is listed in the local agent configuration. USB is **discovery-only**.
5. Server-side validation limits job size to 1 MiB and restricts operations and serial parameters.
6. Do not store secrets in the repository. Do not enable anonymous CORS or create arbitrary shell-execution operations.
7. Real printers and serial interfaces can move motors, actuators, or attached machinery. Only allow safe, owner-approved devices and commands.
8. Anyone with the hub API key may submit jobs to a connected agent's locally approved devices. Production needs operator roles, tenant isolation, agent pairing, audit logs and rate limiting.

## Milestones

- **Alpha 0.1:** authenticated hub, local agent, printer and serial allowlists, discovery, simulator, CI.
- **Alpha 0.2 (in progress):** web management dashboard, persistent hashed per-agent credential registry, token rotation/revocation, agent inventory refresh and test coverage; remaining: automatic OS services, scoped permissions and smoother onboarding.
- **Alpha 0.3:** secure USB-HID and USB bulk plugins, approval and permission model, safe sandboxed protocols.
- **Beta:** signed desktop installers, recovery after crashes, end-to-end acknowledgements, device protocol SDK and logging.
- **1.0:** audited multi-tenant controls, observability, upgrade strategy, long-term stable protocol.
