import serial
import serial.tools.list_ports
import struct
import csv
import time
from collections import defaultdict
from datetime import datetime

# WHITELIST MACs
WHITELIST_MACS = {
    # b'\x3C\x8A\x1F\xA8\x0C\x1C',
    # b'\x3C\x8A\x1F\xA7\xDC\x84',
    # b'\xA0\xB7\x65\x20\xE1\xCC',
    b'\x34\x86\x5D\x39\xA5\x5C',
    # b'\xA0\xDD\x6C\x02\xE9\x48',
    # b'\xA0\xDD\x6C\x0F\x99\xC8',
    # b'\xA0\xDD\x6C\x86\x04\xE4',
    # b'\xA0\xDD\x6C\x0F\xFA\x5C',
    # b'\xA0\xDD\x6C\x85\xF7\x44',
    b'\xA0\xA3\xB3\x2F\x49\xC4',
    b'\x44\x17\x93\x7C\x43\xB0',
}

# CSV_HEADER = ["mac", "timestamp_local_us", "timestamp_real_ms", "timestamp_pc_ms", "timestamp_pc_hms", "CSI"]
CSV_HEADER = ["mac", "timestamp_real_ms", "timestamp_pc_ms", "timestamp_pc_hms", "CSI"]
FPS_CSV_HEADER = ["timestamp_pc_hms", "mac", "fps"]

FRAME_START_BYTE = 0xA5
MAX_PAYLOAD_LEN = 512

def list_serial_ports():
    return serial.tools.list_ports.comports()

def choose_port():
    ports = list_serial_ports()
    if not ports:
        print("⚠️ Không tìm thấy cổng COM nào.")
        exit(1)
    print("🔌 Danh sách COM khả dụng:")
    for idx, p in enumerate(ports):
        desc = p.description or ""
        hwid = p.hwid or ""
        extra = f"({desc} | {hwid})" if desc or hwid else ""
        print(f"  [{idx}] {p.device} {extra}")
    i = int(input("Chọn COM theo số: "))
    return ports[i].device

def choose_baud():
    common_bauds = [9600, 57600, 115200, 230400, 460800, 921600]
    print("⚙️ Chọn baudrate:")
    for i, b in enumerate(common_bauds):
        print(f"  [{i}] {b}")
    idx = int(input("Chọn baudrate theo số: "))
    return common_bauds[idx]

def open_serial(port: str, baud: int) -> serial.Serial:
    return serial.Serial(port, baudrate=baud, timeout=0.1)

def read_event(ser: serial.Serial):
    start = ser.read(1)
    if not start:
        return None
    b0 = start[0]
    if b0 != FRAME_START_BYTE:
        rest = ser.readline()
        try:
            line = start + rest
            text = line.decode('utf-8', errors='replace').rstrip()
        except:
            text = repr(start + rest)
        print(f"[UART LOG] {text}")
        return None

    length_bytes = ser.read(2)
    if len(length_bytes) < 2:
        return None
    payload_len = struct.unpack('<H', length_bytes)[0]
    # if payload_len < 24 or payload_len > MAX_PAYLOAD_LEN:
    if payload_len < 16 or payload_len > MAX_PAYLOAD_LEN:
        print(f"[❌] Invalid payload length: {payload_len}")
        ser.read(payload_len + 1)
        return None

    payload = ser.read(payload_len)
    if len(payload) < payload_len:
        return None
    checksum_b = ser.read(1)
    if len(checksum_b) < 1:
        return None
    recv_crc = checksum_b[0]
    calc_crc = 0
    for x in payload:
        calc_crc ^= x
    if calc_crc != recv_crc:
        print(f"[❌] Checksum mismatch: calc=0x{calc_crc:02X} recv=0x{recv_crc:02X}")
        return None

    try:
        # mac_bytes, ts_local_us, ts_real_ms, length_field = struct.unpack('<6sQQH', payload[:24])
        mac_bytes, ts_real_ms, length_field = struct.unpack('<6sQH', payload[:16])
    except struct.error as e:
        print(f"[❌] Header unpack error: {e}")
        return None
    # csi_raw = payload[24:24+length_field]
    csi_raw = payload[16:16+length_field]
    if len(csi_raw) < length_field:
        return None
    try:
        csi_list = list(struct.unpack(f'<{length_field}b', csi_raw))
    except struct.error as e:
        print(f"[❌] CSI unpack error: {e}")
        return None

    # return mac_bytes, ts_local_us, ts_real_ms, csi_list
    return mac_bytes, ts_real_ms, csi_list

def mac_to_str(mac_bytes: bytes) -> str:
    return ':'.join(f'{b:02X}' for b in mac_bytes)

def main():
    port = choose_port()
    baud = choose_baud()
    ser = open_serial(port, baud)
    now_str = datetime.now().strftime("%Y%m%d_%H%M%S")


    with open(f'csi_data_{now_str}.csv', 'w', newline='') as csvfile, open('fps_log.csv', 'w', newline='') as fpsfile:
        writer = csv.writer(csvfile)
        writer.writerow(CSV_HEADER)

        fps_writer = csv.writer(fpsfile)
        fps_writer.writerow(FPS_CSV_HEADER)

        packet_count = defaultdict(int)
        last_report = time.time()

        print(f"🟢 Bắt đầu ghi CSI từ {port} @ {baud}... Nhấn Ctrl+C để dừng.")
        try:
            while True:
                evt = read_event(ser)
                if evt:
                    timestamp_pc = time.time()
                    timestamp_pc_ms = int(timestamp_pc * 1000)
                    timestamp_pc_hms = datetime.fromtimestamp(timestamp_pc).strftime("%H:%M:%S.%f")[:-3]

                    # mac_bytes, ts_local_us, ts_real_ms, csi = evt
                    mac_bytes, ts_real_ms, csi = evt
                    if mac_bytes in WHITELIST_MACS:
                        mac_str = mac_to_str(mac_bytes)
                        # writer.writerow([mac_str, ts_local_us, ts_real_ms, timestamp_pc_ms, timestamp_pc_hms, csi])
                        writer.writerow([mac_str, ts_real_ms, timestamp_pc_ms, timestamp_pc_hms, csi])
                        packet_count[mac_str] += 1
                    else:
                        print(f"[⚠️] MAC không nằm trong whitelist: {mac_to_str(mac_bytes)}")

                now = time.time()
                if now - last_report >= 1.0:
                    if packet_count:
                        print("📶 Tần số (gói/s) mỗi MAC:")
                        timestamp_hms = datetime.now().strftime("%H:%M:%S")
                        for m, cnt in packet_count.items():
                            print(f"  {m}: {cnt:.2f} Hz")
                            fps_writer.writerow([timestamp_hms, m, cnt])
                    packet_count.clear()
                    last_report = now
        except KeyboardInterrupt:
            print("\n🛑 Dừng ghi.")
        finally:
            ser.close()

if __name__ == '__main__':
    main()
