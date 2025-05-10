import pandas as pd
import os
import re
import ast
import numpy as np
import matplotlib.pyplot as plt


def sanitize(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9\-_\.]+', '_', name)


def filter_csi_raw(raw_list, null_subcarriers=None):
    # Lọc trực tiếp trên raw_list (128 giá trị Re/Im)
    sub_ids = list(range(0, 31)) + list(range(-32, -1))
    if null_subcarriers is None:
        # null_subcarriers = [-32, -31, -30, -29, -28, -27, 0, 27, 28, 29, 30, 31]
        null_subcarriers = [-32, -31, -30, -29, -21, -7, 0, 7, 21, 29, 30, 31]
    remove_set = set(null_subcarriers)
    filtered = []
    for idx, sc in enumerate(sub_ids):
        if sc in remove_set:
            continue
        filtered.extend([raw_list[2*idx], raw_list[2*idx + 1]])
    return filtered
# def filter_csi_raw(raw_list, null_subcarriers=None):
#     """
#     raw_list: list of int8 values, length >= 128
#     null_subcarriers: list các sub‑carrier cần loại bỏ (DC + pilot)
#     Trả về list các byte Re/Im chỉ cho các sub‑carrier dữ liệu còn lại.
#     """

#     # 1) Bỏ 4 giá trị phức đầu (4 byte) nếu ESP32 đánh dấu first_word_invalid
#     #    Trong thực tế mình luôn bỏ 4 byte đầu, để chắc chắn.
#     data = raw_list[4:4 + 56*2]  # 56 sub‑carrier * 2 byte

#     # 2) Khởi tạo danh sách chỉ số sub‑carrier cho HT20
#     #    -28, -27, ..., -1, +1, +2, ..., +28
#     sub_ids = list(range(-28, 0)) + list(range(1, 29))

#     # 3) Danh sách sub‑carrier mặc định cần loại bỏ:
#     #    DC (=0) và 4 pilot: -21, -7, +7, +21
#     if null_subcarriers is None:
#         null_subcarriers = [0, -21, -7, 7, 21]

#     remove_set = set(null_subcarriers)

#     # 4) Lọc: với mỗi sub‑carrier, nếu không nằm trong remove_set thì giữ lại cặp I/Q
#     filtered = []
#     for idx, sc in enumerate(sub_ids):
#         if sc in remove_set:
#             continue
#         # mỗi sub‑carrier chiếm 2 byte: I ở data[2*idx], Q ở data[2*idx+1]
#         filtered.append(data[2*idx])      # Imag
#         filtered.append(data[2*idx + 1])  # Real

#     return filtered
# ---------------- Main Script ----------------
print("✅ Bắt đầu xử lý dữ liệu CSI...")

data_df = pd.read_csv('csi_data_20250508_101047.csv')
timestamp_df = pd.read_csv('timestamps.csv')

data_df['timestamp_real_ms'] = pd.to_datetime(data_df['timestamp_real_ms'], unit='ms')
timestamp_df['start_utc_ms'] = pd.to_datetime(timestamp_df['start_utc_ms'], unit='ms')
timestamp_df['end_utc_ms'] = pd.to_datetime(timestamp_df['end_utc_ms'], unit='ms')

csi_col = next(col for col in data_df.columns 
               if data_df[col].dtype == object 
               and data_df[col].str.strip().str.startswith('[').any())
print(f"- Cột CSI được phát hiện: {csi_col}")

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

# Xử lý từng sample
sample_counters = {}
for _, row in timestamp_df.iterrows():
    start, end = row['start_utc_ms'], row['end_utc_ms']
    location, label = str(row['location']), str(row['label'])
    sample_id = sample_counters.get((label, location), 1)
    sample_counters[(label, location)] = sample_id + 1
    sample_folder = os.path.join(sanitize(label), sanitize(location), f'sample{sample_id}')
    os.makedirs(sample_folder, exist_ok=True)

    mask = (data_df['timestamp_real_ms'] >= start) & (data_df['timestamp_real_ms'] <= end)
    sliced = data_df.loc[mask]
    print(f"Sample {sample_id}: {label}/{location}, rows: {len(sliced)}")

    # Danh sách devices
    devices = list(sliced.groupby('mac'))

    # Vẽ biểu đồ biên độ theo thời gian cho mỗi device riêng biệt
    for mac, grp in devices:
        safe_mac = sanitize(mac)
        csv_f = os.path.join(sample_folder, f'{safe_mac}.csv')
        grp.to_csv(csv_f, index=False)
        print(f"  - {mac}: {len(grp)} rows -> {csv_f}")

        timestamps = grp['timestamp_real_ms']
        plt.figure(figsize=(10, 4))
        for i in range(n_pairs):
            re_col = f'subcarrier_{i}_Re'
            im_col = f'subcarrier_{i}_Im'
            amp = np.sqrt(grp[re_col]**2 + grp[im_col]**2)
            plt.plot(timestamps, amp, lw=0.5)
        plt.xlabel('Thời gian')
        plt.ylabel('Biên độ CSI')
        plt.title(f'Amplitude CSI - sample{sample_id} - {label}/{location} - {mac}')
        plt.tight_layout()
        img_plot = os.path.join(sample_folder, f'{safe_mac}_amp.png')
        plt.savefig(img_plot)
        plt.close()

    # Vẽ heatmap 3x1 cho tối đa 3 device
    fig, axes = plt.subplots(3, 1, figsize=(10, 12))
    for idx, (mac, grp) in enumerate(devices[:3]):
        re_vals = grp[[f'subcarrier_{i}_Re' for i in range(n_pairs)]].values
        im_vals = grp[[f'subcarrier_{i}_Im' for i in range(n_pairs)]].values
        amp_matrix = np.sqrt(re_vals**2 + im_vals**2).T
        ax = axes[idx]
        im = ax.imshow(amp_matrix, aspect='auto', cmap='jet', interpolation='nearest')
        ax.set_title(f'{mac}')
        ax.set_ylabel('Subcarrier Index')
        ax.set_xticks([])
    for j in range(len(devices), 3):
        axes[j].axis('off')
    axes[-1].set_xlabel('Time Index')
    # Điều chỉnh layout tránh cảnh báo tight_layout
    fig.tight_layout(rect=[0, 0, 0.9, 1])
    cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
    fig.colorbar(im, cbar_ax)
    img_heat = os.path.join(sample_folder, f'sample{sample_id}_heatmap.png')
    fig.savefig(img_heat)
    plt.close(fig)

print("✅ Hoàn thành tất cả bước xử lý và vẽ CSI.")
