#!/usr/bin/env python

import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime

def merge_and_sort_gps_csv(files):
    if not files:
        print("Error: No input files provided.", file=sys.stderr)
        sys.exit(1)

    EXPECTED_HEADER = [
        "type", "date time", "latitude", "longitude", "accuracy(m)",
        "altitude(m)", "geoid_height(m)", "speed(m/s)", "bearing(deg)",
        "sat_used", "sat_inview", "name", "desc"
    ]

    # Two possible formats
    DATE_FORMATS = [
        "%Y-%m-%d %H:%M:%S.%f",  # with milliseconds
        "%Y-%m-%d %H:%M:%S"      # without milliseconds
    ]

    all_rows = []
    first_file = True

    for file_path in files:
        path = Path(file_path)
        if not path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)

        with path.open(newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)

            if header is None:
                print(f"Warning: Empty file skipped: {file_path}", file=sys.stderr)
                continue

            header = [h.strip() for h in header]

            if first_file:
                if header != EXPECTED_HEADER:
                    print(f"Error: Unexpected header in {file_path}", file=sys.stderr)
                    print(f"Expected: {', '.join(EXPECTED_HEADER)}", file=sys.stderr)
                    print(f"Got:      {', '.join(header)}", file=sys.stderr)
                    sys.exit(1)
                first_file = False
            else:
                if header != EXPECTED_HEADER:
                    print(f"Warning: Skipping {file_path} due to mismatched header", file=sys.stderr)
                    continue

            for row_num, row in enumerate(reader, start=2):
                if len(row) != len(EXPECTED_HEADER):
                    print(f"Warning: Skipping malformed row in {file_path} (line {row_num})", file=sys.stderr)
                    continue

                cleaned_row = [field.strip() if field else '' for field in row]
                date_str = cleaned_row[1].strip()

                # Try parsing with both formats
                dt = None
                for fmt in DATE_FORMATS:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue

                if dt is None:
                    print(f"Warning: Unparseable date in {file_path} (line {row_num}): '{date_str}'", file=sys.stderr)
                    # Place unparseable dates at the end
                    dt = datetime.max

                all_rows.append((dt, cleaned_row))

    if not all_rows:
        print("Error: No valid data rows found in input files.", file=sys.stderr)
        sys.exit(1)

    # Sort by datetime (earliest first)
    all_rows.sort(key=lambda x: x[0])

    # Extract cleaned rows
    sorted_rows = [row for _, row in all_rows]

    # Output to stdout
    writer = csv.writer(sys.stdout)
    writer.writerow(EXPECTED_HEADER)
    writer.writerows(sorted_rows)

def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple GPS CSV/TXT files and sort by date time (handles formats with/without milliseconds)."
    )
    parser.add_argument(
        "files",
        nargs='+',
        help="One or more input CSV/TXT files to merge"
    )
    args = parser.parse_args()

    merge_and_sort_gps_csv(args.files)

if __name__ == "__main__":
    main()
