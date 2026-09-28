# Development

```bash
make charm-venv
make lint-test unit-test
make build-charm
```

Dependencies come from pyproject.toml. Commit uv.lock after updates.
The charm uses the uv Charmcraft plugin and one Ubuntu 24.04 amd64 platform.
`make fmt-test` applies formatting.

On a non-Ubuntu workstation, use charmpacker against a committed revision:

```bash
charmpack --repo "$PWD" --ref HEAD --ubuntu-version 24.04
```

Unit tests cover archive guards, asynchronous bootstrap, binary replacement order,
Juju lifecycle, metadata failures, and relation payloads.
The coverage gate is 55 percent. Ruff limits McCabe complexity to 10.

## Integration

Use a disposable Juju model. Never run this suite on a production archive model.
Tests stop services and change configuration.
Provide a small genuine mainnet archive snapshot compatible with Octez 0.65 and 0.66.
The suite installs 0.65, then verifies replacement with 0.66.
A full mainnet snapshot needs hours and terabytes; CI requires explicit inputs.

```bash
export OCTEZ_CHARM=/absolute/path/to/octez.charm
export OCTEZ_TEST_SNAPSHOT=https://your-test-storage.example/tiny-archive
export OCTEZ_INITIAL_BINARY_URL=https://gitlab.com/api/v4/projects/3836952/packages/generic/octez-evm-node-0.65/0.65/linux-x86_64-octez-evm-node
export OCTEZ_INITIAL_BINARY_SHA256=7cda413e627c70e6510018ce52e71fd8f90202643b3e1b5ec56c380cf260bb2d
export OCTEZ_BINARY_URL=https://gitlab.com/api/v4/projects/3836952/packages/generic/octez-evm-node-0.66/0.66/linux-x86_64-octez-evm-node
export OCTEZ_BINARY_SHA256=e36136e0bdd9f527dd17b0ab6c8b3d3951fc986c6bbf48d14f92be0a72133079
export OCTEZ_TEST_MODEL=local:admin/disposable-octez
export OCTEZ_TEST_MODEL_UUID=MODEL_UUID
export OCTEZ_ALLOW_DESTRUCTIVE=yes
make integration-test
```

For an already staged fixture, set OCTEZ_TEST_MACHINE to its machine ID.
Use `/var/lib/octez-snapshots/archive.snapshot`, readable by the `octez` account.
Keep fixtures outside `/tmp` and `/var/tmp`; the bootstrap service uses private temporary directories.
The pytest/Jubilant suite deploys the charm on that machine.
It verifies the model UUID and permits only the localhost LXD cloud.
It refuses an existing octez application.
Direct pytest runs leave the supplied model for inspection.
The integration workflow destroys its disposable controller afterward.
The manual integration workflow and release workflow run this suite.
The upgrade check compares binary checksums, process identity, the snapshot marker, and a retained block hash.
A malformed test secret verifies blocked status while RPC and local metadata remain available.
It contains only `bucket=local-test`, so credential validation fails before any upload.
The suite resets this configuration and deletes its temporary secret after the check.
Pull requests run lint and unit tests only.
Release remains blocked until integration succeeds; the release workflow publishes a GitHub artifact, not a Charmhub channel.

Live acceptance must also check actual archive history, Dune tracing, metadata upload, and Alloy backend labels.
The small fixture proves lifecycle behavior, not mainnet archive completeness.
