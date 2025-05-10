import pandas as pd
import os
import re
import ast
import numpy as np
import matplotlib.pyplot as plt


def sanitize(name: str) -> str:
    # Thay tất cả ký tự không phải chữ, số, dấu gạch ngang hoặc gạch dưới thành gạch dưới
    return re.sub(r'[^A-Za-z0-9\-_\.]', '_', name)


def filter_csi_raw(raw_list, null_subcarriers=None):
    """
    Lọc trực tiếp trên danh sách raw_list độ dài 128 (Re/Im xen kẽ).
    - null_subcarriers: danh sách subcarrier index theo chuẩn 64-FFT.
      Theo chuẩn IEEE 802.11, bỏ 12 subcarriers (guard bands + DC).
    Trả về raw_filtered vẫn giữ định dạng gồm cả Re và Im.
    """
    sub_ids = list(range(0, 32)) + list(range(-32, 0))
    if null_subcarriers is None:
        null_subcarriers = [-32, -31, -30, -29, -28, -27, 0, 27, 28, 29, 30, 31]
    remove_set = set(null_subcarriers)
    filtered = []
    for idx, sc in enumerate(sub_ids):
        if sc in remove_set:
            continue
        filtered.extend([raw_list[2*idx], raw_list[2*idx + 1]])
    return filtered

# ---------------- Main Script ----------------
print("✅ Bắt đầu xử lý dữ liệu CSI...")

# Đọc dữ liệu
data_df = pd.read_csv('merged.csv')
timestamp_df = pd.read_csv('timestamps.csv')

# Chuyển timestamp
data_df['timestamp_local_us'] = pd.to_datetime(data_df['timestamp_local_us'], unit='ms')
timestamp_df['start_utc_ms'] = pd.to_datetime(timestamp_df['start_utc_ms'], unit='ms')
timestamp_df['end_utc_ms'] = pd.to_datetime(timestamp_df['end_utc_ms'], unit='ms')

# Phát hiện cột CSI
csi_col = next(col for col in data_df.columns if data_df[col].dtype == object and data_df[col].str.strip().str.startswith('[').any())
print(f"- Cột CSI được phát hiện: {csi_col}")

# Áp dụng lọc null subcarriers
data_df[csi_col] = data_df[csi_col].apply(lambda s: filter_csi_raw(ast.literal_eval(s)))
post_len = len(data_df[csi_col].iloc[0])
print(f"- Độ dài raw_list sau lọc: {post_len} (mong muốn 104)")

# Mở rộng thành cột Re và Im
n_pairs = post_len // 2
cols = []
for i in range(n_pairs):
    cols += [f'subcarrier_{i}_Re', f'subcarrier_{i}_Im']
csi_expanded = pd.DataFrame(data_df[csi_col].tolist(), index=data_df.index, columns=cols)
data_df = pd.concat([data_df.drop(columns=[csi_col]), csi_expanded], axis=1)

# Tách và lưu theo sample, vẽ amplitude 52 subcarriers theo thời gian
sample_counters = {}
for _, row in timestamp_df.iterrows():
    start, end = row['start_utc_ms'], row['end_utc_ms']
    location, label = str(row['location']), str(row['label'])
    sample_id = sample_counters.get((label, location), 1)
    sample_counters[(label, location)] = sample_id + 1
    sample_folder = os.path.join(sanitize(label), sanitize(location), f'sample{sample_id}')
    os.makedirs(sample_folder, exist_ok=True)
    mask = (data_df['timestamp_local_us'] >= start) & (data_df['timestamp_local_us'] <= end)
    sliced = data_df.loc[mask]
    print(f"Sample {sample_id}: {label}/{location}, rows: {len(sliced)}")
    for mac, grp in sliced.groupby('mac'):
        safe_mac = sanitize(mac)
        csv_f = os.path.join(sample_folder, f'{safe_mac}.csv')
        grp.to_csv(csv_f, index=False)
        print(f"  - {mac}: {len(grp)} rows -> {csv_f}")

        # Tính và vẽ biên độ cho 52 subcarriers
        timestamps = grp['timestamp_local_us']
        plt.figure(figsize=(10, 6))
        for i in range(n_pairs):
            re_col = f'subcarrier_{i}_Re'
            im_col = f'subcarrier_{i}_Im'
            amp = np.sqrt(grp[re_col]**2 + grp[im_col]**2)
            plt.plot(timestamps, amp)
        plt.xlabel('Thời gian')
        plt.ylabel('Biên độ CSI')
        plt.title(f'Biên độ CSI sample{sample_id} - {label}/{location} - {mac}')
        plt.tight_layout()
        img_f = os.path.join(sample_folder, f'{safe_mac}.png')
        plt.savefig(img_f)
        plt.close()

print("✅ Hoàn thành lọc và vẽ biên độ các subcarriers CSI.")
