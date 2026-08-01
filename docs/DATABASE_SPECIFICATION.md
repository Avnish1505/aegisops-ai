# Database Specification

## Status and scope

`backend/db/models.py` and Alembic revision `124aba1dcba2` define the initial relational schema. The runtime API currently has no database session, repository, or CRUD route, so these tables are not populated by scenario generation, recommendations, UI approval clicks, or the in-memory `AuditLog` helper.

The configured default connection string is SQLite (`sqlite:///./aegisops.db`); `asyncpg` is available for future PostgreSQL work. Migrations are managed through `backend/alembic.ini`.

## Tables

| Table | Primary key | Purpose |
| --- | --- | --- |
| `users` | `id` integer | User identity record: unique username/email, password hash, active flag, timestamps. |
| `roles` | `id` integer | Unique role enum: `ADMIN`, `OPERATOR`, or `VIEWER`. |
| `user_role` | `(user_id, role_id)` | Many-to-many user-to-role association. |
| `incidents` | `id` string(64) | Persistable incident attributes and synthetic coordinate components. |
| `evidence` | `id` string(64) | Evidence text, source, 0–1 confidence, optional incident reference and timestamp. |
| `decisions` | `id` integer | Scenario ID, engine, status, human-gate flag, confidence, JSON trace, timestamp. |
| `approvals` | `id` integer | Decision/user references, approval boolean, comment timestamp. |
| `audit_log` | `id` integer | Optional user reference plus action, table, record, JSON change data, timestamp. |

## Relationships and indexes

`evidence.incident_id` references `incidents.id`. `approvals.decision_id` and `approvals.user_id` reference decisions and users. `audit_log.user_id` is nullable and references users. User-role links are many-to-many.

Indexes support common lookups: user username/email; incident type, severity, and `(location_x, location_y)`; evidence incident/confidence; decision scenario/status; approval decision/user; and audit user/timestamp/`(table_name, record_id)`. The initial migration also creates identifier indexes for several integer primary keys.

## Data handling constraints

The schema has no retention, encryption, row-level authorization, signed audit trail, approval reason, or route-level persistence implementation. Do not treat it as an operational system of record. Before handling non-synthetic data, define data classification, retention/deletion, encryption, access enforcement, audit integrity, backups, and migration/rollback procedures.
