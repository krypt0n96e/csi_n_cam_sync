import csv
import ast
import numpy as np
import matplotlib.pyplot as plt
import pywt

# Configuration
CSV_FILE = '34_86_5D_39_A5_5C.csv'            # Path to your input CSV data
OUTPUT_CSV = 'occupancy_output.csv'  # Path to save detection results
THRESHOLD = 0.8                      # STI threshold for occupancy
PLOT_INTERVAL_MS = 20_000            # Interval to plot STI (20 seconds in ms)
WAVELET = 'sym4'                     # Symlet wavelet for DWT denoising

# Utility: parse CSI string to numpy array
# Returns None if parsing fails
def parse_csi(csi_str):
    try:
        raw = ast.literal_eval(csi_str)
        return np.array(raw, dtype=float)
    except Exception:
        return None

# DWT denoising of a 1D signal
def denoise_signal(signal, wavelet=WAVELET, level=None):
    coeffs = pywt.wavedec(signal, wavelet, level=level)
    detail_coeffs = coeffs[1]
    sigma = np.median(np.abs(detail_coeffs)) / 0.6745
    uthresh = sigma * np.sqrt(2 * np.log(len(signal)))
    denoised_coeffs = [coeffs[0]] + [pywt.threshold(c, uthresh, mode='soft') for c in coeffs[1:]]
    return pywt.waverec(denoised_coeffs, wavelet)[:len(signal)]

# Load CSI entries robustly, handling missing data
def load_entries(path):
    raw_rows = []
    with open(path, 'r', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            raw_rows.append(row)

    # Determine subcarrier length from first valid row
    n_sub = None
    for row in raw_rows:
        vec = parse_csi(row['CSI'])
        if vec is not None:
            n_sub = len(vec)
            break
    if n_sub is None:
        raise ValueError('No valid CSI data found')

    # Build arrays
    timestamps = []
    macs = []
    raw_matrix = []
    for row in raw_rows:
        macs.append(row['mac'])
        ts = float(row['timestamp_real_ms'])
        timestamps.append(ts)
        vec = parse_csi(row['CSI'])
        if vec is None:
            raw_matrix.append(np.full(n_sub, np.nan))
        else:
            raw_matrix.append(vec)

    return np.array(timestamps), np.vstack(raw_matrix), macs

# Preprocess CSI matrix: interpolate missing and DWT denoise
def preprocess_csi(timestamps, raw_matrix):
    denoised = np.zeros_like(raw_matrix)
    for i in range(raw_matrix.shape[1]):
        col = raw_matrix[:, i]
        valid_idx = ~np.isnan(col)
        if valid_idx.sum() < 2:
            denoised[:, i] = np.nan_to_num(col)
            continue
        interp = np.interp(timestamps, timestamps[valid_idx], col[valid_idx])
        denoised[:, i] = denoise_signal(interp)
    return denoised

# Normalize CSI vector: translation and scale
def normalize_csi(vec):
    mean = np.mean(vec)
    shifted = vec - mean
    sigma = np.linalg.norm(shifted)
    return shifted if sigma == 0 else shifted / sigma

# Main occupancy detection + plotting
def run():
    ts, raw_matrix, macs = load_entries(CSV_FILE)
    csi_matrix = preprocess_csi(ts, raw_matrix)

    # Prepare output CSV and write header
    with open(OUTPUT_CSV, 'w', newline='') as out_file:
        writer = csv.writer(out_file)
        writer.writerow(['mac', 'timestamp_real_ms', 'sti', 'occupancy'])

    prev_norm = None
    window_start = ts[0] if ts.size else 0
    window_times = []
    window_sti = []

    # Process samples
    with open(OUTPUT_CSV, 'a', newline='') as out_file:
        writer = csv.writer(out_file)
        for idx, current_ts in enumerate(ts):
            current_vec = csi_matrix[idx]
            current_norm = normalize_csi(current_vec)
            if prev_norm is not None:
                sti = np.linalg.norm(current_norm - prev_norm)
                occ = sti > THRESHOLD
                # Write every sample
                writer.writerow([macs[idx], current_ts, round(sti,4), occ])
                # Collect for plotting
                window_times.append((current_ts - window_start)/1000.0)
                window_sti.append(sti)
                # Plot interval reached
                if current_ts - window_start >= PLOT_INTERVAL_MS:
                    plt.figure()
                    plt.plot(window_times, window_sti)
                    plt.title(f'STI {int(window_start)}–{int(current_ts)}ms')
                    plt.xlabel('Time (s)')
                    plt.ylabel('STI')
                    fname = f'sti_{int(window_start)}_{int(current_ts)}.png'
                    plt.savefig(fname)
                    plt.close()
                    print(f'Plot saved: {fname}')
                    window_start = current_ts
                    window_times.clear()
                    window_sti.clear()
            prev_norm = current_norm

    print(f'Completed. Results in {OUTPUT_CSV}')

if __name__ == '__main__':
    run()
