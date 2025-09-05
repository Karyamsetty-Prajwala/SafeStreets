import os
import json
from flask import Flask, jsonify, request, send_from_directory
from dotenv import load_dotenv
import psycopg2
import psycopg2.pool
import joblib
import pandas as pd
import numpy as np
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS
import googlemaps
import random
from urllib.parse import urlparse

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()  # Only needed for local dev; Render injects env vars at deploy

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# -----------------------------
# Initialize Flask app
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# Initialize Google Maps client
# -----------------------------
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
# Initialize Database Pool
# -----------------------------
db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is not None:
        return  # Already initialized

    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in environment")
        return

    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )
        print("✅ Database pool initialized")
    except Exception as e:
        print(f"❌ Error initializing database pool: {e}")
        db_pool = None

init_db_pool()

@app.teardown_appcontext
def close_db_pool(exception=None):
    global db_pool
    if db_pool:
        try:
            db_pool.closeall()
            print("PostgreSQL connection pool closed.")
            db_pool = None
        except Exception as e:
            print(f"Error closing database pool: {e}")

# -----------------------------
# Initialize ML Model
# -----------------------------
model_pipeline = None
model_path = 'gradient_boosting_safety_score_pipeline.pkl'

def init_ml_model():
    global model_pipeline
    try:
        if os.path.exists(model_path):
            model_pipeline = joblib.load(model_path)
            print(f"✅ ML model pipeline loaded from {model_path}")
        else:
            print(f"⚠️ ML model file not found at {model_path}. Using mock predictions.")
    except Exception as e:
        print(f"❌ Error loading ML model pipeline: {e}")
        model_pipeline = None

init_ml_model()

# -----------------------------
# Test DB endpoint
# -----------------------------
@app.route("/api/test_db")
def test_db():
    global db_pool
    if db_pool is None:
        return {"status": "error", "message": "Database pool not initialized"}, 500
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        db_pool.putconn(conn)
        return {"status": "success", "db_version": version}, 200
    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

# -----------------------------
# Frontend route example
# -----------------------------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# -----------------------------
# Backend routes: /api/register example
# -----------------------------
@app.route('/api/register', methods=['POST'])
def register_user():
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
            VALUES (%s, %s, %s, %s, %s) RETURNING user_id;
        """, (name, email, hashed_password, phone, gender))
        user_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"status": "success", "message": "User registered successfully!", "user_id": user_id}), 201
    except psycopg2.IntegrityError as e:
        if conn:
            conn.rollback()
        if "users_email_key" in str(e):
            return jsonify({"status": "error", "message": "Email already registered."}), 409
        return jsonify({"status": "error", "message": "Database integrity error."}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error during registration: {e}")
        return jsonify({"status": "error", "message": f"An error occurred during registration: {e}"}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

# -----------------------------
# Start app
# -----------------------------
if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(debug=True, port=port)
