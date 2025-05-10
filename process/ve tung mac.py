import csv
import ast
import numpy as np
import matplotlib.pyplot as plt
import os

# Configuration
device_files = [
    '34_86_5D_39_A5_5C.csv',
    'A0_DD_6C_0F_99_C8.csv',
    'A0_DD_6C_85_F7_44.csv'
]
OUTPUT_DIR = 'heatmaps'      # Thư mục lưu ảnh
WINDOW_MS = 20_000          # Khoảng thời gian 20 giây

# Tạo thư mục lưu nếu chưa tồn tại
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Hàm parse CSI string thành numpy array
def parse_csi(csi_str):
    try:
        raw = ast.literal_eval(csi_str)
        return np.array(raw, dtype=float)
    except:
        return None

# Load dữ liệu CSI gốc, bỏ qua các dòng không parse được
def load_entries(path):
    timestamps, raw_matrix = [], []
    with open(path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            vec = parse_csi(row['CSI'])
            if vec is None:
                continue
            timestamps.append(float(row['timestamp_real_ms']))
            raw_matrix.append(vec)
    return np.array(timestamps), np.vstack(raw_matrix)

# Main: load all devices
data = {}
for csv_file in device_files:
    ts, raw = load_entries(csv_file)
    data[csv_file] = {
        'ts': ts,
        'amp': np.abs(raw)
    }

# Xác định thời gian chung từ bắt đầu sớm nhất đến kết thúc muộn nhất
all_starts = [d['ts'][0] for d in data.values()]
all_ends = [d['ts'][-1] for d in data.values()]
start_time = min(all_starts)
end_time = max(all_ends)

# Vẽ và lưu heatmap mỗi cửa sổ 20s với 3 hàng, 1 cột
window_start = start_time
while window_start < end_time:
    window_end = window_start + WINDOW_MS
    fig, axes = plt.subplots(len(device_files), 1, figsize=(80, 10 * len(device_files)))
    for ax, csv_file in zip(axes, device_files):
        ts = data[csv_file]['ts']
        amp = data[csv_file]['amp']
        n_sub = amp.shape[1]
        # Tạo blank canvas chung
        blank = np.full((2, n_sub), np.nan)
        im = ax.imshow(
            blank.T,
            aspect='auto',
            origin='lower',
            extent=[window_start/1000, window_end/1000, 0, n_sub]
        )
        # Ghi dữ liệu nếu có
        idx = np.where((ts >= window_start) & (ts < window_end))[0]
        if idx.size > 0:
            seg_amp = amp[idx, :]
            seg_ts = ts[idx]
            ax.imshow(
                seg_amp.T,
                aspect='auto',
                origin='lower',
                extent=[seg_ts[0]/1000, seg_ts[-1]/1000, 0, n_sub]
            )
        device_name = os.path.splitext(os.path.basename(csv_file))[0]
        ax.set_title(device_name)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Subcarrier Index')
        fig.colorbar(im, ax=ax, orientation='vertical', label='Amplitude')
    plt.suptitle(f'Time {int(window_start)}–{int(window_end)} ms')
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    fname = f"heatmap_{int(window_start)}_{int(window_end)}.png"
    plt.savefig(os.path.join(OUTPUT_DIR, fname))
    plt.close()
    print(f'Saved {fname}')
    window_start = window_end

print('All heatmaps saved in', OUTPUT_DIR)
