import pandas as pd
import os
import re

def sanitize(name: str) -> str:
    # Thay tất cả ký tự không phải chữ, số, dấu gạch ngang hoặc gạch dưới thành gạch dưới
    return re.sub(r'[^A-Za-z0-9\-_\.]', '_', name)

# Đọc dữ liệu
data_df = pd.read_csv('merged.csv')  # cột: mac, timestamp_local_us, data...
timestamp_df = pd.read_csv('timestamps.csv')  # cột: start_utc_ms, end_utc_ms, location, label

# Chuyển timestamp từ milliseconds sang datetime
data_df['timestamp_local_us'] = pd.to_datetime(data_df['timestamp_local_us'], unit='ms')
timestamp_df['start_utc_ms']   = pd.to_datetime(timestamp_df['start_utc_ms'], unit='ms')
timestamp_df['end_utc_ms']     = pd.to_datetime(timestamp_df['end_utc_ms'], unit='ms')

# Đếm sample theo từng cặp (label, location)
sample_counters = {}

for _, row in timestamp_df.iterrows():
    start    = row['start_utc_ms']
    end      = row['end_utc_ms']
    location = str(row['location'])
    label    = str(row['label'])

    # Xác định sample số mấy cho cặp (label, location)
    sample_id = sample_counters.get((label, location), 1)
    sample_counters[(label, location)] = sample_id + 1

    # Tạo đường dẫn thư mục
    sample_folder = os.path.join(sanitize(label), sanitize(location), f'sample{sample_id}')
    os.makedirs(sample_folder, exist_ok=True)

    # Lọc dữ liệu theo khoảng thời gian
    mask = (data_df['timestamp_local_us'] >= start) & (data_df['timestamp_local_us'] <= end)
    sliced_df = data_df[mask]

    # Tách theo thiết bị (mac) và lưu ra file
    for mac, group in sliced_df.groupby('mac'):
        safe_mac = sanitize(mac)
        filename = os.path.join(sample_folder, f'{safe_mac}.csv')
        group.to_csv(filename, index=False)

print("✅ Đã tách và lưu dữ liệu theo cấu trúc thư mục yêu cầu.")
