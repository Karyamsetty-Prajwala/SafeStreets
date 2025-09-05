# test_db.py
import os
from dotenv import load_dotenv
import psycopg2

# Load environment variables from .env file
load_dotenv()

def test_db_connection():
    """
    Attempts a direct connection to the PostgreSQL database using
    the credentials from the .env file.
    """
    conn = None
    try:
        print("Attempting a direct connection to PostgreSQL...")
        
        # Get credentials from environment variables
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_host = os.getenv('DB_HOST')
        db_port = os.getenv('DB_PORT')
        db_database = os.getenv('DB_DATABASE')

        # Print the values to confirm they are being loaded correctly
        print(f"User: {db_user}")
        print(f"Host: {db_host}")
        print(f"Port: {db_port}")
        print(f"Database: {db_database}")

        conn = psycopg2.connect(
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database=db_database
        )
        print("✅ Success: Connection to PostgreSQL successful!")

        # You can perform a simple query to be sure
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"Database version: {db_version}")
        cursor.close()

    except psycopg2.OperationalError as e:
        print(f"❌ Error: Database connection failed. Details: {e}")
        print("Possible causes:")
        print("1. PostgreSQL service is not running.")
        print("2. Incorrect credentials in your .env file.")
        print("3. The database or user does not exist.")
        print("4. A firewall is blocking the connection.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
    finally:
        if conn:
            conn.close()
            print("Connection closed.")

if __name__ == "__main__":
    test_db_connection()
