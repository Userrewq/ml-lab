# DNS Tunneling Detection — ML Project

## О проекте

Проект посвящён анализу DNS-трафика и использованию машинного обучения для обнаружения DNS-туннелирования.

Используется [DNS Tunneling Dataset](https://www.kaggle.com/datasets/daumel/dns-tunneling-dataset) с классами `Benign` и `Malicious`.

## Структура проекта

```text
ml-lab/
├── data/
│   ├── raw/              # Исходные CSV
│   └── *.csv             # Объединённые датасеты
├── notebooks/            # Анализ и эксперименты
├── src/
│   └── merge_dataset.py  # Объединение CSV
├── models/               # Обученные модели
├── tests/                # Тесты
├── requirements.txt
├── .gitignore
└── README.md
```

## Установка

```bash
git clone https://github.com/Userrewq/ml-lab
cd ml-lab

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip check
```

Для последующих запусков достаточно активировать окружение:

```bash
source .venv/bin/activate
```

## Подготовка данных

1. Скачайте датасет с [Kaggle](https://www.kaggle.com/datasets/daumel/dns-tunneling-dataset).
2. Поместите исходные CSV в `data/raw/`, сохранив подпапки `benign` и `malicious`.
3. Запустите объединение:

```bash
python src/merge_dataset.py
```

Объединённый CSV сохранится в `data/` с временной меткой в имени. Исходные файлы не изменяются.

## Проверка SHA-256

Вычислить контрольную сумму датасета:

```bash
sha256sum data/combined_dataset_YYYYMMDD_HHMMSS.csv
```

Имя файла: combined_dataset.csv
Хэш: f20a6fc8541835170cdaa4243900269e5192690bdc3959e0742d4d01eb96543b  

## Запуск Jupyter

```bash
jupyter notebook
```

Откройте ноутбук из каталога `notebooks/`.
### Ноутбук 01_data_analysis.ipynb
Выводит информацию о распределении классов в датасете. Перед запуском необходимо в переменной path указать путь к датасету.

## Воспроизводимость и безопасность

- Используйте зависимости из `requirements.txt`.
- Не загружайте в Git датасеты, виртуальное окружение и секреты.
