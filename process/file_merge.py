import csv

def merge_csv_files(output_file, input_files):
    with open(output_file, 'w', newline='', encoding='utf-8') as out_csv:
        writer = None

        for idx, file in enumerate(input_files):
            with open(file, 'r', newline='', encoding='utf-8') as in_csv:
                reader = csv.reader(in_csv)
                header = next(reader)

                if writer is None:
                    writer = csv.writer(out_csv)
                    writer.writerow(header)  # ghi header một lần

                for row in reader:
                    writer.writerow(row)

    print(f"Đã ghép xong các file vào: {output_file}")

# Ví dụ sử dụng:
merge_csv_files('merged.csv', ['part1.csv', 'part2.csv'])
