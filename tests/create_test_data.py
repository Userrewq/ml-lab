import pandas as pd
import numpy as np
import os

os.makedirs('tests/data', exist_ok=True)

valid_df = pd.read_csv('data/raw/dataset_1.csv').head(10)
valid_df.to_csv('tests/data/valid_small.csv', index=False)

nan_df = valid_df.copy()
nan_df.iloc[0, 0] = np.nan
nan_df.to_csv('tests/data/with_nan.csv', index=False)

wrong_cols_df = valid_df.iloc[:, :10]
wrong_cols_df.to_csv('tests/data/wrong_columns.csv', index=False)

large_df = pd.concat([valid_df] * 1001, ignore_index=True)
large_df.to_csv('tests/data/exceeds_limit.csv', index=False)

with open('tests/data/corrupted.csv', 'wb') as f:
    f.write(b'\xff\xfe\xfd\xfc\xfb\xfa\xf9\xf8')

print(f"valid_small.csv: {valid_df.shape}")
print(f"with_nan.csv: {nan_df.shape}")
print(f"wrong_columns.csv: {wrong_cols_df.shape}")
print(f"exceeds_limit.csv: {large_df.shape}")
print("corrupted.csv: binary garbage")
print("\nTest data created in tests/data/")