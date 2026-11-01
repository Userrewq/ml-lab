import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from val_predict import DNSPredictor

@pytest.fixture
def predictor():
    return DNSPredictor(model_path='models/logistic_regression_model.onnx')


def test_positive_valid_dataframe(predictor):
    df = pd.read_csv('tests/data/valid_small.csv')
    predictions = predictor.predict(df)
    assert isinstance(predictions, list)
    assert len(predictions) == len(df)
    assert all(p in [0, 1] for p in predictions)

def test_positive_valid_file(predictor):
    predictions = predictor.predict('tests/data/valid_small.csv')
    assert isinstance(predictions, list)
    assert len(predictions) > 0

def test_invalid_type(predictor):
    with pytest.raises(TypeError, match="Ожидается pandas.DataFrame или путь к файлу"):
        predictor.predict({"key": "value"})

def test_empty_dataframe(predictor):
    df = pd.DataFrame()
    with pytest.raises(ValueError, match="Входные данные пусты"):
        predictor.predict(df)

def test_dataframe_with_nan(predictor):
    df = pd.read_csv('tests/data/with_nan.csv')
    with pytest.raises(ValueError, match="Данные содержат NaN"):
        predictor.predict(df)

def test_dataframe_with_inf(predictor):
    df = pd.read_csv('tests/data/valid_small.csv')
    df['src_port'] = df['src_port'].astype(float)
    df.loc[0, 'src_port'] = np.inf
    with pytest.raises(ValueError, match="Данные содержат Inf"):
        predictor.predict(df)

def test_wrong_number_of_features(predictor):
    df = pd.read_csv('tests/data/wrong_columns.csv')
    with pytest.raises(ValueError, match="Ожидается .* числовых признаков"):
        predictor.predict(df)

def test_file_exceeds_row_limit(predictor, tmp_path):
    df = pd.read_csv('tests/data/valid_small.csv')
    large_df = pd.concat([df] * 1001, ignore_index=True)

    large_file = tmp_path / "exceeds_limit.csv"
    large_df.to_csv(large_file, index=False)

    with pytest.raises(ValueError, match="содержит более .* строк"):
        predictor.predict(str(large_file))

def test_corrupted_file(predictor):
    with pytest.raises(ValueError, match="Не удалось прочитать файл"):
        predictor.predict('tests/data/corrupted.csv')

def test_file_not_found(predictor):
    with pytest.raises(FileNotFoundError, match="Файл не найден"):
        predictor.predict('nonexistent_file.csv')