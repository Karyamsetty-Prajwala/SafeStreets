import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def view_table_fields(table_name):
    """
    Connects to the database and prints the fields (columns) of a specified table.
    """
    conn = None
    try:
        # Get credentials from environment variables
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_database = os.getenv('DB_DATABASE')

        # Connect to the database
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database=db_database
        )
        cursor = conn.cursor()

        # Query to get the column names and data types of a table
        cursor.execute(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}';
        """)
        
        columns = cursor.fetchall()

        if not columns:
            print(f"Table '{table_name}' not found or has no columns.")
            return

        print(f"--- Columns in '{table_name}' table ---")
        for col in columns:
            print(f"Column: {col[0]}, Type: {col[1]}, Nullable: {'YES' if col[2] == 'YES' else 'NO'}")

        cursor.close()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # Call the function for each table you want to inspect
    view_table_fields('users')
    print("\n")
    view_table_fields('crime_logs')

