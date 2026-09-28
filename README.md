# Octez EVM operator

This Juju machine charm runs a native Octez EVM observer with archive history.
It targets Ubuntu 24.04 on amd64 and uses systemd.
Deploy one unit per application. Use separate applications or models for replicas.

## Deploy

Create the machine with sufficient storage before deploying the charm.
For Etherlink mainnet, allocate a 4 TiB container on XFS.
The September 2026 snapshot contains a 3.014 TB store member before other files.
Snapshot imports stream directly from HTTPS to avoid retaining a compressed copy.

```bash
juju deploy ./octez_ubuntu@24.04-amd64.charm octez --to 0 \
  --config binary-url=https://gitlab.com/api/v4/projects/3836952/packages/generic/octez-evm-node-0.66/0.66/linux-x86_64-octez-evm-node \
  --config binary-sha256=e36136e0bdd9f527dd17b0ab6c8b3d3951fc986c6bbf48d14f92be0a72133079 \
  --config snapshot-source=https://snapshots.tzinit.org/etherlink-mainnet/evm-snapshot-archive
```

Verify the current archive URL and capacity before deployment.
An absolute `snapshot-source` path also supports a previously downloaded snapshot.
The charm does not copy or delete that file.

The default command includes mainnet, archive history, HTTP port 8545, and `--dont-track-rollup-node`.
It follows the mainnet relay without a local Tezos rollup node.
Additional flags belong in `service-args`.
The charm rejects duplicate archive, RPC, and data-directory settings.
Port 8545 serves JSON-RPC and `/metrics`.
WebSocket support requires `--ws` and separate end-to-end validation.

## Snapshot lifecycle

`octez-bootstrap.service` imports the snapshot outside Juju hooks.
Hooks report maintenance while the import runs.
After successful import, the worker writes `/var/lib/octez/.snapshot-imported`.
The next update-status event starts `octez.service`.

An existing `octez-bootstrap` systemd process is adopted without interruption.
Use `/usr/local/bin/octez-evm-node`, the `octez` account, and `/var/lib/octez` for early imports.
Write the completion marker only after a successful native import.
The charm verifies a prestaged binary against `binary-sha256` before using it.

The importer does not resume partial downloads.
After failure, inspect `journalctl -u octez-bootstrap` before running `start-node`.
The worker refuses to overwrite `store` or `store.sqlite` without a completion marker.
It never passes `--force`.
Inspect incomplete data before recovery; the charm never deletes node data.
Changing `snapshot-source` does not replace an imported database.

## Operations

```bash
juju run octez/0 get-node-info
juju run octez/0 stop-node
juju run octez/0 start-node
juju run octez/0 restart-node
juju run octez/0 print-readme
```

Stopping also stops an active import and preserves that stop across configuration events.
Restart refuses while importing. A charm refresh does not restart either service.
Binary updates download and verify the replacement before stopping the node.
Status checks use `eth_chainId` and `eth_blockNumber`; Octez does not support `eth_syncing`.
RPC readiness alone does not prove archive completeness or tracing support.

## Metadata and observability

The charm writes `/var/lib/octez-metadata/<unit>.json` with runtime and Juju topology data.
Chain identity uses explicit `chain-id` and `network-name` configuration.
A live RPC chain mismatch blocks the unit.
Optional uploads use a model-local Juju secret:

```bash
juju add-secret collector-s3 bucket=BUCKET region=REGION \
  access-key-id=KEY secret-access-key=SECRET
juju grant-secret collector-s3 octez
juju config octez collector-s3-credentials=secret:ID
```

Optional keys are `endpoint-url`, `key-prefix`, and `session-token`.
Credentials never belong in JSON configuration strings.
Invalid credentials or failed uploads block the unit while retaining local metadata.

Relate a compatible Alloy subordinate through `machine-observability`.
The v3 payload advertises local metrics and both service journals with source topology.
No alert rules ship because workload thresholds have not been approved.
Backend telemetry and source labels require live collector validation.

## Archive acceptance

Before publishing an endpoint, verify old block reads, transaction receipts, historical state, and both trace methods.
Test `debug_traceBlockByNumber` and `debug_traceTransaction` with `callTracer` and `withLog`.
Compare trace transaction hashes with the requested block.
Match the Dune issue's timeout and request-body limits in routing configuration.
Neither a completed snapshot import nor an active Juju status replaces these checks.

References:

- [Etherlink node setup](https://docs.etherlink.com/network/evm-nodes)
- [Octez source](https://gitlab.com/tezos/tezos)
- [Development workflow](DEVELOPING.md)
- [Architecture and dependency provenance](ARCHITECTURE.md)
- [Creation compliance](docs/compliance.md)
