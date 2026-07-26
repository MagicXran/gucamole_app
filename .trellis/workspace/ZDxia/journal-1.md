# Journal - ZDxia (Part 1)

> AI development session journal
> Started: 2026-07-25

---

## 2026-07-26 - GuacDrive general restriction implementation

- Started `.trellis/tasks/07-25-guacdrive-access-isolation` after explicit user approval.
- Implemented security modes, VSCode control profiles, fail-closed launch policy, admin APIs, Vue policy management, schema migration, docs, and regression tests.
- Migrated the local Docker/MySQL instance after saving a database dump; migration idempotency and live API/schema smoke passed.
- `default-controlled` intentionally remains inactive/invalid until real Windows shell, toolchain, debugger, extension, and network allowlists are inventoried.
- Remaining: Windows GPO, NTFS, AppLocker, Firewall, VSCode enterprise policy, and real two-user RemoteApp verification.
