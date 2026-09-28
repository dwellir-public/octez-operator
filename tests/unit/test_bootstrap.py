"""Snapshot import owns the no-overwrite and completion-marker contracts."""

import subprocess
from unittest.mock import patch

import pytest

from bootstrap import import_snapshot


def test_import_marks_success_only_after_real_store_exists(tmp_path):
    config = {
        "binary": "/usr/bin/octez",
        "data_dir": str(tmp_path),
        "source": "https://snapshot.test/archive",
    }

    def import_process(args, check):
        assert "--force" not in args
        assert args[3] == config["source"]
        assert not (tmp_path / ".snapshot-imported").exists()
        (tmp_path / "store.sqlite").touch()

    with patch("bootstrap.subprocess.run", side_effect=import_process) as run:
        import_snapshot(config)
        import_snapshot(config)
    assert (tmp_path / ".snapshot-imported").exists()
    assert run.call_count == 1


@pytest.mark.parametrize(
    "existing, message",
    [
        ("store", "Existing node data"),
        ("store.sqlite", "Existing node data"),
        (".octez_evm_node_import_abcd", "Interrupted native snapshot staging"),
    ],
)
def test_ambiguous_snapshot_data_is_never_overwritten(tmp_path, existing, message):
    (tmp_path / existing).touch()
    with patch("bootstrap.subprocess.run") as run, pytest.raises(RuntimeError, match=message):
        import_snapshot({"binary": "octez", "data_dir": str(tmp_path), "source": "snapshot"})
    run.assert_not_called()
    assert not (tmp_path / ".snapshot-imported").exists()


def test_failed_import_remains_retryable_without_success_marker(tmp_path):
    with patch("bootstrap.subprocess.run", side_effect=subprocess.CalledProcessError(1, "octez")):
        with pytest.raises(subprocess.CalledProcessError):
            import_snapshot({"binary": "octez", "data_dir": str(tmp_path), "source": "snapshot"})
    assert not (tmp_path / ".snapshot-imported").exists()
