import os

# Đường dẫn gốc (thư mục cha ngoài cùng)
root_dir = '.'

# Duyệt đệ quy toàn bộ thư mục con
for dirpath, dirnames, filenames in os.walk(root_dir):
    for filename in filenames:
        if filename.endswith('.csv') and filename.startswith('user1_'):
            old_path = os.path.join(dirpath, filename)
            # Cắt bỏ 'luu chon' ở đầu tên file
            new_filename = filename[len('user1_'):]
            new_path = os.path.join(dirpath, new_filename)
            
            os.rename(old_path, new_path)
            print(f'Đã hoàn tác: {old_path} -> {new_path}')
