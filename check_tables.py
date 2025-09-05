import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def check_database_tables():
    """Connects to the database and prints a list of all tables."""
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

        # Query to get the names of all tables
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = cursor.fetchall()

        print("Available tables in the database:")
        for table in tables:
            print(f"- {table[0]}")

        cursor.close()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    check_database_tables()