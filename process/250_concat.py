import os
import pandas as pd

def keep_center_250_rows(input_path):
    df = pd.read_csv(input_path)
    total_rows = len(df)

    if total_rows <= 250:
        return df
    else:
        start = (total_rows - 250) // 2
        end = start + 250
        return df.iloc[start:end]

def process_all_csv_in_folder(source_root, dest_root):
    for subdir, _, files in os.walk(source_root):
        for file in files:
            if file.endswith(".csv"):
                source_file_path = os.path.join(subdir, file)

                # Tạo đường dẫn lưu mới tương ứng trong thư mục dest_root
                relative_path = os.path.relpath(source_file_path, source_root)
                dest_file_path = os.path.join(dest_root, relative_path)

                # Tạo thư mục đích nếu chưa tồn tại
                os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)

                try:
                    trimmed_df = keep_center_250_rows(source_file_path)
                    trimmed_df.to_csv(dest_file_path, index=False)
                    print(f"Đã lưu: {dest_file_path}")
                except Exception as e:
                    print(f"Lỗi xử lý {source_file_path}: {e}")

# Gọi hàm với thư mục gốc "2" và thư mục đích "2_concat"
process_all_csv_in_folder("2", "2_concat")
