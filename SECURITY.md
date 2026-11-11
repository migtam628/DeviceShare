# Security policy

DeviceShare is **alpha software**; no stable release is available, and it is not security-audited.

## Reporting a vulnerability

Please do not publicly post vulnerability details while they could enable real device compromise. Contact the repository owner privately or use GitHub's private vulnerability reporting feature if enabled. Do not include API keys, tokens, private serial numbers, or print payloads in public issues.

## Deployment cautions

- Bind the hub to loopback by default. Use TLS plus network access controls for any remote access.
- Use a high-entropy administrator API key and unique station tokens; the hub stores only token hashes. Rotate or revoke from the dashboard. Do not store secrets in source control or logs.
- Never expose an agent-controlled arbitrary shell or unrestricted USB command endpoint.
- Explicitly authorize each physical printer or serial device on the local agent.
- Treat physical devices as potentially hazardous. Never assume they understand a byte sequence safely.
- Protect printer content and transmitted serial data as potentially confidential.
- Validate jobs before executing and audit each job by ID and submitting system.
- Avoid blind retries after delivery uncertainty.
- Per-agent tokens are available, but a single administrator API key still controls provisioning and all jobs. Roles, token expiry, quotas, tenant isolation, rate limiting, pairing approval and signed updates are required before a public multi-tenant deployment.
