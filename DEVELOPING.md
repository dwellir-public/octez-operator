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
Provide a small genuine archive snapshot and a native binary checksum.
A full mainnet snapshot needs hours and terabytes; CI requires explicit inputs.

```bash
export OCTEZ_CHARM=/absolute/path/to/octez.charm
export OCTEZ_TEST_SNAPSHOT=https://your-test-storage.example/tiny-archive
export OCTEZ_BINARY_URL=https://gitlab.com/api/v4/projects/3836952/packages/generic/octez-evm-node-0.66/0.66/linux-x86_64-octez-evm-node
export OCTEZ_BINARY_SHA256=e36136e0bdd9f527dd17b0ab6c8b3d3951fc986c6bbf48d14f92be0a72133079
make integration-test ARGS='--controller local --model disposable-octez'
```

For an already staged fixture, set OCTEZ_TEST_MACHINE to its machine ID and use an absolute snapshot path.
The suite deploys the charm on that machine.
The manual integration workflow and release workflow run this suite.
Pull requests run lint and unit tests only.
Release remains blocked until integration succeeds; the release workflow publishes a GitHub artifact, not a Charmhub channel.

Live acceptance must also check actual archive history, Dune tracing, metadata upload, and Alloy backend labels.
The small fixture proves lifecycle behavior, not mainnet archive completeness.
