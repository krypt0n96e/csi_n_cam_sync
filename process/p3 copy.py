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

# Tạo thư mục chung để lưu plot
os.makedirs('plot', exist_ok=True)

# Đọc dữ liệu
data_df = pd.read_csv('csi_data_20250508_101047.csv')
timestamp_df = pd.read_csv('timestamps.csv')

data_df['timestamp_real_ms'] = pd.to_datetime(data_df['timestamp_real_ms'], unit='ms')
timestamp_df['start_utc_ms'] = pd.to_datetime(timestamp_df['start_utc_ms'], unit='ms')
timestamp_df['end_utc_ms'] = pd.to_datetime(timestamp_df['end_utc_ms'], unit='ms')

# Tìm cột CSI và lọc
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

    # Lọc dữ liệu theo thời gian
    mask = (data_df['timestamp_real_ms'] >= start) & (data_df['timestamp_real_ms'] <= end)
    sliced = data_df.loc[mask]
    # print(f"Sample {sample_id}: {label}/{location}, rows: {len(sliced)}")

    # Danh sách devices
    devices = list(sliced.groupby('mac'))

    # Tạo figure với 3 hàng 2 cột
    fig, axes = plt.subplots(3, 2, figsize=(80, 20))
    for idx in range(3):
        if idx < len(devices):
            mac, grp = devices[idx]
            safe_mac = sanitize(mac)

            # Heatmap ở cột 0
            re_vals = grp[[f'subcarrier_{i}_Re' for i in range(n_pairs)]].values
            im_vals = grp[[f'subcarrier_{i}_Im' for i in range(n_pairs)]].values
            amp_matrix = np.sqrt(re_vals**2 + im_vals**2).T
            ax_h = axes[idx, 0]
            imh = ax_h.imshow(amp_matrix, aspect='auto', cmap='jet', interpolation='nearest')
            ax_h.set_title(f'Heatmap - {mac}')
            ax_h.set_ylabel('Subcarrier')
            ax_h.set_xticks([])

            # Line plot ở cột 1
            ax_l = axes[idx, 1]
            for i in range(n_pairs):
                re_col = f'subcarrier_{i}_Re'
                im_col = f'subcarrier_{i}_Im'
                amp = np.sqrt(grp[re_col]**2 + grp[im_col]**2)
                ax_l.plot(grp['timestamp_real_ms'], amp, lw=0.5)
            ax_l.set_title(f'Amplitude - {mac}')
            ax_l.set_xlabel('Time')
            ax_l.set_ylabel('Amplitude')
        else:
            # Không có device, tắt cả hai subplot
            axes[idx, 0].axis('off')
            axes[idx, 1].axis('off')

    # Chỉnh layout và thêm colorbar cho heatmaps
    fig.tight_layout(rect=[0, 0, 0.92, 1])
    cbar_ax = fig.add_axes([0.93, 0.15, 0.02, 0.7])
    fig.colorbar(imh, cbar_ax)

    # Lưu plot chung vào thư mục 'plot'
    fname = f'plot_location_{sanitize(location)}_label_{sanitize(label)}_sample{sample_id}.jpg'
    out_path = os.path.join('plot', fname)
    plt.savefig(out_path)
    plt.close(fig)
    # print(f"  -> Saved combined plot: {out_path}")

print("✅ Hoàn thành tất cả bước xử lý và vẽ CSI.")
