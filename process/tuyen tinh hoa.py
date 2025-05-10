import pandas as pd
import numpy as np
from datetime import datetime

# === Đọc file CSV ===
input_file = 'csi_data_20250508_101047.csv'
output_file = 'csi_data_20250508_101047_interpolated.csv'

df = pd.read_csv(input_file)

# === Chuyển CSI từ string sang list[int] ===
df['CSI'] = df['CSI'].apply(lambda x: list(map(int, x.strip('[]').split(','))))

# === Bỏ trùng timestamp_real_ms trong từng MAC (giữ dòng đầu tiên) ===
df = df.drop_duplicates(subset=['mac', 'timestamp_real_ms'], keep='first')

# === Lấy danh sách MAC ===
mac_list = df['mac'].unique()

# === Tạo index mac + timestamp_real_ms ===
df = df.set_index(['mac', 'timestamp_real_ms']).sort_index()

# === Tạo dải timestamp đầy đủ (bước 10ms) ===
min_ts = df.index.get_level_values('timestamp_real_ms').min()
max_ts = df.index.get_level_values('timestamp_real_ms').max()
full_ts = np.arange(min_ts, max_ts + 1, 10)

# === Lưu kết quả ===
output_rows = []

for mac in mac_list:
    mac_df = df.loc[mac]
    mac_df = mac_df.reindex(full_ts)
    
    # Lấy CSI dạng array object
    csi_array = np.array(mac_df['CSI'].tolist(), dtype=object)
    csi_interp = []
    
    # Xác định độ dài CSI
    csi_valid = [x for x in csi_array if isinstance(x, list)]
    csi_length = len(csi_valid[0]) if csi_valid else 0
    
    # Nội suy từng phần tử CSI
    for i in range(csi_length):
        csi_column = [x[i] if isinstance(x, list) else np.nan for x in csi_array]
        series = pd.Series(csi_column, index=mac_df.index)
        series_interp = series.interpolate().fillna(method='bfill').fillna(method='ffill')
        csi_interp.append(series_interp.values)
    
    # Chuyển CSI nội suy về list
    csi_interp = np.array(csi_interp).T.tolist()
    
    # Tạo timestamp_pc_ms, timestamp_pc_hms
    base_pc_ms = mac_df['timestamp_pc_ms'].dropna().iloc[0]
    pc_delta = full_ts - min_ts
    timestamp_pc_ms = base_pc_ms + pc_delta
    timestamp_pc_hms = [datetime.fromtimestamp(t/1000).strftime('%H:%M:%S.%f')[:-3] for t in timestamp_pc_ms]
    
    # Ghi vào output
    for ts_real, ts_pc, ts_hms, csi in zip(full_ts, timestamp_pc_ms, timestamp_pc_hms, csi_interp):
        row = {
            'mac': mac,
            'timestamp_real_ms': int(ts_real),
            'timestamp_pc_ms': int(ts_pc),
            'timestamp_pc_hms': ts_hms,
            'CSI': str([int(round(x)) for x in csi])
        }
        output_rows.append(row)

# === Tạo DataFrame kết quả ===
output_df = pd.DataFrame(output_rows)

# === Đảm bảo đúng thứ tự cột ===
output_df = output_df[['mac', 'timestamp_real_ms', 'timestamp_pc_ms', 'timestamp_pc_hms', 'CSI']]

# === Sắp xếp lại để mỗi timestamp có đủ 3 MAC ===
output_df = output_df.sort_values(['timestamp_real_ms', 'mac'])

# === Ghi ra file CSV ===
output_df.to_csv(output_file, index=False)

print(f'Done! Output saved to {output_file}')
