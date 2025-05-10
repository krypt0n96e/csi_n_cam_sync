import pandas as pd

def interpolate_csi(input_csv='csi_data_20250508_141303_fix_duplicate.csv', output_csv='output.csv'):
    # Read input CSV
    df = pd.read_csv(input_csv)

    # Convert timestamp_real_ms to integer
    df['timestamp_real_ms'] = df['timestamp_real_ms'].astype(int)

    # Determine global time range at 100 Hz (every 10 ms)
    t_min = df['timestamp_real_ms'].min()
    t_max = df['timestamp_real_ms'].max()
    full_times = pd.DataFrame({'timestamp_real_ms': range(t_min, t_max + 1, 10)})

    # Expand CSI list string to separate columns efficiently
    csi_expanded = df['CSI'].str.strip('[]').str.split(',', expand=True).astype(int)
    N = csi_expanded.shape[1]
    col_names = [f'CSI_{i}' for i in range(N)]
    csi_expanded.columns = col_names
    df = pd.concat([df.drop(columns=['CSI']), csi_expanded], axis=1)

    # Perform interpolation per device MAC
    rows = []
    for mac, group in df.groupby('mac'):
        g = group.set_index('timestamp_real_ms')[col_names]
        g_interp = g.reindex(full_times['timestamp_real_ms']).interpolate(method='linear', limit_direction='both')
        # For each interpolated row, reconstruct CSI string
        for t, vals in g_interp.iterrows():
            csi_list = vals.round().astype(int).tolist()
            csi_str = '[' + ','.join(str(v) for v in csi_list) + ']'
            rows.append({
                'mac': mac,
                'timestamp_real_ms': t,
                'timestamp_pc_ms': '',
                'timestamp_pc_hms': '',
                'CSI': csi_str
            })

    # Create result DataFrame with original header order
    result = pd.DataFrame(rows, columns=['mac', 'timestamp_real_ms', 'timestamp_pc_ms', 'timestamp_pc_hms', 'CSI'])

    # Save output, preserving header
    result.to_csv(output_csv, index=False)

if __name__ == '__main__':
    interpolate_csi()  # reads 'input_csv.csv', writes 'output.csv'
