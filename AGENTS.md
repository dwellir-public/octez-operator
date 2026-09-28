# Octez operator

Use the Dwellir charm development skill before editing lifecycle behavior.
Keep definitions in charmcraft.yaml and dependencies in pyproject.toml plus uv.lock.
Run `make lint-test unit-test` before sharing changes.
Run integration tests on an explicitly selected disposable model before release.
Never run destructive integration tests against archive production models.
Keep snapshot import outside Juju hooks. Preserve data on charm refresh.
The upgrade-charm hook must not restart either systemd service.
Update README.md, ARCHITECTURE.md, and DEVELOPING.md when behavior changes.
