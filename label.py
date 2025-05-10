import csv
import time
import os

FILENAME = 'timestamps.csv'
FIELDNAMES = ['start_utc_ms', 'end_utc_ms', 'label', 'location']

# Initialize CSV file with header if not exists
def init_csv():
    file_exists = os.path.isfile(FILENAME)
    if not file_exists:
        with open(FILENAME, mode='w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            writer.writeheader()

# Wait for 'h' key press
def wait_for_h(prompt_msg=None):
    if prompt_msg:
        print(prompt_msg)
    try:
        import keyboard  # pip install keyboard
    except ImportError:
        print("Thiếu thư viện 'keyboard'. Vui lòng cài đặt: pip install keyboard")
        exit(1)
    # Block until 'h' is pressed
    keyboard.wait('h')

# Get current UTC timestamp in milliseconds
def get_utc_ms():
    return int(time.time() * 1000)


def main():
    print("Chương trình ghi lại timestamp UTC (ms) với nhãn và vị trí. Nhấn 'h' để bắt đầu.")
    init_csv()
    while True:
        # Nhập vị trí
        location = input("Nhập location cho lần ghi này và nhấn Enter: ")

        # Bắt đầu
        wait_for_h("Nhấn 'h' để ghi start timestamp...")
        start_ts = get_utc_ms()
        print(f"Start timestamp: {start_ts}")

        # Kết thúc
        wait_for_h("Nhấn 'h' lần nữa để ghi end timestamp...")
        end_ts = get_utc_ms()
        print(f"End timestamp: {end_ts}")

        # Chọn nhãn
        label = None
        while label not in map(str, range(8)):
            label = input("Chọn nhãn (0-7) và nhấn Enter: ")
        print(f"Bạn đã chọn nhãn: {label}")

        # Ghi vào CSV
        with open(FILENAME, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            writer.writerow({
                'start_utc_ms': start_ts,
                'end_utc_ms': end_ts,
                'label': label,
                'location': location
            })
        print(f"Đã ghi vào {FILENAME}\n")


if __name__ == '__main__':
    main()
