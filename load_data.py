# backend-python/load_data.py
import os
import pandas as pd
import psycopg2
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# --- Database Connection Details ---
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_DATABASE = os.getenv('DB_DATABASE')

# --- Path to your CSV file ---
CSV_FILE_PATH = 'cleaned_crime_dataset.csv' # Ensure this file is in the same directory as this script

def load_csv_to_db():
    conn = None
    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_DATABASE
        )
        cur = conn.cursor()
        print("Successfully connected to PostgreSQL database for data loading.")

        # --- Read CSV into DataFrame ---
        df = pd.read_csv(CSV_FILE_PATH)
        print(f"CSV file '{CSV_FILE_PATH}' loaded successfully. Shape: {df.shape}")

        # IMPORTANT: Clean column names by stripping whitespace from all headers
        df.columns = df.columns.str.strip()
        print("Columns read from CSV (after stripping whitespace):", df.columns.tolist())

        # --- Data Preprocessing and Type Conversion for DB Insertion ---

        # 1. Convert 'Date of Occurrence' to datetime objects and then to string for PostgreSQL TIMESTAMP
        # CORRECTED: Use "%d-%m-%Y %H:%M" format string for DD-MM-YYYY HH:MM
        print("Attempting to convert 'Date of Occurrence' column...")
        df['date_of_occurrence_dt'] = pd.to_datetime(df['Date of Occurrence'], format="%d-%m-%Y %H:%M")
        df['date_of_occurrence'] = df['date_of_occurrence_dt'].dt.strftime('%Y-%m-%d %H:%M:%S')
        print("'Date of Occurrence' converted.")

        # 2. Handle 'Weapon Used' missing values - fill NaN with 'None' string
        print("Handling 'Weapon Used' missing values...")
        df['Weapon Used'] = df['Weapon Used'].fillna('None')
        print("'Weapon Used' handled.")

        # 3. Create integer mappings for categorical columns
        print("Creating integer mappings for categorical columns...")
        # Note: If any category in the CSV is not in the map (e.g., new unique value), map() will produce NaN.
        # .astype(int) will then raise an error. Consider handling NaNs or unmapped values.
        city_to_code_map = {val: i for i, val in enumerate(df['City'].unique())}
        crime_type_to_code_map = {val: i for i, val in enumerate(df['crime_type'].unique())}
        victim_gender_to_code_map = {val: i for i, val in enumerate(df['Victim Gender'].unique())}
        weapon_used_to_code_map = {val: i for i, val in enumerate(df['Weapon Used'].unique())}
        zone_type_to_code_map = {val: i for i, val in enumerate(df['zone_type'].unique())}
        source_to_code_map = {val: i for i, val in enumerate(df['source'].unique())}

        df['city_code'] = df['City'].map(city_to_code_map).astype(int)
        df['crime_type_code'] = df['crime_type'].map(crime_type_to_code_map).astype(int)
        df['victim_gender_code'] = df['Victim Gender'].map(victim_gender_to_code_map).astype(int)
        df['weapon_used_code'] = df['Weapon Used'].map(weapon_used_to_code_map).astype(int)
        df['zone_type_code'] = df['zone_type'].map(zone_type_to_code_map).astype(int)
        df['source_code'] = df['source'].map(source_to_code_map).astype(int)
        print("Categorical columns mapped.")

        # 4. Ensure other numeric/boolean types match DB schema
        print("Converting other numeric/boolean types...")
        df['victim_age'] = df['Victim Age'].astype(float)
        df['latitude'] = df['latitude'].astype(float)
        df['longitude'] = df['longitude'].astype(float)
        df['crowd_density'] = df['crowd_density'].astype(float)
        df['severity_score'] = df['severity_score'].astype(float)
        df['safety_score'] = df['safety_score'].astype(float)
        df['is_safe_route'] = df['is_safe_route'].astype(bool)

        # Extract hour, day, month from the datetime object
        df['hour_val'] = df['date_of_occurrence_dt'].dt.hour.astype(float)
        df['day_val'] = df['date_of_occurrence_dt'].dt.day.astype(float)
        df['month_val'] = df['date_of_occurrence_dt'].dt.month.astype(float)
        print("Numeric/boolean types converted and date components extracted.")

        # Define the exact order of columns for insertion to match crime_logs table in PostgreSQL
        db_column_order = [
            'date_of_occurrence', 'city_code', 'crime_code', 'crime_type', 'crime_description',
            'victim_age', 'victim_gender', 'weapon_used', 'latitude', 'longitude',
            'zone_type', 'crowd_density', 'severity_score', 'safety_score',
            'source', 'is_safe_route', 'hour', 'day', 'month'
        ]

        # Select and rename columns to match DB schema, ensuring correct order
        print("Preparing final DataFrame for insertion...")
        df_final_insert = df[[
            'date_of_occurrence',
            'city_code',
            'Crime Code', # Maps to crime_code in DB
            'crime_type_code', # Maps to crime_type in DB
            'Crime Description', # Maps to crime_description in DB
            'victim_age',
            'victim_gender_code', # Maps to victim_gender in DB
            'weapon_used_code', # Maps to weapon_used in DB
            'latitude',
            'longitude',
            'zone_type_code', # Maps to zone_type in DB
            'crowd_density',
            'severity_score',
            'safety_score',
            'source_code', # Maps to source in DB
            'is_safe_route',
            'hour_val', # Maps to hour in DB
            'day_val', # Maps to day in DB
            'month_val' # Maps to month in DB
        ]].rename(columns={
            'Crime Code': 'crime_code',
            'crime_type_code': 'crime_type',
            'Crime Description': 'crime_description',
            'victim_gender_code': 'victim_gender',
            'weapon_used_code': 'weapon_used',
            'zone_type_code': 'zone_type',
            'source_code': 'source',
            'hour_val': 'hour',
            'day_val': 'day',
            'month_val': 'month'
        })

        # Reorder columns to ensure they match `db_column_order`
        df_final_insert = df_final_insert[db_column_order]
        print("DataFrame columns reordered to match DB schema.")

        # --- Insert Data into PostgreSQL ---
        insert_sql = """
        INSERT INTO crime_logs (
            date_of_occurrence, city_code, crime_code, crime_type, crime_description,
            victim_age, victim_gender, weapon_used, latitude, longitude,
            zone_type, crowd_density, severity_score, safety_score,
            source, is_safe_route, hour, day, month
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s
        );
        """
        rows_inserted = 0
        conn.autocommit = False # Start a transaction

        print("Starting row insertion into database...")
        for index, row in df_final_insert.iterrows():
            try:
                # Replace np.nan with None for DB insertion (especially for Weapon Used if it's not mapped fully)
                row_list = [None if pd.isna(x) else x for x in row.tolist()]
                cur.execute(insert_sql, tuple(row_list))
                rows_inserted += 1
            except psycopg2.Error as e:
                conn.rollback()
                print(f"Database error inserting row {index}: {e}")
                print(f"Row data: {row.tolist()}")
                raise
            except Exception as e:
                conn.rollback()
                print(f"An unexpected error occurred inserting row {index}: {e}")
                print(f"Row data: {row.tolist()}")
                raise

        conn.commit()
        print(f"Successfully inserted {rows_inserted} rows into 'crime_logs' table.")

    except FileNotFoundError:
        print(f"Error: CSV file not found at '{CSV_FILE_PATH}'")
    except psycopg2.Error as e:
        print(f"Database connection or query error: {e}")
        if conn:
            conn.rollback()
    except Exception as e:
        print(f"An unexpected error occurred during data loading: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
            print("Database connection closed.")

if __name__ == '__main__':
    load_csv_to_db()