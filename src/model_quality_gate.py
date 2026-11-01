import json
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from val_predict import DNSPredictor  # noqa: E402


DATA_DIR = ROOT / "data" / "ci"
METRICS_DIR = ROOT / "metrics"

BASELINE_PATH = METRICS_DIR / "ci_baseline.json"
RESULT_PATH = METRICS_DIR / "model_gate_result.json"
MODEL_PATH = ROOT / "models" / "logistic_regression_model.onnx"


def main():
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    manifest = json.loads(
        (DATA_DIR / "manifest.json").read_text(encoding="utf-8")
    )

    if manifest["dataset_version"] != baseline["dataset_version"]:
        raise ValueError("Dataset version does not match baseline")

    X = pd.read_csv(DATA_DIR / "control_X.csv")
    y = pd.read_csv(DATA_DIR / "control_y.csv")["label"]

    if len(X) != len(y) or len(X) == 0:
        raise ValueError("Invalid control dataset shape")

    predictor = DNSPredictor(str(MODEL_PATH))
    predictions = predictor.predict(X)

    if len(predictions) != len(y):
        raise ValueError("Prediction count does not match target count")

    f1 = float(f1_score(y, predictions, average="weighted"))
    accuracy = float(accuracy_score(y, predictions))

    baseline_f1 = float(baseline["main_metric_value"])
    degradation = float(baseline["allowed_relative_degradation"])
    minimum_f1 = baseline_f1 * (1 - degradation)

    if not all(map(lambda x: 0 <= x <= 1, [f1, accuracy, baseline_f1])):
        raise ValueError("Invalid metric value")

    passed = f1 >= minimum_f1

    result = {
        "dataset_version": manifest["dataset_version"],
        "model": str(MODEL_PATH.relative_to(ROOT)),
        "metric": "f1_weighted",
        "baseline_f1": baseline_f1,
        "candidate_f1": f1,
        "minimum_acceptable_f1": minimum_f1,
        "accuracy": accuracy,
        "allowed_relative_degradation": degradation,
        "passed": passed
    }

    METRICS_DIR.mkdir(exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8"
    )

    print(json.dumps(result, indent=2))

    if not passed:
        raise ValueError("MODEL QUALITY GATE FAILED: F1 below threshold")

    print("MODEL QUALITY GATE: PASSED")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"MODEL QUALITY GATE: FAILED: {error}", file=sys.stderr)
        sys.exit(1)
