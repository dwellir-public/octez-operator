# Architecture

`src/charm.py` owns Juju events, status, metadata, and relation publication.
`src/octez.py` owns bounded system commands, installation, configuration, and RPC diagnostics.
`src/bootstrap.py` runs as a standalone system Python process under systemd.
It needs no charm virtual environment or Juju agent connection.
`src/constants.py` owns the path contract.

The data path differs from Octez's default home directory to support stable machine storage.
The service and Unix account are named `octez`, matching the charm.
The binary remains named `octez-evm-node`.
The default service flags retain archive history and the fixed published RPC port.
The operator controls other flags through `service-args`.

The bootstrap success marker separates a completed snapshot from incomplete files.
Existing data without this marker requires operator inspection.
The charm never infers completeness from directory existence.
The upstream importer streams HTTP input and performs its own extraction and final rename.
Network failure requires a fresh import attempt. There is no byte-range resume.

System management commands have a 60-second timeout.
Stops and restarts allow 330 seconds, exceeding systemd's 300-second stop timeout.
An explicit stop disables the service at boot until the operator starts it again.
Snapshot import runs in a separate oneshot service with no start timeout.
An active bootstrap prevents binary installation or service-file changes.
This also supports imports started before charm deployment.

The common library supplies downloads, checksum validation, environment files, systemd installation, and metadata.
The local account setup avoids the shared helper's recursive ownership and permission walk over archive data.
Metadata prefers live chain identity and records its source alongside the configured chain.
It also records service state, binary version, and the RPC client version when available.
Secret content never enters the local payload.

## Provenance

| Reference | Commit or version |
| --- | --- |
| op-node-operator | c5c5895145d8bdf4155838adad33e7d215331796 |
| dwellir-blockchain-charms-common checkout | 788fb1d44bbdd4e08caf0201e31403ee14b69c7a |
| charms-dwellir-blockchain-common package | 0.0.2, pinned in uv.lock |
| dwellir-observability-reference | b4e0cd1c0ecc71cbbd8e5a8be195c22e01937e28 |

The observability library is copied unchanged from the authoritative reference.
Its contract uses an application databag with unit identity, so each application permits one unit.
A compatible subordinate must preserve this identity through backend metrics and logs.
