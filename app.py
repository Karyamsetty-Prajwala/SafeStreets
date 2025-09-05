import os
import json
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv
import psycopg2
import psycopg2.pool
import joblib
import pandas as pd
from datetime import datetime
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import googlemaps
import random
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder="static")  # <-- Serve static files from 'static' folder
CORS(app)

# -----------------------------
# Google Maps API
# -----------------------------
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY')
gmaps = None
if GOOGLE_MAPS_API_KEY:
    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        print("✅ Google Maps API client initialized.")
    except Exception as e:
        print(f"❌ Error initializing Google Maps API client: {e}")
        gmaps = None
else:
    print("⚠️ GOOGLE_MAPS_API_KEY not found. Route functionality will be mocked.")

# -----------------------------
# Database Connection Pool
# -----------------------------
db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        try:
            DATABASE_URL = os.getenv('DATABASE_URL')
            if not DATABASE_URL:
                raise ValueError("DATABASE_URL environment variable is not set.")
            url = urlparse(DATABASE_URL)
            db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port,
                database=url.path[1:]
            )
            print("✅ PostgreSQL connection pool initialized!")
            create_tables()
        except Exception as e:
            print(f"❌ Error initializing database pool: {e}")
            db_pool = None

def create_tables():
    global db_pool
    if db_pool is None:
        print("Database pool not initialized. Cannot create tables.")
        return
    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        # Users table
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            phone VARCHAR(10) NOT NULL,
            gender VARCHAR(10) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW()
        );
        """)
        # Route history
        cur.execute("""
        CREATE TABLE IF NOT EXISTS route_history (
            route_id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
            source_lat FLOAT NOT NULL,
            source_lng FLOAT NOT NULL,
            destination_lat FLOAT NOT NULL,
            destination_lng FLOAT NOT NULL,
            selected_route JSON NOT NULL,
            request_time TIMESTAMP DEFAULT NOW()
        );
        """)
        # Crime logs
        cur.execute("""
        CREATE TABLE IF NOT EXISTS crime_logs (
            crime_id SERIAL PRIMARY KEY,
            latitude FLOAT NOT NULL,
            longitude FLOAT NOT NULL,
            severity_score FLOAT,
            crowd_density FLOAT,
            is_safe_route BOOLEAN,
            crime_type VARCHAR(255)
        );
        """)
        # Feedback
        cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id SERIAL PRIMARY KEY,
            user_id INT REFERENCES users(user_id) ON DELETE CASCADE,
            segment_id INT,
            rating INT,
            comment TEXT,
            submitted_at TIMESTAMP DEFAULT NOW()
        );
        """)
        conn.commit()
        print("✅ All tables are initialized successfully!")
    except Exception as e:
        if conn: conn.rollback()
        print(f"❌ Error creating tables: {e}")
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.teardown_appcontext
def close_db_pool(exception=None):
    global db_pool
    if db_pool is not None:
        try:
            db_pool.closeall()
            print("PostgreSQL connection pool closed.")
            db_pool = None
        except Exception as e:
            print(f"Error closing database pool: {e}")

# Initialize DB pool at startup
init_db_pool()

# -----------------------------
# ML Model
# -----------------------------
model_pipeline = None
model_path = "gradient_boosting_safety_score_pipeline.pkl"

def init_ml_model():
    global model_pipeline
    try:
        if os.path.exists(model_path):
            model_pipeline = joblib.load(model_path)
            print(f"✅ ML model loaded from {model_path}")
        else:
            print(f"⚠️ ML model file not found at {model_path}. Using mock predictions.")
    except Exception as e:
        print(f"❌ Failed to load ML model: {e}")
        model_pipeline = None

init_ml_model()

# -----------------------------
# Serve Static Frontend
# -----------------------------
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    Serve static files (HTML, CSS, JS, images, videos) from the 'static' folder.
    If path not found, default to index.html
    """
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    else:
        return send_from_directory(app.static_folder, 'index.html')

# -----------------------------
# API Routes (Register/Login example)
# -----------------------------
@app.route('/api/register', methods=['POST'])
def register_user():
    global db_pool
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone')
    gender = data.get('gender')

    if not all([name, email, password, phone, gender]):
        return jsonify({"status": "error", "message": "All fields are required."}), 400

    hashed_password = generate_password_hash(password)
    conn, cur = None, None

    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO users (name, email, password_hash, phone, gender)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING user_id;
        """, (name, email, hashed_password, phone, gender))
        user_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"status": "success", "message": "User registered successfully!", "user_id": user_id}), 201
    except psycopg2.IntegrityError as e:
        if conn: conn.rollback()
        if "users_email_key" in str(e):
            return jsonify({"status": "error", "message": "Email already registered."}), 409
        return jsonify({"status": "error", "message": "Database integrity error."}), 500
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during registration: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/login', methods=['POST'])
def login_user():
    global db_pool
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, password_hash FROM users WHERE email=%s;", (email,))
        user = cur.fetchone()
        if user and check_password_hash(user[2], password):
            return jsonify({"status": "success", "user_id": user[0], "username": user[1]}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid credentials."}), 401
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

# -----------------------------
# Start Flask
# -----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
