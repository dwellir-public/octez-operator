# Creation compliance record

Scope: new Octez EVM observer charm for Etherlink archive nodes. Date: 2026-09-28.
Before: empty repository. No deployed charm exists.

| Requirement | Authority / applicability | Before | Disposition | Target | Actual evidence |
| --- | --- | --- | --- | --- | --- |
| Consolidated definitions, uv, lock, ops testing | Required baseline BUILD-001 / shared | GAP | Implement | PASS | Pending checks |
| Domain and event separation | Task-required creation standard / blockchain | GAP | Implement | PASS | Pending checks |
| Required actions and debug handler logging | Task-required creation standard / blockchain | GAP | Implement | PASS | Pending tests |
| Native binary, download before stop, version from binary | Task-required creation standard / blockchain | GAP | Implement | PASS | Pending tests |
| Upgrade preserves running workload | Task-required creation standard / blockchain | GAP | Implement | PASS | Pending tests |
| Metadata local write and optional secret upload | Task-required creation standard / blockchain | GAP | Implement | PASS | Pending tests |
| Accurate source topology | Required baseline OBS-001 / observability | GAP | Implement | PASS conditional on live collector | Pending live checks |
| Machine observability schema v3 | Contract-required / selected interface | GAP | Vendor reference | PASS | Pending tests |
| Recoverable snapshot bootstrap outside hooks | Task-required / archive deployment | GAP | Implement | PASS conditional on real snapshot import | Pending integration |
| 55% coverage, lint and build | Task-required creation standard / shared | GAP | Implement | PASS | Pending checks |
| Destructive integration before release | Task-required creation standard / release | UNKNOWN | Implement suite; run on explicit test model | PASS conditional on environment | Pending integration |
| Alerts | Recommended default / observability | N/A | Publish empty artifacts; no approved thresholds | N/A | Empty artifacts |

No user decisions are needed for implementation. Live archive and collector checks remain separate from local tests.

Sources: [charm standard](https://github.com/dwellir-public/agent-skills),
[op-node reference](https://github.com/dwellir-public/op-node-operator),
[common library](https://github.com/dwellir-public/dwellir-blockchain-charms-common),
[observability authority](https://github.com/dwellir-public/dwellir-observability-reference).
