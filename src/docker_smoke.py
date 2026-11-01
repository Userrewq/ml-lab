import pandas as pd

from val_predict import DNSPredictor


def main():
    X = pd.read_csv("data/ci/control_X.csv")

    predictor = DNSPredictor("models/logistic_regression_model.onnx")
    predictions = predictor.predict(X)

    if len(predictions) != len(X):
        raise RuntimeError("Prediction count mismatch")

    if not all(value in (0, 1) for value in predictions):
        raise RuntimeError("Unexpected prediction values")

    print("DOCKER SMOKE TEST: PASSED")
    print(f"Rows: {len(X)}")
    print(f"Predictions: {len(predictions)}")


if __name__ == "__main__":
    main()
