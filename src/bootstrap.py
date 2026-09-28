"""Run snapshot import outside Juju hooks without replacing node data."""

import json
import subprocess
from pathlib import Path


def import_snapshot(config: dict) -> None:
    """Import once, then record success only after the client exits successfully."""
    data = Path(config["data_dir"])
    marker = data / ".snapshot-imported"
    if marker.exists():
        return
    if (data / "store").exists() or (data / "store.sqlite").exists():
        raise RuntimeError("Existing node data found without import marker; inspect before recovery")
    if any(data.glob(".octez_evm_node_import_*")):
        raise RuntimeError("Interrupted native snapshot staging found; inspect before recovery")
    subprocess.run(
        [config["binary"], "snapshot", "import", config["source"], "--data-dir", str(data)],
        check=True,
    )
    if not (data / "store.sqlite").is_file():
        raise RuntimeError("Snapshot import returned without store.sqlite")
    marker.touch()


if __name__ == "__main__":
    import_snapshot(json.loads(Path("/etc/octez-bootstrap.json").read_text()))
