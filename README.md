# DNS Tunneling Detection

Учебный ML-проект по обнаружению DNS-туннелирования (ЛР1–ЛР2).

**Направление:** Structured Data  
**Задача:** бинарная классификация DNS-трафика (`Benign` / `Malicious`).  
**Датасет:** [DNS Tunneling Dataset](https://www.kaggle.com/datasets/daumel/dns-tunneling-dataset).

## 1. Установка

```bash
git clone https://github.com/Userrewq/ml-lab.git
cd ml-lab

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 2. Подготовка данных

Скачайте датасет с Kaggle и разместите исходные CSV относительно корня проекта:

```text
raw/
├── benign/
│   └── *.csv
└── malicious/
    ├── <название_утилиты_1>/
    └── <название_утилиты_2>/
```

Запустите скрипт объединения:

```bash
python src/merge_dataset.py

mkdir -p data/raw
mv dataset_1.csv dataset_2.csv data/raw/
```

Скрипт формирует два набора данных: вредоносный трафик разделяется по группам утилит DNS-туннелирования, легитимный — без пересечения. Используется `random_state=42`.

Исходные CSV и сформированные датасеты не хранятся в GitHub.

## 3. Обучение модели

Запустите Jupyter из каталога `notebooks/`:

```bash
cd notebooks
jupyter lab --ip=127.0.0.1 --no-browser
```
Выполните ноутбуки:

1. `01_data_analysis.ipynb` — первичный анализ исходного датасета.
2. `02_data_validation.ipynb` — проверка данных, предобработка, обучение и оценка модели.
3. `02_robustness_test.ipynb` — эксперимент с изменёнными входными данными.

При необходимости скорректируйте путь к исходному CSV в первом ноутбуке.

Во втором ноутбуке используются:

- 31 числовой признак;
- разделение обучающей и тестовой выборок 50/50;
- `random_state=42`, стратификация по меткам;
- `LogisticRegression(max_iter=1000, random_state=42)`;
- сравнение с классификатором наиболее частого класса.

Результаты обучения сохраняются в:

```text
models/logistic_regression_model.onnx
metrics/baseline.json
```

Перед запуском создайте отсутствующие каталоги:

```bash
mkdir -p ../metrics
```

## 4. Предсказание и тестирование

Модуль `src/val_predict.py` содержит класс `DNSPredictor`, который проверяет входные данные перед вызовом ONNX-модели.

Ограничения входа:

- `pandas.DataFrame` или путь к CSV;
- 31 числовой признак в порядке, использованном при обучении;
- максимум 10 000 строк;
- максимальный размер CSV — 50 МБ;
- пустой ввод, NaN и Inf отклоняются.

Пример предсказания из корня проекта:

```python
import pandas as pd
from src.val_predict import DNSPredictor

sample = pd.read_csv("data/X_test_v1.csv").head(1)

predictor = DNSPredictor("models/logistic_regression_model.onnx")
print(predictor.predict(sample))
```

После обучения модели создайте тестовые данные и запустите тесты:

```bash
python tests/create_test_data.py
python -m pytest tests/ -q
```

Статический анализ Python-кода:

```bash
python -m bandit -r src/
```

## 5. Эксперимент с устойчивостью

В `02_robustness_test.ipynb` исследуются 20 тестовых объектов.

| Изменение | Изменившиеся предсказания |
|---|---:|
| Удвоение `distinct_A_records` | 0 из 20 (0%) |
| Установка `src_port = 99999` | 3 из 20 (15%) |

Эксперимент показал необходимость дополнительной семантической валидации: значение сетевого порта должно находиться в допустимом диапазоне `0–65535`.

В текущей реализации проверка этого диапазона ещё не добавлена.

## 6. Удалённый доступ к Jupyter

Jupyter запускается на виртуальной машине с привязкой к loopback:

```bash
cd ~/ml-lab/notebooks
jupyter lab --ip=127.0.0.1 --port 8888 --no-browser
```

При использовании VirtualBox NAT с пробросом SSH-порта `2222` туннель создаётся на клиентской машине:

```bash
ssh -p 2222 -L 8889:127.0.0.1:8888 mluser@127.0.0.1
```

Аутентификацию Jupyter необходимо оставить включённой. Не публикуйте токены, SSH-ключи, исходные данные и файлы модели в открытом репозитории.

## 7. Контрольные суммы

Для контроля хэш-сумм артефакта выполните:

```bash
sha256sum models/logistic_regression_model.onnx
sha256sum data/<название датасета>
```