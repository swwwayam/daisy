"""Package corruption must be detected before pickle deserialization."""
import hashlib
import json
from unittest.mock import patch

import joblib
import pytest

from daisy_predict import load_model, verify_package


def package(directory):
    members = {"model.joblib": b"trusted model", "metadata.json": b'{"model":"ridge"}'}
    for name, content in members.items():
        (directory / name).write_bytes(content)
    (directory / "checksums.json").write_text(json.dumps({"format_version": 1, "files": {
        name: hashlib.sha256(content).hexdigest() for name, content in members.items()
    }}), encoding="utf-8")
    return directory / "model.joblib"


@pytest.mark.parametrize("name", ["model.joblib", "metadata.json"])
@pytest.mark.parametrize("damage", ["changed", "missing"])
def test_damage_is_rejected_before_loading(tmp_path, name, damage):
    model = package(tmp_path)
    if damage == "missing":
        (tmp_path / name).unlink()
    else:
        (tmp_path / name).write_bytes(b"corrupt")
    with patch("daisy_predict.joblib.load") as deserialize:
        with pytest.raises(ValueError, match="integrity check failed"):
            load_model(model)
        deserialize.assert_not_called()


@pytest.mark.parametrize("manifest", [[], {}, {"format_version": 2, "files": {}},
    {"format_version": 1, "files": {"model.joblib": "bad digest"}},
    {"format_version": 1, "files": {"model.joblib": "0" * 64, "../outside": "0" * 64}}])
def test_invalid_manifests_fail_closed(tmp_path, manifest):
    model = package(tmp_path)
    (tmp_path / "checksums.json").write_text(json.dumps(manifest), encoding="utf-8")
    with patch("daisy_predict.joblib.load") as deserialize:
        with pytest.raises(ValueError, match="integrity check failed"):
            load_model(model)
        deserialize.assert_not_called()


def test_manifest_cannot_reference_files_outside_package(tmp_path):
    model = package(tmp_path)
    manifest = json.loads((tmp_path / "checksums.json").read_text(encoding="utf-8"))
    manifest["files"]["../outside"] = "0" * 64
    (tmp_path / "checksums.json").write_text(json.dumps(manifest), encoding="utf-8")
    with patch("daisy_predict.joblib.load") as deserialize:
        with pytest.raises(ValueError, match="Invalid package filename"):
            load_model(model)
        deserialize.assert_not_called()


def test_legacy_package_remains_loadable(tmp_path):
    path = tmp_path / "model.joblib"
    joblib.dump({"format_version": 1, "legacy": True}, path)
    assert verify_package(path) is False
    assert load_model(path)["legacy"] is True
