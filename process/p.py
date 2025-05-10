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
data_df = pd.read_csv('merged.csv')  # mac, timestamp_local_us, và CSI dưới dạng chuỗi danh sách
timestamp_df = pd.read_csv('timestamps.csv')  # start_utc_ms, end_utc_ms, location, label

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

# Tách và lưu theo sample, vẽ amplitude và heatmap 3x1
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

    # Lấy danh sách các devices (mac)
    devices = list(sliced.groupby('mac'))  # list of (mac, DataFrame)
    # Chuẩn bị figure với 3 subplots (3 hàng 1 cột)
    fig, axes = plt.subplots(3, 1, figsize=(10, 12))
    for idx, (mac, grp) in enumerate(devices[:3]):
        safe_mac = sanitize(mac)
        # Lưu CSV
        csv_f = os.path.join(sample_folder, f'{safe_mac}.csv')
        grp.to_csv(csv_f, index=False)
        print(f"  - {mac}: {len(grp)} rows -> {csv_f}")

        # Tính amplitude matrix: shape (n_pairs, n_times)
        re_vals = grp[[f'subcarrier_{i}_Re' for i in range(n_pairs)]].values  # shape (rows, n_pairs)
        im_vals = grp[[f'subcarrier_{i}_Im' for i in range(n_pairs)]].values
        amp_matrix = np.sqrt(re_vals**2 + im_vals**2).T  # shape (n_pairs, rows)

        # Vẽ heatmap
        ax = axes[idx]
        im = ax.imshow(amp_matrix, aspect='auto', cmap='jet', interpolation='nearest')
        ax.set_title(f'{mac}')
        ax.set_ylabel('Subcarrier Index')
        ax.set_xticks([])
    # Với số device < 3, tắt axis trống
    for j in range(len(devices), 3):
        axes[j].axis('off')
    axes[-1].set_xlabel('Time Index')
    fig.colorbar(im, ax=axes, orientation='vertical', fraction=0.02, pad=0.02)
    plt.tight_layout()
    # Lưu heatmap image
    img_f = os.path.join(sample_folder, f'heatmap_sample{sample_id}.png')
    fig.savefig(img_f)
    plt.close(fig)

print("✅ Hoàn thành lọc và tạo heatmap CSI cho mỗi sample.")
