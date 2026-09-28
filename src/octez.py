"""Native Octez installation, bootstrap and diagnostics."""

import json
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests
from charms.dwellir.blockchain_common.v1.downloads import download_file, perform_sha256_checksum_from_string
from charms.dwellir.blockchain_common.v1.systemd import install_systemd_unit, write_service_args

import constants as c


def command(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a bounded management command; never use this for snapshot import."""
    return subprocess.run(args, check=check, text=True, capture_output=True, timeout=60)


def service_state(service: str) -> str:
    """Return systemd state including activating for a long snapshot import."""
    return command("systemctl", "is-active", service, check=False).stdout.strip() or "inactive"


def bootstrap_running() -> bool:
    """Detect managed and operator-started snapshot workers."""
    return service_state(c.BOOTSTRAP_SERVICE) in {"active", "activating", "deactivating"}


def validate_config(config) -> str:
    """Validate install inputs and prevent conflicting managed runtime flags."""
    url = str(config["binary-url"])
    if urlparse(url).scheme != "https":
        raise ValueError("binary-url must be an HTTPS URL")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", str(config["binary-sha256"])):
        raise ValueError("binary-sha256 must contain 64 hexadecimal characters")
    source = str(config["snapshot-source"])
    if source and not (urlparse(source).scheme == "https" or Path(source).is_absolute()):
        raise ValueError("snapshot-source must be HTTPS or an absolute file path")
    args = str(config["service-args"])
    tokens = shlex.split(args)
    flags = {token.split("=", 1)[0] for token in tokens}
    reserved = {"--data-dir", "--config-file", "--init-from-snapshot"}
    if flags & reserved:
        raise ValueError(f"service-args contains charm-owned flags: {', '.join(sorted(flags & reserved))}")
    require_flag(tokens, "--history", "archive")
    require_flag(tokens, "--rpc-addr", "0.0.0.0")
    require_flag(tokens, "--rpc-port", "8545")
    if any(char in args for char in "\n\r'\\"):
        raise ValueError("service-args cannot contain newlines, single quotes or backslashes")
    return args


def require_flag(tokens: list[str], name: str, expected: str) -> None:
    """Require one unambiguous CLI setting for the archive/RPC contract."""
    values = []
    for index, token in enumerate(tokens):
        if token == name:
            values.append(tokens[index + 1] if index + 1 < len(tokens) else "")
        elif token.startswith(name + "="):
            values.append(token.split("=", 1)[1])
    if values != [expected]:
        raise ValueError(f"service-args must set {name} {expected} exactly once")


def prepare() -> None:
    """Create a workload account without walking a multi-terabyte data directory."""
    if command("getent", "passwd", c.SERVICE, check=False).returncode:
        command(
            "useradd",
            "--system",
            "--user-group",
            "--home-dir",
            str(c.DATA),
            "--shell",
            "/usr/sbin/nologin",
            c.SERVICE,
        )
    c.DATA.mkdir(parents=True, exist_ok=True)
    shutil.chown(c.DATA, c.SERVICE, c.SERVICE)
    c.DATA.chmod(0o750)
    c.METADATA.mkdir(parents=True, exist_ok=True)


def install_binary(url: str, digest: str) -> None:
    """Verify a staged replacement before stopping the running node."""
    staged = c.BINARY.with_suffix(".new")
    try:
        download_file(url, staged)
        perform_sha256_checksum_from_string(staged, digest)
        staged.chmod(0o755)
        command(str(staged), "--version")
        command("systemctl", "stop", c.SERVICE, check=False)
        staged.replace(c.BINARY)
    finally:
        staged.unlink(missing_ok=True)


def configure(args: str, source: str) -> None:
    """Install service definitions and worker config while no import is running."""
    write_service_args(c.SERVICE, args)
    for service in (c.SERVICE, c.BOOTSTRAP_SERVICE):
        install_systemd_unit(Path("templates") / f"{service}.service", service)
    c.BOOTSTRAP_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("bootstrap.py"), c.BOOTSTRAP_SCRIPT)
    c.BOOTSTRAP_CONFIG.write_text(
        json.dumps({"binary": str(c.BINARY), "data_dir": str(c.DATA), "source": source})
    )
    c.BOOTSTRAP_CONFIG.chmod(0o644)
    command("systemctl", "enable", c.SERVICE)


def start(source: str, *, retry: bool = False) -> None:
    """Start the node or queue an import without waiting for its completion."""
    if c.MARKER.exists():
        command("systemctl", "start", c.SERVICE)
        return
    if bootstrap_running():
        return
    if not source:
        raise ValueError("snapshot-source is required until archive import completes")
    if service_state(c.BOOTSTRAP_SERVICE) == "failed" and not retry:
        raise ValueError("Snapshot import failed; inspect journal then run start-node to retry")
    command("systemctl", "start", "--no-block", c.BOOTSTRAP_SERVICE)


def version() -> str:
    """Read the installed workload version."""
    if not c.BINARY.exists():
        return "not-installed"
    return command(str(c.BINARY), "--version").stdout.strip()


def rpc(method: str) -> object:
    """Query local RPC with a bounded timeout and reject protocol errors."""
    response = requests.post(
        c.RPC_URL, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": []}, timeout=10
    )
    response.raise_for_status()
    body = response.json()
    if "error" in body:
        raise ValueError(f"{method}: {body['error']}")
    return body["result"]


def node_info() -> dict:
    """Return diagnostics without scanning archive data files."""
    disk = shutil.disk_usage(c.DATA)
    return {
        "service-state": service_state(c.SERVICE),
        "bootstrap-state": service_state(c.BOOTSTRAP_SERVICE),
        "snapshot-imported": c.MARKER.exists(),
        "version": version(),
        "service-args": c.ARGS_FILE.read_text() if c.ARGS_FILE.exists() else "",
        "disk-total-bytes": disk.total,
        "disk-free-bytes": disk.free,
    }
