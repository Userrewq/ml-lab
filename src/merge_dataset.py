
from pathlib import Path
from datetime import datetime
import argparse

import pandas as pd


def main():
    project_dir = Path(__file__).resolve().parent.parent
    input_dir = project_dir / "data" / "raw"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = project_dir / "data" / f"combined_dataset_{timestamp}.csv"

    parser = argparse.ArgumentParser(
        description="Объединение CSV-файлов DNS Tunneling Dataset"
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=100_000,
        help="Количество строк за один проход",
    )
    args = parser.parse_args()

    if not input_dir.is_dir():
        parser.error(f"Каталог не найден: {input_dir}")

    if args.chunksize <= 0:
        parser.error("--chunksize должен быть больше нуля")

    files = sorted(input_dir.rglob("*.csv"))

    if not files:
        parser.error(f"В каталоге {input_dir} нет CSV-файлов")

    expected_columns = None
    total_rows = 0
    processed_files = 0

    try:
        for file in files:
            print(f"Обработка: {file}")

            parts = {part.lower() for part in file.parts}

            if "benign" in parts:
                inferred_label = "Benign"
            elif "malicious" in parts:
                inferred_label = "Malicious"
            else:
                inferred_label = None

            try:
                for chunk in pd.read_csv(file, chunksize=args.chunksize):
                    if "label" not in chunk.columns:
                        if inferred_label is None:
                            raise ValueError(
                                f"Не удалось определить label для {file}"
                            )
                        chunk["label"] = inferred_label

                    if expected_columns is None:
                        expected_columns = list(chunk.columns)
                    elif set(chunk.columns) != set(expected_columns):
                        raise ValueError(
                            f"Набор столбцов отличается в файле: {file}"
                        )

                    chunk = chunk[expected_columns]
                    chunk.to_csv(
                        output_file,
                        mode="a",
                        header=(total_rows == 0),
                        index=False,
                    )
                    total_rows += len(chunk)

                processed_files += 1

            except pd.errors.EmptyDataError:
                print(f"Пустой файл пропущен: {file}")

        if total_rows == 0:
            raise ValueError("В исходных файлах нет строк")

    except Exception:
        output_file.unlink(missing_ok=True)
        raise

    print("\nОбъединение завершено.")
    print(f"Обработано файлов: {processed_files}")
    print(f"Всего строк: {total_rows:,}")
    print(f"Результат: {output_file}")


if __name__ == "__main__":
    main()
