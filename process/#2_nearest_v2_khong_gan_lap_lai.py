import pandas as pd
import numpy as np

# Đọc dữ liệu
df = pd.read_csv('csi_data_20250508_141303.csv')
df = df.sort_values(['mac', 'timestamp_real_ms']).reset_index(drop=True)

# Tạo lưới thời gian 100Hz
start_time = df['timestamp_real_ms'].min()
end_time = df['timestamp_real_ms'].max()
grid_timestamps = np.arange(start_time, end_time + 1, 10)

# Kết quả đầu ra
result_rows = []

# Xử lý theo từng MAC
for mac, group in df.groupby('mac'):
    group = group.sort_values('timestamp_real_ms').reset_index(drop=True)
    source_times = group['timestamp_real_ms'].values
    used_index = set()  # Ghi lại các chỉ số đã dùng

    idx = 0  # Chỉ số trong group

    for t in grid_timestamps:
        # Tìm chỉ số đầu tiên mà timestamp >= t
        while idx < len(group) and group.loc[idx, 'timestamp_real_ms'] < t:
            idx += 1
        if idx >= len(group):
            break

        # Nếu dòng đã dùng rồi, xét dòng tiếp theo
        chosen_idx = idx
        if chosen_idx in used_index:
            next_idx = chosen_idx + 1
            if next_idx < len(group):
                next_ts = group.loc[next_idx, 'timestamp_real_ms']
                if next_ts - t > 20:
                    chosen_idx = idx  # dùng lại dòng trước
                else:
                    chosen_idx = next_idx
            else:
                continue  # Không còn dòng nào

        if chosen_idx >= len(group):
            continue

        if chosen_idx not in used_index:
            row = group.loc[chosen_idx].copy()
            if row['timestamp_real_ms'] >= t:
                row['timestamp_real_ms'] = t
                result_rows.append(row)
                used_index.add(chosen_idx)

# Ghi kết quả
output_df = pd.DataFrame(result_rows)
output_df.to_csv('csi_data_20250508_141303_snapped_with_logic.csv', index=False)
