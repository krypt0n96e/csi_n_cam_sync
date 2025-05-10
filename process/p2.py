import os
import csv, ast
import numpy as np
import matplotlib.pyplot as plt

# Hàm lọc subcarriers đã cho
def filter_csi_raw(raw_list, null_subcarriers=None):
    sub_ids = list(range(0, 32)) + list(range(-32, 0))
    if null_subcarriers is None:
        null_subcarriers = [-32, -31, -30, -29, -28, -27, 0,
                             27, 28, 29, 30, 31]
    remove_set = set(null_subcarriers)
    filtered = []
    for idx, sc in enumerate(sub_ids):
        if sc in remove_set:
            continue
        filtered.extend([raw_list[2*idx], raw_list[2*idx + 1]])
    return filtered

# Đường dẫn gốc input và output
input_root = "process/old"
output_root = "output"

for root, dirs, files in os.walk(input_root):
    for filename in files:
        if not filename.endswith(".csv"):
            continue
        input_path = os.path.join(root, filename)
        # Tạo thư mục output tương ứng
        rel_dir = os.path.relpath(root, input_root)
        output_dir = os.path.join(output_root, rel_dir)
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename[:-4] + ".png")

        # Đọc CSV và nhóm dữ liệu theo MAC
        data_by_mac = {}
        with open(input_path, 'r') as f:
            reader = csv.reader(f)
            headers = next(reader)  # nếu có header, hãy sửa nếu không có
            for row in reader:
                mac = row[0]
                timestamp = int(row[1])
                # row[3] là chuỗi CSI dưới dạng "[re0,im0,re1,im1,...]"
                raw_list = ast.literal_eval(row[3])
                # Lọc subcarriers null
                filtered = filter_csi_raw(raw_list)
                # Tính biên độ 52 kênh
                arr = np.array(filtered).reshape(-1, 2)
                re = arr[:, 0]; im = arr[:, 1]
                amplitude = np.sqrt(re**2 + im**2)
                # Nhóm theo MAC
                data_by_mac.setdefault(mac, []).append((timestamp, amplitude))

        # Vẽ biểu đồ 1x3 cho tối đa 3 MAC
        macs = list(data_by_mac.keys())
        fig, axes = plt.subplots(1, 3, figsize=(12, 4))
        for i in range(3):
            ax = axes[i]
            if i < len(macs):
                mac = macs[i]
                # Sắp xếp theo thời gian
                data = sorted(data_by_mac[mac], key=lambda x: x[0])
                times = [t for (t, _) in data]
                amps = [amp for (_, amp) in data]
                # Vẽ từng subcarrier
                for ch in range(52):
                    ax.plot(times, [row[ch] for row in amps])
                ax.set_title(mac)
                ax.set_xlabel("timestamp_local_us")
                ax.set_ylabel("Amplitude")
            else:
                # Ẩn trục nếu không có dữ liệu
                ax.axis('off')

        plt.tight_layout()
        plt.savefig(output_path)
        plt.close(fig)
