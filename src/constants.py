"""Stable workload paths and service names."""

from pathlib import Path

SERVICE = "octez"
BOOTSTRAP_SERVICE = "octez-bootstrap"
BINARY = Path("/usr/local/bin/octez-evm-node")
DATA = Path("/var/lib/octez")
MARKER = DATA / ".snapshot-imported"
METADATA = Path("/var/lib/octez-metadata")
ARGS_FILE = Path("/etc/default/octez")
BOOTSTRAP_CONFIG = Path("/etc/octez-bootstrap.json")
BOOTSTRAP_SCRIPT = Path("/usr/local/lib/octez/bootstrap.py")
RPC_URL = "http://127.0.0.1:8545"
RPC_PORT = 8545
