"""Shared fixtures. Every test runs with HS_STATE_ROOT and HOME inside a temporary root, so no test
can touch ~/.local/share/humanity-succeed or any other real state."""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from humanity_succeed.canonical import load_document

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = REPO / "examples"
DEV_CASES = REPO / "cases" / "commissioning_dev"
TRAJ = DEV_CASES / "trajectories"


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HS_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


@pytest.fixture
def correction_doc() -> dict:
    return copy.deepcopy(load_document(EXAMPLES / "correction.yaml"))


def load_case_doc(path: Path) -> dict:
    return copy.deepcopy(load_document(path))
