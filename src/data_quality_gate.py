import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "ci"

EXPECTED_VERSION = "dns-ci-control-v1"
MIN_ROWS = 100
MIN_CLASS_SHARE = 0.10


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_data():
    manifest_path = DATA_DIR / "manifest.json"

    if not manifest_path.is_file():
        raise ValueError("Manifest file is missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("dataset_version") != EXPECTED_VERSION:
        raise ValueError("Unsupported dataset version")

    X_path = DATA_DIR / "control_X.csv"
    y_path = DATA_DIR / "control_y.csv"

    for name, path in [
        ("control_X.csv", X_path),
        ("control_y.csv", y_path),
    ]:
        if not path.is_file():
            raise ValueError(f"Missing file: {name}")

        expected_hash = manifest["files"].get(name)
        if not expected_hash or sha256(path) != expected_hash:
            raise ValueError(f"SHA256 mismatch: {name}")

    X = pd.read_csv(X_path)
    y = pd.read_csv(y_path)

    expected_features = manifest["features"]

    if X.columns.tolist() != expected_features:
        raise ValueError("Feature schema or column order mismatch")

    if list(y.columns) != ["label"]:
        raise ValueError("Target schema mismatch")

    if len(X) != len(y):
        raise ValueError("Feature/target row count mismatch")

    if len(X) < MIN_ROWS:
        raise ValueError("Too few samples")

    if len(X) != manifest["rows"]:
        raise ValueError("Manifest row count mismatch")

    if X.shape[1] != manifest["feature_count"]:
        raise ValueError("Manifest feature count mismatch")

    if not all(pd.api.types.is_numeric_dtype(dtype) for dtype in X.dtypes):
        raise ValueError("Non-numeric feature type")

    if X.isna().any().any() or y.isna().any().any():
        raise ValueError("Missing values detected")

    if not np.isfinite(X.to_numpy(dtype=float)).all():
        raise ValueError("NaN or Inf detected in features")

    if not set(y["label"].unique()).issubset({0, 1}):
        raise ValueError("Unexpected target label")

    counts = y["label"].value_counts().to_dict()
    total = len(y)

    if len(counts) != 2:
        raise ValueError("Both classes must be present")

    if min(counts.values()) / total < MIN_CLASS_SHARE:
        raise ValueError("Class distribution is too imbalanced")

    expected_classes = {
        str(key): int(value)
        for key, value in counts.items()
    }

    if expected_classes != manifest["classes"]:
        raise ValueError("Class distribution differs from manifest")

    print("DATA QUALITY GATE: PASSED")
    print(f"Dataset version: {EXPECTED_VERSION}")
    print(f"Samples: {len(X)}")
    print(f"Features: {X.shape[1]}")
    print(f"Classes: {expected_classes}")


if __name__ == "__main__":
    try:
        check_data()
    except Exception as error:
        print(f"DATA QUALITY GATE: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
