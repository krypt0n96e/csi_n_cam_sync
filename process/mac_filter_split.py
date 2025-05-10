import pandas as pd
import os
import re

def sanitize(name: str) -> str:
    # Loại bỏ ký tự không hợp lệ để dùng trong tên file
    return re.sub(r'[^A-Za-z0-9\-_\.]', '_', name)

# Đọc dữ liệu
data_df = pd.read_csv('csi_data_20250508_141303_fix_duplicate.csv')  # cột: mac, timestamp_local_us, data...


# Tạo thư mục đầu ra (tùy ý)
output_dir = 'output_by_mac'
os.makedirs(output_dir, exist_ok=True)

# Tách và lưu từng file theo mac
for mac, group in data_df.groupby('mac'):
    safe_mac = sanitize(mac)
    filename = os.path.join(output_dir, f'{safe_mac}.csv')
    group.to_csv(filename, index=False)

print("✅ Đã tách dữ liệu thành các file theo MAC.")