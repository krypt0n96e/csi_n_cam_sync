import pandas as pd
import os
import re
import ast
import numpy as np
import matplotlib.pyplot as plt


def sanitize(name: str) -> str:
    return re.sub(r'[^A-Za-z0-9\-_\.]+', '_', name)


def filter_csi_raw(raw_list, null_subcarriers=None):
    # print(f"- Độ dài raw_list trước lọc: {len(raw_list)}")
    sub_ids = list(range(0,1))+ list(range(0, 32)) + list(range(-31, 0))
    # print(f"- sub_ids: {sub_ids}")
    if null_subcarriers is None:
        null_subcarriers = [-31, -30, -29, 0, 28, 29, 30, 31]
        # null_subcarriers = []
        # null_subcarriers = [-32, -31, -30, -29, 0, 1, 29, 30, 31]
    remove_set = set(null_subcarriers)
    filtered = []
    for idx, sc in enumerate(sub_ids):
        if sc in remove_set:
            continue
        filtered.extend([raw_list[2*idx], raw_list[2*idx + 1]])
    # print(f"- Đã lọc {len(sub_ids) - len(filtered)//2} subcarriers")    
    return filtered


# ---------------- Main Script ----------------
print("✅ Bắt đầu xử lý dữ liệu CSI...")

root_output_folder = "output_csi_samples_snapped_forward_v2"
os.makedirs(root_output_folder, exist_ok=True)

data_df = pd.read_csv('output_snapped_with_logic.csv')
timestamp_df = pd.read_csv('timestamps.csv')

# data_df['timestamp_real_ms'] = pd.to_datetime(data_df['timestamp_real_ms'], unit='ms')
# timestamp_df['start_utc_ms'] = pd.to_datetime(timestamp_df['start_utc_ms'], unit='ms')
# timestamp_df['end_utc_ms'] = pd.to_datetime(timestamp_df['end_utc_ms'], unit='ms')

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
plot_folder = os.path.join(root_output_folder,'plot_v2')
os.makedirs(plot_folder, exist_ok=True)
sample_counters = {}
for _, row in timestamp_df.iterrows():
    start, end = row['start_utc_ms'], row['end_utc_ms']
    location, label = str(row['location']), str(row['label'])
    sample_id = sample_counters.get((label, location), 1)
    sample_counters[(label, location)] = sample_id + 1
    sample_folder = os.path.join(root_output_folder, sanitize(label), sanitize(location), f'sample{sample_id}')
    # sample_folder = os.path.join(root_output_folder,'plot_v2')
    os.makedirs(sample_folder, exist_ok=True)

    mask = (data_df['timestamp_real_ms'] >= start) & (data_df['timestamp_real_ms'] <= end)
    sliced = data_df.loc[mask]
    # print(f"Sample {sample_id}: {label}/{location}, rows: {len(sliced)}")

    devices = list(sliced.groupby('mac'))

    for mac, grp in devices:
        safe_mac = sanitize(mac)
        csv_f = os.path.join(sample_folder, f'{safe_mac}.csv')
        grp.to_csv(csv_f, index=False)
        # print(f"  - {mac}: {len(grp)} rows -> {csv_f}")

    # Vẽ subplot 3x2: heatmap và line plot cho tối đa 3 thiết bị
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    for idx, (mac, grp) in enumerate(devices[:3]):
        safe_mac = sanitize(mac)
        timestamps = grp['timestamp_real_ms']
        re_vals = grp[[f'subcarrier_{i}_Re' for i in range(n_pairs)]].values
        im_vals = grp[[f'subcarrier_{i}_Im' for i in range(n_pairs)]].values
        amp_matrix = np.sqrt(re_vals**2 + im_vals**2)

        # Cột 1: heatmap
        ax_hm = axes[idx, 0]
        imshow_obj = ax_hm.imshow(amp_matrix.T, aspect='auto', cmap='jet', interpolation='nearest')
        ax_hm.set_title(f'{mac} - Heatmap')
        ax_hm.set_ylabel('Subcarrier Index')
        ax_hm.set_xticks([])

        # Cột 2: lineplot
        ax_ln = axes[idx, 1]
        for i in range(n_pairs):
            amp = amp_matrix[:, i]
            ax_ln.plot(timestamps, amp, lw=0.5)
        ax_ln.set_title(f'{mac} - Line Plot')
        ax_ln.set_ylabel('Amplitude')
        ax_ln.tick_params(axis='x', labelrotation=30)

    for j in range(len(devices), 3):
        axes[j, 0].axis('off')
        axes[j, 1].axis('off')

    axes[2, 0].set_xlabel('Time Index')
    axes[2, 1].set_xlabel('Thời gian')

    fig.tight_layout(rect=[0, 0, 0.95, 1])
    cbar_ax = fig.add_axes([0.96, 0.15, 0.01, 0.7])
    fig.colorbar(imshow_obj, cax=cbar_ax)

    fig_path = os.path.join(plot_folder, f'location_{location}_label_{label}_sample_{sample_id}')
    fig.savefig(fig_path)
    plt.close(fig)

print("✅ Hoàn thành tất cả bước xử lý và vẽ CSI.")
