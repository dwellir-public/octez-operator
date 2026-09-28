"""Destructive lifecycle checks using a genuine, small archive snapshot."""

import json
import os

import pytest


async def action(unit, name):
    result = await unit.run_action(name)
    await result.wait()
    assert result.status == "completed", result.results
    return result.results


async def process_identity(ops_test):
    code, output, error = await ops_test.juju(
        "ssh", "octez/0", "systemctl show octez -p MainPID -p ExecMainStartTimestampMonotonic"
    )
    assert code == 0, error
    return output


@pytest.mark.abort_on_fail
async def test_archive_lifecycle(ops_test):
    """Verify import, lifecycle actions, configuration, metadata, and safe charm refresh."""
    required = ("OCTEZ_CHARM", "OCTEZ_TEST_SNAPSHOT", "OCTEZ_BINARY_URL", "OCTEZ_BINARY_SHA256")
    missing = [name for name in required if not os.environ.get(name)]
    assert not missing, f"Required integration inputs: {', '.join(missing)}"
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
    deployment = {"application_name": "octez", "config": config, "base": "ubuntu@24.04"}
    if os.environ.get("OCTEZ_TEST_MACHINE"):
        deployment["to"] = os.environ["OCTEZ_TEST_MACHINE"]
    await ops_test.model.deploy(os.environ["OCTEZ_CHARM"], **deployment)
    await ops_test.model.wait_for_idle(apps=["octez"], status="active", timeout=3600)
    app = ops_test.model.applications["octez"]
    unit = app.units[0]
    info = await action(unit, "get-node-info")
    assert info["snapshot-imported"] is True
    assert info["service-state"] == "active"
    assert "0.66" in info["version"]
    assert "Octez EVM operator" in (await action(unit, "print-readme"))["readme"]

    await action(unit, "stop-node")
    assert (await action(unit, "get-node-info"))["service-state"] == "inactive"
    await action(unit, "start-node")
    await ops_test.model.wait_for_idle(apps=["octez"], status="active", timeout=300)
    identity = await process_identity(ops_test)
    await action(unit, "restart-node")
    await ops_test.model.wait_for_idle(apps=["octez"], status="active", timeout=300)
    assert await process_identity(ops_test) != identity

    identity = await process_identity(ops_test)
    await app.set_config({"service-args": args + " --rpc-batch-limit 50"})
    await ops_test.model.wait_for_idle(apps=["octez"], status="active", timeout=300)
    assert "--rpc-batch-limit 50" in (await action(unit, "get-node-info"))["service-args"]
    assert await process_identity(ops_test) != identity

    code, metadata, error = await ops_test.juju(
        "ssh", "octez/0", "sudo cat /var/lib/octez-metadata/octez-0.json"
    )
    assert code == 0, error
    payload = json.loads(metadata)
    assert payload["blockchain"]["chain_id"] == 42793
    assert payload["juju_topology"]["application"] == "octez"

    identity = await process_identity(ops_test)
    await app.refresh(path=os.environ["OCTEZ_CHARM"])
    await ops_test.model.wait_for_idle(apps=["octez"], status="active", timeout=600)
    assert await process_identity(ops_test) == identity
