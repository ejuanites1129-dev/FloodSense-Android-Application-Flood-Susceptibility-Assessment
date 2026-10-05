# Selected team local setup snapshot

Snapshot: `local-team-2026-10-06`. The project owner requested sharing these
selected rows through Git on 6 October 2026. This is a small allowlisted setup
package, not a database dump, institutional approval, or official-data import.

## Included

- The existing renamed Bacoor administrative-boundary source's metadata and
  internal `APPROVED` status. Its current local reviewer/date are empty; the
  snapshot does not invent them or claim City endorsement.
- One City and 47 barangay identities, all currently `PENDING_VALIDATION` and
  enabled. The source was approved, but the individual areas were **not**.
- The existing temporary evacuation-center source and two selected test markers:
  `LOCAL TEST - Evac_Test1 (NOT A REAL FACILITY)` and
  `LOCAL TEST - evac_test2 (NOT A REAL FACILITY)`. UUIDs, coordinates, barangay
  relations, visible limitations, and non-personal display fields are retained.

Geometry is reused from the existing checked-in normalized COD-AB/PSA extracts,
not copied from a local database. SHA-256 hashes bind the snapshot to those files.
Read the [boundary dataset README](../../administrative_boundaries/README.md)
for attribution, redistribution conditions, merger derivation and limitations.
The selected local geometry must match those files; the importer refuses edits.

## Excluded

No users, account emails/passwords, original reviewer IDs, `.env`, tokens,
contact details, database backups, audit history, MGB/LiPAD deliveries,
susceptibility facts, expert rules, parameters, or guidance are exported.
Existing contact details remain local and are not erased on a repeat import.
No demo zones are recreated or deleted. This package is not a mirror of the
entire owner's database, and it does not continuously synchronize later edits.

## Import behavior and safety

Use `import_team_local_data` only with an explicitly authorized local PostGIS
database, `DJANGO_DEBUG=true` and `FLOODSENSE_LOCAL_TESTING=true`. It refuses
remote database hosts and requires an existing active local superuser supplied
as `--actor`. A local port-forward/tunnel to a shared database is **not** an
authorized local target even if its address looks like loopback.

The default run executes a transactional preview and rolls back all rows and
audit entries. `--apply` saves the changes. PostgreSQL sequences can advance
during a rolled-back preview; gaps in internal row IDs are harmless.

The command creates missing selected rows in the existing normal tables. It
matches areas by PSGC code, centers by public UUID, and the boundary source by
the City relation (with guarded legacy/current-name bootstrap). It can align an
untouched pending boundary import to this reviewed snapshot. Other source,
geometry, status or center differences are conflicts: the whole transaction
rolls back. There is no force/overwrite option. Existing withdrawn/disabled or
locally edited records are not restored silently, and revoked test approvals
are not reapplied.

Temporary source/center approvals use the existing local workflow and are
attributed to the teammate's chosen local superuser. They are not copies of the
original reviewer's account or proof of agency/facility verification. At rest,
the source and centers remain `DEMONSTRATION`, publicly unreleasable, with no
verification date or capacity. Normal operation excludes them when local testing
is disabled. Import audit entries belong to the local actor; no old audit rows
are copied.

See [teammate setup instructions](../../../docs/TEAM_LOCAL_DATA_HANDOFF.md).
Changes to this snapshot require explicit selection, privacy/source review,
updated checksums if geometry changes, and tests in the same reviewed commit.
