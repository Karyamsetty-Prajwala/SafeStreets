import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def inspect_database():
    """
    Connects to the database and prints the schema and data of key tables.
    """
    conn = None
    try:
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_database = os.getenv('DB_DATABASE')

        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_database
        )
        cursor = conn.cursor()

        # --- List all tables ---
        print("--- Available Tables ---")
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [table[0] for table in cursor.fetchall()]
        if tables:
            for table in tables:
                print(f"- {table}")
        else:
            print("No tables found in the database.")
        print("\n")

        # --- Inspect and display data for the 'users' table ---
        if 'users' in tables:
            print("--- Users Table Schema ---")
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'users' ORDER BY ordinal_position;
            """)
            for col in cursor.fetchall():
                print(f"Column: {col[0]}, Type: {col[1]}")
            print("\n--- Users Table Data ---")
            cursor.execute("SELECT user_id, name, email, phone, gender, created_at FROM users;")
            users = cursor.fetchall()
            for user in users:
                print(user)
            print("\n")

        # --- Inspect and display data for the 'routes' table ---
        if 'routes' in tables:
            print("--- Routes Table Schema ---")
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'routes' ORDER BY ordinal_position;
            """)
            for col in cursor.fetchall():
                print(f"Column: {col[0]}, Type: {col[1]}")
            print("\n--- Routes Table Data ---")
            cursor.execute("SELECT * FROM routes LIMIT 5;") # Limit to 5 for brevity
            routes = cursor.fetchall()
            for route in routes:
                print(route)
            print("\n")
                
        # --- Inspect and display data for the 'crime_logs' table ---
        if 'crime_logs' in tables:
            print("--- Crime Logs Table Schema ---")
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'crime_logs' ORDER BY ordinal_position;
            """)
            for col in cursor.fetchall():
                print(f"Column: {col[0]}, Type: {col[1]}")
            print("\n--- Crime Logs Table Data (First 5 Rows) ---")
            cursor.execute("SELECT * FROM crime_logs LIMIT 5;") # Limit to 5 for brevity
            crime_logs = cursor.fetchall()
            for log in crime_logs:
                print(log)
            print("\n")

        cursor.close()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    inspect_database()