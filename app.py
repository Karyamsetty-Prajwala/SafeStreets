import os
import json
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool
import joblib
import pandas as pd
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
import googlemaps
from datetime import datetime
import random

# -----------------------------
# Load environment variables
# -----------------------------
load_dotenv()  # Only used for local development

DATABASE_URL = os.getenv("DATABASE_URL")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# -----------------------------
# Flask app
# -----------------------------
app = Flask(__name__)
CORS(app)

# -----------------------------
# Google Maps client
# -----------------------------
gmaps = None
if GOOGLE_MAPS_API_KEY:
    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)
        print("✅ Google Maps API client initialized.")
    except Exception as e:
        print(f"❌ Google Maps API client initialization failed: {e}")
else:
    print("⚠️ GOOGLE_MAPS_API_KEY not set. Route functionality will be mocked.")

# -----------------------------
# Database Pool
# -----------------------------
db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is not None:
        return
    if not DATABASE_URL:
        print("❌ DATABASE_URL not set in environment variables.")
        return
    try:
        db_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )
        print("✅ Database pool initialized.")
    except Exception as e:
        print(f"❌ Failed to initialize database pool: {e}")
        db_pool = None

init_db_pool()

@app.teardown_appcontext
def close_db_pool(exception=None):
    global db_pool
    if db_pool:
        try:
            db_pool.closeall()
            print("Database pool closed.")
            db_pool = None
        except Exception as e:
            print(f"Error closing database pool: {e}")

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
# Test DB Endpoint
# -----------------------------
@app.route("/api/test_db")
def test_db():
    global db_pool
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        cur.close()
        db_pool.putconn(conn)
        return jsonify({"status": "success", "db_version": version}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# -----------------------------
# Example Frontend Route
# -----------------------------
@app.route('/')
def home():
    return send_from_directory('.', 'index.html')

# -----------------------------
# Example API Route: Register User
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

# -----------------------------
# Start Flask app
# -----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(debug=True, port=port)
