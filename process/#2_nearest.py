import pandas as pd
import numpy as np

# Đọc dữ liệu gốc
df = pd.read_csv('csi_data_20250508_141303_fix_duplicate.csv')
df = df.sort_values(['mac', 'timestamp_real_ms']).reset_index(drop=True)

# Tạo lưới thời gian 100 Hz
start_time = df['timestamp_real_ms'].min()
end_time = df['timestamp_real_ms'].max()
grid_timestamps = np.arange(start_time, end_time + 1, 10)

# Danh sách kết quả
result_rows = []

# Xử lý theo từng MAC
for mac, group in df.groupby('mac'):
    group = group.sort_values('timestamp_real_ms').reset_index(drop=True)
    source_times = group['timestamp_real_ms'].values

    # Tìm chỉ số dòng có timestamp >= t (gần nhất về phía sau)
    indices = np.searchsorted(source_times, grid_timestamps, side='left')

    for i, t in enumerate(grid_timestamps):
        idx = indices[i]
        if idx < len(group):
            row = group.iloc[idx].copy()
            if row['timestamp_real_ms'] >= t:
                row['timestamp_real_ms'] = t  # Gán lại timestamp theo lưới
                result_rows.append(row)

# Tạo DataFrame và xuất
output_df = pd.DataFrame(result_rows)
output_df.to_csv('csi_data_20250508_141303_snapped_forward.csv', index=False)
