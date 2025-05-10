import csv
import ast
import numpy as np
import matplotlib.pyplot as plt

# Configuration
CSV_FILE = 'A0_DD_6C_0F_99_C8.csv'      # Path to your input CSV data
OUTPUT_CSV = 'occupancy_output.csv'  # Path to save detection results
THRESHOLD = 0.8                # STI threshold for occupancy
PLOT_INTERVAL_MS = 10_000      # Interval to plot STI (20 seconds in ms)

# Utility: parse CSI string to numpy array
def parse_csi(csi_str):
    try:
        raw = ast.literal_eval(csi_str)
        return np.array(raw, dtype=float)
    except (ValueError, SyntaxError) as e:
        print(f'Failed to parse CSI: {e}')
        return None

# Utility: compute normalized (translated + scaled) CSI vector
def normalize_csi(vec):
    mean = np.mean(vec)
    shifted = vec - mean
    sigma = np.linalg.norm(shifted)
    return shifted if sigma == 0 else shifted / sigma

# Load all CSI entries from CSV into memory (fast batch processing)
def load_entries(path):
    entries = []
    with open(path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            csi_vec = parse_csi(row['CSI'])
            if csi_vec is not None:
                entries.append({
                    'mac': row['mac'],
                    'timestamp': float(row['timestamp_real_ms']),
                    'csi': csi_vec
                })
    return entries

# Main occupancy detection and periodic plotting
def run():
    entries = load_entries(CSV_FILE)
    prev_norm = None

    # Prepare output CSV
    with open(OUTPUT_CSV, 'w', newline='') as out_file:
        writer = csv.writer(out_file)
        writer.writerow(['mac', 'timestamp_real_ms', 'sti', 'occupancy'])

    # Initialize plotting window
    window_start_ts = entries[0]['timestamp'] if entries else 0
    window_timestamps = []
    window_sti = []



    # Process entries
    for entry in entries:
        current_norm = normalize_csi(entry['csi'])
        if prev_norm is not None:
            sti = np.linalg.norm(current_norm - prev_norm)
            # Record occupancy detections
            if sti > THRESHOLD:
                with open(OUTPUT_CSV, 'a', newline='') as out_file:
                    writer = csv.writer(out_file)
                    writer.writerow([
                        entry['mac'],
                        entry['timestamp'],
                        round(float(sti), 4),
                        True
                    ])
            else:
                with open(OUTPUT_CSV, 'a', newline='') as out_file:
                    writer = csv.writer(out_file)
                    writer.writerow([
                        entry['mac'],
                        entry['timestamp'],
                        round(float(sti), 4),
                        False
                    ])
            # Append to current window
            window_timestamps.append(entry['timestamp'])
            window_sti.append(float(sti))

            # Check if it's time to plot
            if entry['timestamp'] - window_start_ts >= PLOT_INTERVAL_MS:
                # Plot STI over the last interval
                plt.figure(figsize=(14, 7))
                plt.grid(True)
                # convert ms to seconds relative to window
                times_sec = [(ts - window_start_ts) / 1000.0 for ts in window_timestamps]
                plt.plot(times_sec, window_sti)
                plt.title(f'STI from {window_start_ts}ms to {entry["timestamp"]}ms')
                plt.xlabel('Time (s)')
                plt.ylabel('STI')
                fname = f'sti_{int(window_start_ts)}_{int(entry["timestamp"])}.png'
                plt.savefig(fname)
                plt.close()
                # print(f'Plot saved: {fname}')

                # Reset window
                window_start_ts = entry['timestamp']
                window_timestamps.clear()
                window_sti.clear()
            Check if it's time to plot

            
            
        prev_norm = current_norm

    print(f'Processing complete: results saved to {OUTPUT_CSV}')

if __name__ == '__main__':
    run()
