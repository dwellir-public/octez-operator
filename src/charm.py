#!/usr/bin/env python3
"""Juju event orchestration for native Octez EVM archive nodes."""

import hashlib
import logging
import subprocess
from pathlib import Path

import ops
import requests
from charms.dwellir.blockchain_common.v1 import (
    EvmBlockchainMetadata,
    MetadataUploadError,
    MetadataValidationError,
    collect_and_upload,
    parse_credentials_secret_id,
)
from charms.dwellir.blockchain_common.v1.evm_chains.registry import chain_name
from charms.dwellir_observability.v0.machine_observability import (
    MachineObservabilityPayload,
    MachineObservabilityProvider,
    MetricsEndpoint,
    SourceTopology,
)

import constants as c
import octez

logger = logging.getLogger(__name__)
ERRORS = (OSError, ValueError, subprocess.SubprocessError, requests.RequestException)


class OctezCharm(ops.CharmBase):
    """Manage one archive node per application and its snapshot worker."""

    _stored = ops.StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self._stored.set_default(binary_digest="", service_args="", configured=False, stopped=False)
        for event in (self.on.install, self.on.start, self.on.config_changed):
            self.framework.observe(event, self._on_reconcile)
        self.framework.observe(self.on.update_status, self._on_update_status)
        self.framework.observe(self.on.upgrade_charm, self._on_upgrade_charm)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.secret_changed, self._on_secret_changed)
        self.framework.observe(self.on.start_node_action, self._on_start_node)
        self.framework.observe(self.on.stop_node_action, self._on_stop_node)
        self.framework.observe(self.on.restart_node_action, self._on_restart_node)
        self.framework.observe(self.on.get_node_info_action, self._on_get_node_info)
        self.framework.observe(self.on.print_readme_action, self._on_print_readme)
        self.observability = MachineObservabilityProvider(self, payload_factory=self._observability_payload)

    def _on_reconcile(self, _event):
        logger.debug("Reconcile workload configuration")
        self._reconcile()

    def _reconcile(self, *, retry=False):
        """Apply configuration without interrupting an active snapshot import."""
        try:
            args = octez.validate_config(self.config)
            if self.app.planned_units() > 1:
                raise ValueError("Deploy one unit per application to preserve observability source identity")
            if octez.bootstrap_running():
                self._status_metadata()
                return
            octez.prepare()
            self._install_binary()
            changed = self._stored.configured and args != self._stored.service_args
            octez.configure(args, self.config["snapshot-source"])
            self._stored.configured = True
            self._stored.service_args = args
            self.unit.set_workload_version(octez.version())
            self.unit.open_port("tcp", c.RPC_PORT)
            if not self._stored.stopped:
                self._start_or_restart(changed, retry=retry)
            self._status_metadata()
        except ERRORS as exc:
            logger.exception("Workload reconciliation failed")
            self.unit.status = ops.BlockedStatus(f"Node {octez.service_state(c.SERVICE)}; {exc}")

    def _install_binary(self):
        """Adopt a verified prestaged binary or install its replacement."""
        digest = self.config["binary-sha256"].lower()
        if self._stored.binary_digest == digest and c.BINARY.exists():
            return
        actual = ""
        if c.BINARY.exists():
            with c.BINARY.open("rb") as binary:
                actual = hashlib.file_digest(binary, "sha256").hexdigest()
        if actual != digest:
            octez.install_binary(self.config["binary-url"], digest)
        self._stored.binary_digest = digest

    def _start_or_restart(self, changed, *, retry=False):
        """Restart only for changed arguments after the snapshot is ready."""
        if changed and octez.snapshot_ready():
            octez.command("systemctl", "restart", c.SERVICE)
        else:
            octez.start(self.config["snapshot-source"], retry=retry)

    def _on_update_status(self, _event):
        logger.debug("Refresh workload and bootstrap status")
        if not self._stored.configured or (octez.snapshot_ready() and not self._stored.stopped):
            self._reconcile()
        else:
            self._status_metadata()

    def _on_upgrade_charm(self, _event):
        logger.debug("Refresh charm without restarting workload or bootstrap")
        self._status_metadata()

    def _on_secret_changed(self, event):
        logger.debug("Refresh metadata after secret rotation")
        event.secret.get_content(refresh=True)
        self._status_metadata()

    def _on_stop(self, _event):
        logger.debug("Stop workload before unit shutdown")
        self._stop()

    def _stop(self):
        """Stop both services and persist the operator stop across config events."""
        self._stored.stopped = True
        octez.stop_services()
        self.unit.status = ops.BlockedStatus("Node stopped by operator")

    def _status_metadata(self):
        """Report workload readiness and keep metadata failures visible."""
        try:
            self._set_status()
            if c.BINARY.exists():
                self._metadata()
        except (MetadataValidationError, MetadataUploadError, *ERRORS) as exc:
            logger.exception("Status or metadata collection failed")
            self.unit.status = ops.BlockedStatus(
                f"Node {octez.service_state(c.SERVICE)}; metadata/status: {exc}"
            )

    def _set_status(self):
        """Distinguish import, explicit stop, RPC readiness and archive service health."""
        if octez.bootstrap_running():
            self.unit.status = ops.MaintenanceStatus("Node stopped; snapshot import running")
            return
        if self._stored.stopped:
            self.unit.status = ops.BlockedStatus("Node stopped by operator")
            return
        if octez.service_state(c.SERVICE) != "active":
            self.unit.status = ops.BlockedStatus("Node stopped; inspect get-node-info and systemd journal")
            return
        try:
            chain = int(str(octez.rpc("eth_chainId")), 16)
            if chain != self.config["chain-id"]:
                self.unit.status = ops.BlockedStatus(f"Node running; unexpected chain ID {chain}")
                return
            head = int(str(octez.rpc("eth_blockNumber")), 16)
            self.unit.status = ops.ActiveStatus(f"Node running; RPC ready at block {head}")
        except (requests.RequestException, ValueError, KeyError):
            self.unit.status = ops.WaitingStatus("Node running; RPC not ready")

    def _metadata(self):
        """Write topology and chain metadata locally, then upload with Juju credentials."""
        identity = octez.runtime_identity(self.config["chain-id"])
        actual_chain = identity["chain_id"]
        network = self.config["network-name"]
        if actual_chain != self.config["chain-id"]:
            network = chain_name(actual_chain, f"chain-{actual_chain}")
        blockchain = EvmBlockchainMetadata(
            blockchain_ecosystem="ethereum",
            blockchain_network_name=network,
            chain_id=actual_chain,
            l2_chain_id=actual_chain,
            client_name="octez-evm-node",
            client_version=octez.version(),
            cmdline=f"run observer --data-dir {c.DATA} {self.config['service-args']}",
            binary_path=str(c.BINARY),
        )
        # Write before resolving credentials, so a broken upload never removes local evidence.
        payload_args = dict(
            model=self.model,
            app=self.app,
            unit=self.unit,
            meta=self.meta,
            base_dir=c.METADATA,
            blockchain=blockchain,
            sections={
                "runtime": octez.node_info(),
                "chain_identity": {**identity, "configured_chain_id": self.config["chain-id"]},
            },
        )
        collect_and_upload(**payload_args, no_upload=True)
        secret = self.config["collector-s3-credentials"]
        if secret:
            credentials = parse_credentials_secret_id(self.model, secret)
            collect_and_upload(**payload_args, credentials=credentials)

    def _observability_payload(self):
        """Publish local sources using the workload's Juju identity."""
        return MachineObservabilityPayload(
            schema_version=3,
            charm_name=self.meta.name,
            source_topology=SourceTopology(
                model=self.model.name,
                model_uuid=self.model.uuid,
                application=self.app.name,
                unit=self.unit.name,
                charm_name=self.meta.name,
            ),
            metrics_endpoints=[MetricsEndpoint(targets=["127.0.0.1:8545"])],
            systemd_units=["octez.service", "octez-bootstrap.service"],
            artifacts=[],
        )

    def _on_start_node(self, event):
        logger.debug("Start node action")
        try:
            self._stored.stopped = False
            self._reconcile(retry=True)
            if isinstance(self.unit.status, ops.BlockedStatus):
                event.fail(self.unit.status.message)
                return
            event.set_results({"result": self.unit.status.message})
        except ERRORS as exc:
            event.fail(str(exc))

    def _on_stop_node(self, event):
        logger.debug("Stop node action")
        try:
            self._stop()
            event.set_results({"result": "Node and snapshot worker stopped"})
        except ERRORS as exc:
            event.fail(str(exc))

    def _on_restart_node(self, event):
        logger.debug("Restart node action")
        try:
            if octez.bootstrap_running() or not octez.snapshot_ready():
                raise ValueError("Cannot restart before snapshot import completes")
            self._stored.stopped = False
            octez.command("systemctl", "restart", c.SERVICE)
            self._status_metadata()
            event.set_results({"result": self.unit.status.message})
        except ERRORS as exc:
            event.fail(str(exc))

    def _on_get_node_info(self, event):
        logger.debug("Get node diagnostics action")
        try:
            event.set_results(octez.node_info())
        except ERRORS as exc:
            event.fail(str(exc))

    def _on_print_readme(self, event):
        logger.debug("Print readme action")
        event.set_results({"readme": Path("README.md").read_text()})


if __name__ == "__main__":
    ops.main(OctezCharm)
