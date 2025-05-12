import os

# Đường dẫn gốc (thư mục cha ngoài cùng)
root_dir = '.'

# Duyệt đệ quy toàn bộ thư mục con
for dirpath, dirnames, filenames in os.walk(root_dir):
    for filename in filenames:
        if filename.endswith('.csv') and not filename.startswith('luu chon'):
            old_path = os.path.join(dirpath, filename)
            new_filename = 'user2_' + filename
            new_path = os.path.join(dirpath, new_filename)
            
            os.rename(old_path, new_path)
            print(f'Đã đổi tên: {old_path} -> {new_path}')
