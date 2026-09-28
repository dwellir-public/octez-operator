"""Exercise Juju lifecycle behavior and metadata against real local files."""

import json
from unittest.mock import patch

import ops
import pytest
from ops.testing import Harness
from test_octez import CONFIG

import constants as c
from charm import OctezCharm


@pytest.fixture
def harness(tmp_path, monkeypatch):
    for name, path in {
        "DATA": tmp_path,
        "BINARY": tmp_path / "binary",
        "MARKER": tmp_path / ".snapshot-imported",
        "METADATA": tmp_path / "metadata",
        "ARGS_FILE": tmp_path / "args",
    }.items():
        monkeypatch.setattr(c, name, path)
    h = Harness(OctezCharm)
    h.set_model_name("etherlink-test")
    h.set_model_uuid("11111111-1111-4111-8111-111111111111")
    h.set_leader(True)
    h.update_config(CONFIG)
    h.begin()
    yield h
    h.cleanup()


def test_upgrade_never_mutates_workload(harness):
    with patch("octez.service_state", return_value="inactive"), patch("octez.command") as command:
        harness.charm.on.upgrade_charm.emit()
    command.assert_not_called()
    assert "stopped" in harness.model.unit.status.message


def test_in_progress_external_import_is_adopted_without_install_or_restart(harness):
    with patch("octez.bootstrap_running", return_value=True):
        with patch("octez.prepare") as prepare, patch("octez.install_binary") as install:
            harness.charm.on.install.emit()
    prepare.assert_not_called()
    install.assert_not_called()
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "import running" in harness.model.unit.status.message


def test_finished_import_starts_node_on_next_status_event(harness):
    c.MARKER.touch()
    (c.DATA / "store.sqlite").touch()
    with patch("octez.bootstrap_running", return_value=False), patch("octez.prepare"):
        with patch.object(harness.charm, "_install_binary"), patch("octez.configure"):
            with patch("octez.start") as start, patch("octez.version", return_value="0.66"):
                with patch.object(harness.charm, "_status_metadata"):
                    harness.charm.on.update_status.emit()
    start.assert_called_once_with(CONFIG["snapshot-source"], retry=False)
    assert harness.get_workload_version() == "0.66"


def test_explicit_stop_survives_later_config_reconcile(harness):
    with patch("octez.command"):
        harness.run_action("stop-node")
    with patch("octez.bootstrap_running", return_value=False), patch("octez.prepare"):
        with patch.object(harness.charm, "_install_binary"), patch("octez.configure"):
            with patch("octez.start") as start, patch("octez.version", return_value="0.66"):
                with patch.object(harness.charm, "_metadata"):
                    harness.charm.on.config_changed.emit()
    start.assert_not_called()
    assert harness.model.unit.status.message == "Node stopped by operator"


def test_metadata_written_before_invalid_secret_blocks_unit(harness):
    c.BINARY.touch()
    harness.charm._stored.configured = True
    harness.disable_hooks()
    harness.update_config({"collector-s3-credentials": "secret:missing"})
    harness.enable_hooks()
    with patch("octez.service_state", return_value="inactive"), patch("octez.version", return_value="0.66"):
        harness.charm.on.update_status.emit()
    payload = json.loads((c.METADATA / "octez-0.json").read_text())
    assert payload["blockchain"]["chain_id"] == 42793
    assert payload["juju_topology"]["model"] == "etherlink-test"
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "secret" in harness.model.unit.status.message


def test_metadata_upload_uses_granted_secret(harness):
    c.BINARY.touch()
    secret_id = harness.add_user_secret(
        {
            "bucket": "metadata",
            "region": "eu-north-1",
            "access-key-id": "access",
            "secret-access-key": "secret",
        }
    )
    harness.grant_secret(secret_id, "octez")
    harness.disable_hooks()
    harness.update_config({"collector-s3-credentials": secret_id})
    harness.enable_hooks()
    with patch("octez.service_state", return_value="inactive"), patch("octez.version", return_value="0.66"):
        with patch(
            "charms.dwellir.blockchain_common.v1.metadata.storage.S3PayloadUploader.upload_json"
        ) as upload:
            harness.charm._metadata()
    upload.assert_called_once()
    assert upload.call_args.kwargs["payload_path"].exists()


def test_observability_relation_contains_source_topology_and_local_targets(harness):
    relation = harness.add_relation("machine-observability", "alloy")
    harness.add_relation_unit(relation, "alloy/0")
    data = harness.get_relation_data(relation, "octez")
    payload = json.loads(data["payload"])
    assert payload["schema_version"] == 3
    assert payload["source_topology"] == {
        "model": "etherlink-test",
        "model_uuid": "11111111-1111-4111-8111-111111111111",
        "application": "octez",
        "unit": "octez/0",
        "charm_name": "octez",
    }
    assert payload["metrics_endpoints"][0]["targets"] == ["127.0.0.1:8545"]
    assert payload["systemd_units"] == ["octez.service", "octez-bootstrap.service"]
    assert payload["artifacts"] == []


def test_health_uses_supported_rpc_and_detects_wrong_chain(harness):
    with (
        patch("octez.service_state", return_value="active"),
        patch("octez.bootstrap_running", return_value=False),
    ):
        with patch("octez.rpc", side_effect=["0xa729", "0x20"]) as rpc:
            harness.charm._set_status()
        assert harness.model.unit.status == ops.ActiveStatus("Node running; RPC ready at block 32")
        assert [call.args[0] for call in rpc.call_args_list] == ["eth_chainId", "eth_blockNumber"]
        with patch("octez.rpc", return_value="0x1"):
            harness.charm._set_status()
        assert "unexpected chain ID 1" in harness.model.unit.status.message


def test_failed_stop_retains_operator_intent(harness):
    import subprocess

    from ops.testing import ActionFailed

    with patch("octez.stop_services", side_effect=subprocess.CalledProcessError(1, "systemctl")):
        with pytest.raises(ActionFailed):
            harness.run_action("stop-node")
    assert harness.charm._stored.stopped
