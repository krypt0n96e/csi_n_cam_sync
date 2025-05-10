import csv
import os
import time
import threading
import cv2

# --- Thông số mặc định ---
DEFAULT_FRAME_WIDTH  = 1280
DEFAULT_FRAME_HEIGHT = 720
DEFAULT_FPS          = 30  # target fps
VIDEO_DIR = "video"
os.makedirs(VIDEO_DIR, exist_ok=True)

# --- Quét camera khả dụng ---
def list_available_cameras(max_cams=5):
    cams = []
    for i in range(max_cams):
        cap = cv2.VideoCapture(i)
        if cap.read()[0]:
            cams.append(i)
        cap.release()
    return cams

# --- Ghi video theo timestamp-based frame indexing ---
def video_recorder(stop_event, cam_index, width, height, target_fps):
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        print(f"[Video] Không thể mở camera index {cam_index}")
        return

    # Ghi thời gian khi bắt đầu mở camera (tính theo ms)
    camera_open_time = int(time.time() * 1000)

    # Tạo file video với tên dựa trên thời gian khởi tạo
    start_ms = int(time.time() * 1000)
    video_file = os.path.join(VIDEO_DIR, f"{start_ms}.avi")
    print(f"[Video] Ghi vào: {video_file} @ {target_fps}fps")

    # Đường dẫn file CSV để ghi thời gian trễ
    csv_file = os.path.join(VIDEO_DIR, f"{start_ms}_delay.csv")
    
    # Kiểm tra nếu file CSV đã tồn tại
    file_exists = os.path.exists(csv_file)

    # Mở file CSV với chế độ append nếu file đã tồn tại, nếu chưa thì tạo mới
    with open(csv_file, 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        
        # Nếu file chưa tồn tại, ghi tiêu đề cột
        if not file_exists:
            csv_writer.writerow(['timestamp', 'delay_ms'])

        # Cấu hình camera
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        out = cv2.VideoWriter(video_file, fourcc, target_fps, (width, height))

        # Lấy thời gian thực để tính trễ giữa khởi động camera và ghi video
        t0 = time.time()  # Ghi nhận thời gian bắt đầu thực
        last_idx = 0
        last_frame = None

        # Tính toán độ trễ giữa mở camera và thời gian bắt đầu ghi video
        delay_ms = (t0 * 1000 - camera_open_time)  # Độ trễ (ms) giữa mở camera và bắt đầu ghi
        print(f"[Video] Thời gian trễ giữa mở camera và bắt đầu ghi: {delay_ms:.2f} ms")

        # Ghi thời gian trễ vào CSV
        csv_writer.writerow([camera_open_time, delay_ms])

        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                # Nếu mất khung, tiếp tục dùng khung cuối cùng
                frame = last_frame
            else:
                last_frame = frame

            # Thời gian trôi qua từ lúc bắt đầu
            elapsed = time.time() - t0
            # Tính toán khung thứ bao nhiêu cần ghi
            target_idx = int(round(elapsed * target_fps))

            # Ghi lại các khung từ last_idx đến target_idx
            for idx in range(last_idx, target_idx):
                if last_frame is None:
                    break
                out.write(last_frame)

            last_idx = target_idx

        # Khi dừng ghi, tính lại thời gian trễ
        final_elapsed = time.time() - t0
        final_delay_ms = (final_elapsed * 1000 - camera_open_time)  # Tính độ trễ cuối cùng

        # Đổi tên file video để thêm độ trễ vào tên file
        new_video_file = os.path.join(VIDEO_DIR, f"{start_ms}_delay_{int(final_delay_ms)}ms.avi")
        os.rename(video_file, new_video_file)
        print(f"[Video] Đổi tên video thành: {new_video_file}")

        # Đổi tên file CSV nếu cần
        new_csv_file = os.path.join(VIDEO_DIR, f"{start_ms}_delay_{int(final_delay_ms)}ms.csv")
        os.rename(csv_file, new_csv_file)
        print(f"[CSV] Đổi tên CSV thành: {new_csv_file}")

        cap.release()
        out.release()
        print("[Video] Hoàn thành ghi.")

# --- Hàm nhập với mặc định ---
def input_with_default(prompt, default, cast):
    s = input(f"{prompt} [{default}]: ").strip()
    try:
        return cast(s) if s else default
    except:
        print(f"[Input] Không hợp lệ, dùng {default}")
        return default

# --- Main ---
def main():
    print("[Main] Tìm camera khả dụng…")
    cams = list_available_cameras()
    if not cams:
        print("[Main] Không tìm thấy camera nào.")
        return

    print(f"[Main] Các camera tìm thấy: {cams}")
    sel = input("Chọn camera index: ")
    try:
        cam_idx = int(sel)
        if cam_idx not in cams:
            raise ValueError
    except:
        print("[Main] Lựa chọn không hợp lệ.")
        return

    print("[Main] Nhập thông số video:")
    w   = input_with_default("Chiều rộng",  DEFAULT_FRAME_WIDTH,  int)
    h   = input_with_default("Chiều cao",   DEFAULT_FRAME_HEIGHT, int)
    fps = input_with_default("FPS (target)", DEFAULT_FPS,         float)

    print(f"[Main] Ghi {w}x{h} @ {fps}fps — Ctrl+C để dừng.")
    stop = threading.Event()
    th = threading.Thread(
        target=video_recorder,
        args=(stop, cam_idx, w, h, fps),
        daemon=True
    )
    th.start()

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop.set()
        th.join()
        print("[Main] Đã ngừng.")

if __name__ == "__main__":
    main()
