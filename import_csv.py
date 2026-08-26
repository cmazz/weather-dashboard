import glob
import sqlite3
import pandas as pd

DB_FILE = "weather.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_weather (
            date TEXT PRIMARY KEY,
            temp_current REAL,
            temp_high REAL,
            temp_low REAL,
            humidity REAL,
            wind_speed REAL,
            bar_pressure REAL,
            dew_point REAL,
            rain_total REAL
        )
    """
    )
    conn.commit()
    conn.close()


def normalize_column_names(df):
    col_map = {}
    used_targets = set()

    for col in df.columns:
        c_lower = str(col).strip().lower()
        target = None

        if "date" in c_lower and "time" not in c_lower:
            target = "date"
        elif "date" in c_lower or "timestamp" in c_lower:
            if "date" not in used_targets:
                target = "date"
        elif "temp" in c_lower or "temp_out" in c_lower:
            if "hi" in c_lower or "high" in c_lower:
                target = "temp_high"
            elif "lo" in c_lower or "low" in c_lower:
                target = "temp_low"
            elif "temp_current" not in used_targets:
                target = "temp_current"
        elif "hum" in c_lower and "humidity" not in used_targets:
            target = "humidity"
        elif (
            "wind" in c_lower
            and "speed" in c_lower
            and "wind_speed" not in used_targets
        ):
            target = "wind_speed"
        elif (
            ("bar" in c_lower or "press" in c_lower)
            and "bar_pressure" not in used_targets
        ):
            target = "bar_pressure"
        elif "dew" in c_lower and "dew_point" not in used_targets:
            target = "dew_point"
        elif "rain" in c_lower and "rain_total" not in used_targets:
            target = "rain_total"

        if target and target not in used_targets:
            col_map[col] = target
            used_targets.add(target)

    renamed_df = df.rename(columns=col_map)
    # Remove duplicate columns if any were assigned
    return renamed_df.loc[:, ~renamed_df.columns.duplicated()]


def process_csv_files():
    init_db()
    csv_files = glob.glob("*.csv")

    if not csv_files:
        print("No CSV files found in this directory.")
        return

    print(f"Found {len(csv_files)} CSV files. Processing...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    total_records = 0

    for file_path in csv_files:
        print(f"Processing: {file_path}")
        try:
            with open(file_path, "r", encoding="cp1252", errors="replace") as f:
                lines = f.readlines()

            header_row_idx = 0
            for idx, line in enumerate(lines[:15]):
                line_lower = line.lower()
                if (
                    "date" in line_lower
                    or "temp" in line_lower
                    or "time" in line_lower
                ):
                    header_row_idx = int(idx)
                    break

            df = pd.read_csv(
                file_path,
                skiprows=header_row_idx,
                encoding="cp1252",
                on_bad_lines="skip",
            )
            df = normalize_column_names(df)

            if "date" not in df.columns:
                print(f"  Skipping {file_path}: No 'date' column recognized.")
                continue

            # Parse date with flexible format checking
            df["date"] = pd.to_datetime(
                df["date"], format="mixed", errors="coerce"
            ).dt.strftime("%Y-%m-%d")
            df = df.dropna(subset=["date"])

            target_cols = [
                "temp_current",
                "temp_high",
                "temp_low",
                "humidity",
                "wind_speed",
                "bar_pressure",
                "dew_point",
                "rain_total",
            ]
            for col in target_cols:
                if col not in df.columns:
                    df[col] = 0.0
                else:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(
                        0.0
                    )

            grouped = (
                df.groupby("date")
                .agg(
                    {
                        "temp_current": "mean",
                        "temp_high": "max",
                        "temp_low": "min",
                        "humidity": "mean",
                        "wind_speed": "mean",
                        "bar_pressure": "mean",
                        "dew_point": "mean",
                        "rain_total": "max",
                    }
                )
                .reset_index()
            )

            for _, row in grouped.iterrows():
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO daily_weather VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        str(row["date"]),
                        round(float(row["temp_current"]), 1),
                        round(float(row["temp_high"]), 1),
                        round(float(row["temp_low"]), 1),
                        round(float(row["humidity"]), 1),
                        round(float(row["wind_speed"]), 1),
                        round(float(row["bar_pressure"]), 2),
                        round(float(row["dew_point"]), 1),
                        round(float(row["rain_total"]), 2),
                    ),
                )
                total_records += 1

        except Exception as e:
            print(f"  Error processing {file_path}: {e}")

    conn.commit()
    conn.close()
    print(
        f"\nSuccessfully imported {total_records} daily records into weather.db!"
    )


if __name__ == "__main__":
    process_csv_files()