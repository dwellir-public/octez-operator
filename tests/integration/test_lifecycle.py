"""Destructive lifecycle checks using a genuine, small archive snapshot."""

import json
import os
from pathlib import Path

import jubilant
import pytest


@pytest.fixture
def juju():
    """Require an explicit, identity-checked local disposable model before mutation."""
    required = (
        "OCTEZ_CHARM",
        "OCTEZ_TEST_SNAPSHOT",
        "OCTEZ_BINARY_URL",
        "OCTEZ_BINARY_SHA256",
        "OCTEZ_TEST_MODEL",
        "OCTEZ_TEST_MODEL_UUID",
    )
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, f"Required integration inputs: {', '.join(missing)}"
    assert os.environ.get("OCTEZ_ALLOW_DESTRUCTIVE") == "yes", "Set OCTEZ_ALLOW_DESTRUCTIVE=yes"
    target = os.environ["OCTEZ_TEST_MODEL"]
    assert ":" in target and "/" in target, "Use controller:owner/model"
    artifact = Path(os.environ["OCTEZ_CHARM"])
    assert artifact.is_file() and artifact.suffix == ".charm", "Use a built local charm artifact"
    client = jubilant.Juju(model=target, wait_timeout=600)
    details = json.loads(client.cli("show-model", target, "--format=json", include_model=False))
    model = next(iter(details.values()))
    assert model["model-uuid"] == os.environ["OCTEZ_TEST_MODEL_UUID"], "Model identity mismatch"
    status = client.status()
    assert status.model.cloud == "localhost", "This destructive suite only permits local LXD models"
    assert "octez" not in status.apps, "Refusing to overwrite an existing application"
    return client


def action(juju, unit, name):
    task = juju.run(unit, name, wait=360)
    task.raise_on_failure()
    return task.results


def process_identity(juju, unit):
    return juju.ssh(unit, "systemctl show octez -p MainPID -p ExecMainStartTimestampMonotonic")


def ready(juju, timeout=600):
    juju.wait(lambda status: jubilant.all_active(status, "octez"), error=jubilant.any_error, timeout=timeout)


def test_archive_lifecycle(juju):
    """Verify import, lifecycle actions, configuration, metadata, and safe charm refresh."""
    args = (
        "--network mainnet --history archive --rpc-addr 0.0.0.0 --rpc-port 8545 "
        "--dont-track-rollup-node --no-sync"
    )
    config = {
        "binary-url": os.environ["OCTEZ_BINARY_URL"],
        "binary-sha256": os.environ["OCTEZ_BINARY_SHA256"],
        "snapshot-source": os.environ["OCTEZ_TEST_SNAPSHOT"],
        "service-args": args,
    }
    juju.deploy(
        os.environ["OCTEZ_CHARM"],
        "octez",
        config=config,
        base="ubuntu@24.04",
        to=os.environ.get("OCTEZ_TEST_MACHINE"),
    )
    ready(juju, timeout=3600)
    unit = next(iter(juju.status().apps["octez"].units))
    info = action(juju, unit, "get-node-info")
    assert info["snapshot-imported"] is True
    assert info["service-state"] == "active"
    assert "0.66" in info["version"]
    assert "Octez EVM operator" in action(juju, unit, "print-readme")["readme"]

    action(juju, unit, "stop-node")
    assert action(juju, unit, "get-node-info")["service-state"] == "inactive"
    action(juju, unit, "start-node")
    ready(juju)
    identity = process_identity(juju, unit)
    action(juju, unit, "restart-node")
    ready(juju)
    assert process_identity(juju, unit) != identity

    identity = process_identity(juju, unit)
    juju.config("octez", {"service-args": args + " --rpc-batch-limit 50"})
    ready(juju)
    assert "--rpc-batch-limit 50" in action(juju, unit, "get-node-info")["service-args"]
    assert process_identity(juju, unit) != identity

    metadata_file = unit.replace("/", "-") + ".json"
    payload = json.loads(juju.ssh(unit, f"sudo cat /var/lib/octez-metadata/{metadata_file}"))
    assert payload["blockchain"]["chain_id"] == 42793
    assert payload["juju_topology"]["application"] == "octez"

    identity = process_identity(juju, unit)
    juju.refresh("octez", path=os.environ["OCTEZ_CHARM"])
    ready(juju)
    assert process_identity(juju, unit) == identity
