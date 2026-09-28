"""Protect node installation, archive flags and asynchronous bootstrap behavior."""

import subprocess
from unittest.mock import patch

import pytest

import constants as c
import octez

CONFIG = {
    "binary-url": "https://example.test/octez",
    "binary-sha256": "a" * 64,
    "snapshot-source": "https://example.test/archive",
    "service-args": "--network mainnet --history archive --rpc-addr 0.0.0.0 --rpc-port 8545",
}


@pytest.mark.parametrize(
    "args",
    [
        "--history full:30 --rpc-addr 0.0.0.0 --rpc-port 8545",
        CONFIG["service-args"] + " --history rolling:7",
        CONFIG["service-args"] + " --data-dir=/tmp/other",
        CONFIG["service-args"] + " --init-from-snapshot",
        CONFIG["service-args"].replace("8545", "9545"),
    ],
)
def test_conflicting_archive_and_managed_flags_are_rejected(args):
    with pytest.raises(ValueError):
        octez.validate_config({**CONFIG, "service-args": args})


def test_explicit_archive_flags_accept_equals_syntax():
    args = "--history=archive --rpc-addr=0.0.0.0 --rpc-port=8545"
    assert octez.validate_config({**CONFIG, "service-args": args}) == args


def test_binary_checksum_failure_preserves_running_service_and_old_binary(tmp_path, monkeypatch):
    binary = tmp_path / "octez"
    binary.write_bytes(b"old")
    monkeypatch.setattr(c, "BINARY", binary)
    with patch("octez.download_file", side_effect=lambda url, path: path.write_bytes(b"bad")):
        with patch("octez.command") as command, pytest.raises(ValueError, match="checksum"):
            octez.install_binary(CONFIG["binary-url"], "a" * 64)
    assert binary.read_bytes() == b"old"
    command.assert_not_called()
    assert not binary.with_suffix(".new").exists()


def test_binary_replacement_stops_only_after_download_and_validation(tmp_path, monkeypatch):
    import hashlib

    binary = tmp_path / "octez"
    binary.write_bytes(b"old")
    monkeypatch.setattr(c, "BINARY", binary)
    calls = []

    def download(url, path):
        calls.append("download")
        path.write_bytes(b"new")

    def command(*args, **kwargs):
        if args[0] == "systemctl":
            assert binary.read_bytes() == b"old"
        calls.append(args[1])
        return subprocess.CompletedProcess(args, 0, "0.66", "")

    with patch("octez.download_file", side_effect=download), patch("octez.command", side_effect=command):
        octez.install_binary(CONFIG["binary-url"], hashlib.sha256(b"new").hexdigest())
    assert calls == ["download", "--version", "stop"]
    assert binary.read_bytes() == b"new"


def test_snapshot_start_does_not_wait_for_import(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "MARKER", tmp_path / "marker")
    with patch("octez.service_state", return_value="inactive"), patch("octez.command") as command:
        octez.start("https://example.test/archive")
    assert command.call_args.args == ("systemctl", "start", "--no-block", "octez-bootstrap")


def test_failed_snapshot_requires_operator_retry(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "MARKER", tmp_path / "marker")
    with patch("octez.service_state", return_value="failed"), patch("octez.command") as command:
        with pytest.raises(ValueError, match="start-node"):
            octez.start("https://example.test/archive")
        command.assert_not_called()
        octez.start("https://example.test/archive", retry=True)
        command.assert_called_once()
