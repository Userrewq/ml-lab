import os
import pandas as pd
import numpy as np
import onnxruntime as ort

MAX_FILE_SIZE_MB = 50
MAX_ROWS = 10000
EXPECTED_FEATURES = 31

class DNSPredictor:
    def __init__(self, model_path='models/logistic_regression_model.onnx'):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Модель не найдена: {model_path}")
        self.session = ort.InferenceSession(model_path)
        self.input_name = self.session.get_inputs()[0].name

    def _load_data(self, input_data):
        if isinstance(input_data, str):
            if not os.path.exists(input_data):
                raise FileNotFoundError(f"Файл не найден: {input_data}")
            if os.path.getsize(input_data) / (1024 * 1024) > MAX_FILE_SIZE_MB:
                raise ValueError(f"Файл превышает лимит {MAX_FILE_SIZE_MB} МБ")
            try:
                df = pd.read_csv(input_data, nrows=MAX_ROWS + 1)
            except Exception as e:
                raise ValueError(f"Не удалось прочитать файл: {e}")
            if len(df) > MAX_ROWS:
                raise ValueError(f"Файл содержит более {MAX_ROWS} строк. Отклонено.")
            return df
        elif isinstance(input_data, pd.DataFrame):
            if len(input_data) > MAX_ROWS:
                raise ValueError(f"DataFrame содержит более {MAX_ROWS} строк. Отклонено.")
            return input_data
        else:
            raise TypeError("Ожидается pandas.DataFrame или путь к файлу (str).")

    def _validate_data(self, data):
        if data.empty:
            raise ValueError("Входные данные пусты.")
        
        numeric_data = data.select_dtypes(include=['number'])
        
        if numeric_data.shape[1] != EXPECTED_FEATURES:
            raise ValueError(f"Ожидается {EXPECTED_FEATURES} числовых признаков, получено {numeric_data.shape[1]}.")
        
        if data.isnull().any().any():
            raise ValueError("Данные содержат NaN. Требуется предварительная очистка.")
        
        if np.isinf(numeric_data.values).any():
            raise ValueError("Данные содержат Inf. Требуется предварительная очистка.")
        
        return numeric_data

    def predict(self, input_data):
        data = self._load_data(input_data)
        numeric_data = self._validate_data(data)
        input_array = numeric_data.values.astype(np.float32)
        result = self.session.run(None, {self.input_name: input_array})
        return result[0].tolist()