# Security and Threat Model — Phase 1

## Assets and boundaries

Assets are synthetic scenario data, decision traces, provider credentials, development role tokens,
local knowledge documents, operator identities, and eventual dispatch integrations. HTTP clients
are untrusted. API-to-engine is a typed boundary; retrieval, NVIDIA NIM, identity, persistence,
and dispatch adapters are separate trust boundaries.

| Threat | Phase 1 control | Required next control |
| --- | --- | --- |
| Malformed input | Validation, bounds, unknown-field rejection | Gateway body-size/rate limits |
| Unsafe allocation | Capability checks, safety gate, human approval | Independent policy service |
| Prompt injection | NIM system instruction, JSON/Pydantic validation, no tools, blocked fallback | Content isolation, provenance, red-team tests |
| Sensitive leakage | Synthetic data, no payload logging, generic errors | Classification, encryption, retention policy |
| Credential exposure | `NVIDIA_API_KEY` read from environment, no committed secret | Secret manager, rotation, workload identity |
| Browser abuse | Explicit CORS, no credentials, headers, development role dependency | OAuth2/OIDC, production RBAC, CSRF assessment |
| Availability abuse | Bounded data model | WAF, quotas, load testing |
| Audit tampering | Response trace | Signed append-only audit store/outbox |

Phase 1 is not authorised for real emergency operations. Production requires a formal safety case,
jurisdictional review, DPIA, incident response plan, penetration test, and accountable authority.
