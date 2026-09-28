# Creation compliance record

Scope: new Octez EVM observer charm for Etherlink archive nodes. Date: 2026-09-28.
Before: empty repository. No deployed charm exists.

| Requirement | Authority / applicability | Before | Disposition | Target | Actual evidence |
| --- | --- | --- | --- | --- | --- |
| Consolidated definitions, uv, lock, ops testing | Required baseline BUILD-001 / shared | GAP | Implement | PASS | PASS: consolidated definition, locked uv build, and source inspection |
| Domain and event separation | Task-required creation standard / blockchain | GAP | Implement | PASS | PASS: charm.py, octez.py, bootstrap.py, constants.py |
| Required actions and debug handler logging | Task-required creation standard / blockchain | GAP | Implement | PASS | PASS: action declarations, first-statement debug logs; live actions pending |
| Native binary, download before stop, version from binary | Task-required creation standard / blockchain | GAP | Implement | PASS | PASS: checksum failure and download-before-stop tests; native v0.66 build tested |
| Upgrade preserves running workload | Task-required creation standard / blockchain | GAP | Implement | PASS | PASS: upgrade event does not issue mutations; live process identity check pending |
| Metadata local write and optional secret upload | Task-required creation standard / blockchain | GAP | Implement | PASS | PASS: local payload, invalid secret, granted secret upload, actual RPC identity tests |
| Accurate source topology | Required baseline OBS-001 / observability | GAP | Implement | PASS conditional on live collector | Pending live checks |
| Machine observability schema v3 | Contract-required / selected interface | GAP | Vendor reference | PASS | PASS: byte-identical reference and relation payload test |
| Recoverable snapshot bootstrap outside hooks | Task-required / archive deployment | GAP | Implement | PASS conditional on real snapshot import | Pending integration |
| 55% coverage, lint and build | Task-required creation standard / shared | GAP | Implement | PASS | PASS: 31 unit tests, coverage above 55%, Ruff, Ubuntu 24.04 charmpacker build |
| Built artifact and pytest/Jubilant integration | Required baseline DEPLOY-001 and task-required creation standard / release | UNKNOWN | Implement suite; run on explicit test model | PASS conditional on environment | Pending integration |
| Alerts | Recommended default / observability | N/A | Publish empty artifacts; no approved thresholds | N/A | Empty artifacts |

No user decisions are needed for implementation. Live archive and collector checks remain separate from local tests.

Sources: [charm standard](https://github.com/dwellir-public/agent-skills),
[op-node reference](https://github.com/dwellir-public/op-node-operator),
[common library](https://github.com/dwellir-public/dwellir-blockchain-charms-common),
[observability authority](https://github.com/dwellir-public/dwellir-observability-reference).

## Review dispositions

The initial review identified completed transient imports that remain active after exit.
The charm now checks the success marker, database, and systemd substate before retiring that unit.
A regression test covers this adoption path.

Stopping before the main service exists previously returned an error before persisting operator intent.
Stop intent now persists first. Missing units are skipped.
The main service is disabled at boot, and later configuration preserves this state.
Stop and restart commands allow 330 seconds, exceeding systemd's 300-second limit.

Metadata now prefers actual RPC chain identity and records the configured chain separately.
A mismatch test protects the distinction.
The integration suite uses pytest/Jubilant and verifies the explicit model UUID before mutations.
It permits only the localhost cloud and requires an explicit destructive opt-in.

## Recorded evidence

- Reference library SHA256: `f93196c38bbd8343b1d72173e860e1adf5ddf04ce728fae36d6e57fc3916e679`.
- Charm development skill SHA256: `cfaf6ec724be60ac9f7aaf237dfa1c3b76579351b45ee0d30a394a7cf987c607`.
- Blockchain charm skill SHA256: `2ed796a6302fd5af8a24261e7d1e32889742c55b296461fdb909af63bfea0902`.
- McCabe complexity: maximum 10, in `validate_config`. No function exceeds the configured limit.
- Live integration, production archive acceptance, and backend telemetry evidence remain pending.

The local suite does not prove a second binary-version upgrade or real S3 delivery.
Those checks require separate live evidence before claiming the full release matrix passes.

The first real integration run found Octez's eager HOME lookup during `--version`.
Juju hooks omit HOME; SSH sessions supplied it and hid the failure.
Management commands now supply the executing account's home when absent.
Both systemd units also set HOME explicitly. A real subprocess test covers this boundary.

A review found that binary replacement ignored a failed service stop.
Replacement now tolerates only a missing service during first installation.
Any real stop failure preserves the installed binary. A regression test checks both files.

GitHub Actions now use verified immutable commit references.
Release publication rejects a pre-existing tag that resolves to a different commit.

Two review requests concern the unmodified observability library's consumer and multi-unit behavior.
This charm only publishes sources, carries no artifacts, and permits one unit per application.
Those upstream contract changes are deferred to the authoritative reference repository.
Changing the vendored bytes here would break the declared provenance and consumer compatibility.

The snapshot staging request is not adopted because the native importer already stages extraction on the data filesystem.
Normal importer failure performs native temporary-directory cleanup.
A forced kill or interruption during final promotion requires operator inspection.
The charm refuses to delete ambiguous data or bypass its no-overwrite guard.

The worker detects leftover native `.octez_evm_node_import_*` staging before starting another import.
This prevents a reboot from silently starting a second multi-terabyte extraction beside interrupted data.

The independent OpenCode review at `72fd305` found no remaining actionable issues.
Later runtime integration reproduced Octez's documented clean signal exit code 127.
The observer unit now accepts that code so an intentional stop reaches `inactive`.
The bootstrap unit still treats interrupted imports as failures.
See [upstream exit codes](https://octez.tezos.com/docs/user/exits.html).
The existing lifecycle integration stop assertion owns this regression.
