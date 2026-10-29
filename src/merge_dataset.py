import os
import glob
import pandas as pd

RAW_DIR = 'data/raw'
BENIGN_DIR = os.path.join(RAW_DIR, 'benign')
MALICIOUS_DIR = os.path.join(RAW_DIR, 'malicious')

malicious_subdirs = [
    "tcp_over_dns", "ozymandns", "iodine", "dnsexfiltrator_modified",
    "dnspot", "dnsexfiltrator", "dnscat2", "dns2tcp", "cobaltstrike"
]

def load_csvs_from_subdirs(base_dir, subdirs):
    dfs = []
    for subdir in subdirs:
        path = os.path.join(base_dir, subdir)
        if os.path.exists(path):
            files = glob.glob(os.path.join(path, '*.csv'))
            for f in files:
                df = pd.read_csv(f)
                dfs.append(df)
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

group1_subdirs = malicious_subdirs[:5]
group2_subdirs = malicious_subdirs[5:]

print(f"Dataset 1 malicious subdirs: {group1_subdirs}")
print(f"Dataset 2 malicious subdirs: {group2_subdirs}")

malicious1_df = load_csvs_from_subdirs(MALICIOUS_DIR, group1_subdirs)
malicious2_df = load_csvs_from_subdirs(MALICIOUS_DIR, group2_subdirs)

benign_df = pd.concat([pd.read_csv(f) for f in glob.glob(os.path.join(BENIGN_DIR, '*.csv'))], ignore_index=True)

n_mal1 = len(malicious1_df)
n_mal2 = len(malicious2_df)
n_benign = len(benign_df)

print(f"\nMalicious group 1: {n_mal1}")
print(f"Malicious group 2: {n_mal2}")
print(f"Benign total: {n_benign}")

if n_mal1 + n_mal2 > n_benign:
    raise ValueError(f"Недостаточно benign примеров: нужно {n_mal1 + n_mal2}, есть {n_benign}")

benign_head = benign_df.head(n_mal1)
benign_tail_start = n_mal1

if benign_tail_start + n_mal2 > n_benign:
    benign_tail_start = n_mal1 + 1
    if benign_tail_start + n_mal2 > n_benign:
        raise ValueError("Невозможно избежать пересечения при текущем распределении")

benign_tail = benign_df.iloc[benign_tail_start:benign_tail_start + n_mal2]

dataset1 = pd.concat([malicious1_df, benign_head], ignore_index=True)
dataset2 = pd.concat([malicious2_df, benign_tail], ignore_index=True)

dataset1 = dataset1.sample(frac=1, random_state=42).reset_index(drop=True)
dataset2 = dataset2.sample(frac=1, random_state=42).reset_index(drop=True)

dataset1.to_csv('dataset_1.csv', index=False)
dataset2.to_csv('dataset_2.csv', index=False)

print(f"\nDataset 1: {len(dataset1)} rows -> dataset_1.csv")
print(f"Dataset 2: {len(dataset2)} rows -> dataset_2.csv")
print(f"\nClass distribution (dataset 1):\n{dataset1['label'].value_counts()}")
print(f"\nClass distribution (dataset 2):\n{dataset2['label'].value_counts()}")