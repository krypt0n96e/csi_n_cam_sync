import csv
from collections import defaultdict
import copy


# Tên file
input_file = 'csi_data_20250508_141303.csv'
output_file = 'csi_data_20250508_141303_fix_duplicate.csv'
duplicate_file = 'csi_data_20250508_141303_duplicate_rows.csv'


# Đọc dữ liệu
with open(input_file, 'r', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = next(reader)
    rows = list(reader)

# Lưu các dòng trùng từng xuất hiện
all_duplicates = []

# Lặp cho đến khi không còn trùng
changed = True
while changed:
    grouped = defaultdict(list)
    for row in rows:
        key = (row[0], row[1])
        grouped[key].append(row)

    changed = False
    new_rows = []

    for key, group in grouped.items():
        if len(group) == 1:
            new_rows.append(group[0])
        else:
            changed = True
            all_duplicates.extend(group)

            # Trừ timestamp_real_ms của dòng đầu tiên đi 1
            first = copy.deepcopy(group[0])
            first[1] = str(int(first[1]) - 1)
            new_rows.append(first)

            # Các dòng còn lại giữ nguyên
            new_rows.extend(group[1:])

    rows = new_rows  # cập nhật cho vòng lặp kế tiếp

# Ghi file kết quả cuối cùng
with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(rows)

# Ghi lại tất cả các dòng đã từng bị trùng
with open(duplicate_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(header)
    writer.writerows(all_duplicates)

print(f"✅ Đã xử lý xong.")
print(f"📄 Kết quả sau xử lý lưu tại: {output_file}")
print(f"📄 Tất cả các dòng từng bị trùng lưu tại: {duplicate_file}")
