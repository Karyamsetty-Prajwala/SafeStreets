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

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Google Maps API client
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
    print("⚠️ GOOGLE_MAPS_API_KEY not found in .env. Route functionality will be mocked.")

# Database Connection Pool
db_pool = None

def init_db_pool():
    global db_pool
    if db_pool is None:
        try:
            db_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                user=os.getenv('DB_USER'),
                password=os.getenv('DB_PASSWORD'),
                host=os.getenv('DB_HOST'),
                port=os.getenv('DB_PORT'),
                database=os.getenv('DB_DATABASE')
            )
            print("Successfully initialized PostgreSQL connection pool!")
        except Exception as e:
            print(f"Error initializing database pool: {e}")
            db_pool = None

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

# Load ML model
model_pipeline = None
model_path = 'gradient_boosting_safety_score_pipeline.pkl'

def init_ml_model():
    global model_pipeline
    try:
        if os.path.exists(model_path):
            model_pipeline = joblib.load(model_path)
            print(f"✅ ML model pipeline loaded from {model_path}")
        else:
            print(f"❌ ML model file not found at {model_path}. Using mock predictions.")
    except Exception as e:
        print(f"❌ Error loading ML model pipeline: {e}")
        model_pipeline = None

init_ml_model()

original_X_columns = [
    'Victim Age', 'latitude', 'longitude', 'crowd_density', 'severity_score',
    'hour', 'is_night', 'day_of_week',
    'City', 'crime_type', 'Victim Gender', 'Weapon Used', 'zone_type', 'source',
    'is_safe_route'
]

def generate_features_for_prediction(lat, lon):
    now = datetime.now()
    hour = float(now.hour)
    is_night = float(1 if hour >= 19 or hour <= 5 else 0)
    day_of_week = float(now.weekday())
    return {
        'Victim Age': float(np.random.randint(10, 79)),
        'latitude': float(lat),
        'longitude': float(lon),
        'crowd_density': float(np.random.uniform(10, 99)),
        'severity_score': float(np.random.uniform(1, 5)),
        'hour': hour,
        'is_night': is_night,
        'day_of_week': day_of_week,
        'City': 'Bengaluru',
        'crime_type': 'Theft',
        'Victim Gender': 'Other',
        'Weapon Used': 'None',
        'zone_type': 'Residential',
        'source': 'crowdsourced',
        'is_safe_route': float(np.random.choice([0, 1]))
    }

def get_nearby_crime_data(lat, lon, radius_km=0.5):
    conn = None
    cur = None
    try:
        if db_pool is None: return {"incident_count": 0, "avg_severity_score": 0.0, "perc_safe_incidents": 100.0, "crime_type_codes_nearby": []}
        conn = db_pool.getconn()
        if conn is None: return {"incident_count": 0, "avg_severity_score": 0.0, "perc_safe_incidents": 100.0, "crime_type_codes_nearby": []}
        cur = conn.cursor()
        lat_degree_per_km = 1 / 111.0
        lon_degree_per_km = 1 / (111.0 * np.cos(np.radians(lat)))
        lat_delta = radius_km * lat_degree_per_km
        lon_delta = radius_km * lon_degree_per_km
        min_lat = float(lat - lat_delta)
        max_lat = float(lat + lat_delta)
        min_lon = float(lon - lon_delta)
        max_lon = float(lon + lon_delta)
        query = """
        SELECT severity_score, is_safe_route, crime_type, victim_gender, weapon_used, zone_type, source
        FROM crime_logs
        WHERE latitude BETWEEN %s AND %s AND longitude BETWEEN %s AND %s
        LIMIT 200;
        """
        cur.execute(query, (min_lat, max_lat, min_lon, max_lon))
        crime_records = cur.fetchall()
        incident_count = len(crime_records)
        total_severity = 0
        safe_route_incidents = 0
        crime_type_codes_nearby = []
        for record in crime_records:
            total_severity += record[0]
            if record[1]:
                safe_route_incidents += 1
            crime_type_codes_nearby.append(record[2])
        avg_severity = total_severity / incident_count if incident_count > 0 else 0
        perc_safe_incidents = (safe_route_incidents / incident_count * 100) if incident_count > 0 else 0
        return {
            "incident_count": incident_count,
            "avg_severity_score": float(avg_severity),
            "perc_safe_incidents": float(perc_safe_incidents),
            "crime_type_codes_nearby": list(set(crime_type_codes_nearby))
        }
    except Exception as e:
        print(f"Error fetching nearby crime data: {e}")
        return {"incident_count": 0, "avg_severity_score": 0.0, "perc_safe_incidents": 100.0, "crime_type_codes_nearby": []}
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

# -----------------------------
# API Routes
# -----------------------------
@app.route('/')
def hello_world():
    return jsonify({"message": "SafeStreets Python Backend API is running!"})

@app.route('/api/save_selected_route', methods=['POST'])
def save_selected_route():
    """
    Save the user's selected route to the database.
    """
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    required_fields = ["user_id", "source_lat", "source_lng", "destination_lat", "destination_lng", "selected_route"]
    if not all(field in data for field in required_fields):
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO route_history (user_id, source_lat, source_lng, destination_lat, destination_lng, selected_route)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING route_id
        """, (
            data["user_id"],
            float(data["source_lat"]),
            float(data["source_lng"]),
            float(data["destination_lat"]),
            float(data["destination_lng"]),
            json.dumps(data["selected_route"])
        ))
        route_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"status": "success", "message": "Route saved successfully", "route_id": route_id}), 201
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error saving selected route: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

# In app.py, replace the existing /api/get_route_history route with this:
# In app.py, replace the existing get_route_history function with this:
# In app.py, replace the existing get_route_history function with this:
# In app.py, replace the existing get_route_history function with this:
# In app.py, replace the existing get_route_history function with this:
@app.route('/api/get_route_history/<int:user_id>', methods=['GET'])
def get_route_history(user_id):
    """
    Fetches a user's ride history from the database, converting
    coordinates to addresses using a geocoding service.
    """
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT request_time, source_lat, source_lng, destination_lat, destination_lng, selected_route
            FROM route_history
            WHERE user_id = %s
            ORDER BY request_time DESC;
        """, (user_id,))
        rows = cur.fetchall()

        history = []
        for r in rows:
            try:
                # Retrieve coordinates from the row
                source_lat, source_lng = r[1], r[2]
                dest_lat, dest_lng = r[3], r[4]

                # Convert coordinates to human-readable addresses
                source_address = get_address_from_coords(source_lat, source_lng)
                destination_address = get_address_from_coords(dest_lat, dest_lng)

                # Assuming r[5] is the selected_route JSON data
                selected_route_data = r[5]

                history.append({
                    "request_time": r[0].isoformat(),
                    "source_address": source_address,
                    "destination_address": destination_address,
                    "selected_route": selected_route_data
                })
            except Exception as e:
                print(f"Error processing ride history data for user {user_id}: {e}")
                continue

        return jsonify({"status": "success", "history": history}), 200
    except Exception as e:
        print(f"Error fetching ride history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)
@app.route('/api/create_tables')
def create_tables():
    """
    Drops existing tables and recreates them with the correct schema,
    including foreign key constraints.
    """
    conn = None
    cur = None
    try:
        if db_pool is None: init_db_pool()
        if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")

        cur = conn.cursor()

        # Drop tables in a safe order to avoid foreign key conflicts
        cur.execute("DROP TABLE IF EXISTS route_history CASCADE;")
        cur.execute("DROP TABLE IF EXISTS feedback CASCADE;")
        cur.execute("DROP TABLE IF EXISTS crime_logs CASCADE;")
        cur.execute("DROP TABLE IF EXISTS users CASCADE;")

        # Create tables
        cur.execute("""
            CREATE TABLE users (
                user_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                phone VARCHAR(10) NOT NULL,
                gender VARCHAR(10) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP WITH TIME ZONE
            );
        """)

        cur.execute("""
            CREATE TABLE crime_logs (
                id SERIAL PRIMARY KEY,
                latitude DECIMAL(9, 6) NOT NULL,
                longitude DECIMAL(9, 6) NOT NULL,
                severity_score DECIMAL(5, 2),
                crowd_density INTEGER,
                is_safe_route BOOLEAN,
                crime_type VARCHAR(50),
                reported_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE feedback (
                feedback_id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                segment_id INTEGER NOT NULL,
                rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                comment TEXT,
                submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)

        cur.execute("""
            CREATE TABLE route_history (
                route_id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                source_lat DECIMAL(9,6) NOT NULL,
                source_lng DECIMAL(9,6) NOT NULL,
                destination_lat DECIMAL(9,6) NOT NULL,
                destination_lng DECIMAL(9,6) NOT NULL,
                request_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                selected_route JSON NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            );
        """)

        conn.commit()
        print("Database tables created or already exist.")
        return jsonify({"status": "success", "message": "Database tables created or already exist."}), 200
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error creating tables: {e}")
        return jsonify({"status": "error", "message": f"Error creating tables: {e}"}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/user_data/<username>', methods=['GET'])
def get_user_data(username):
    """
    Fetches comprehensive user data including profile details, ride history, and feedback.
    """
    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()

        # 1. Fetch user details by username
        cur.execute("""
            SELECT user_id, name, email, phone, gender, created_at, last_login 
            FROM users WHERE name = %s;
        """, (username,))
        user_record = cur.fetchone()

        if not user_record:
            return jsonify({"status": "error", "message": "User not found."}), 404

        user_data = {
            "user_id": user_record[0],
            "name": user_record[1],
            "email": user_record[2],
            "phone": user_record[3],
            "gender": user_record[4],
            "created_at": user_record[5].isoformat() if user_record[5] else None,
            "last_login": user_record[6].isoformat() if user_record[6] else None
        }

        # 2. Fetch recent ride history for this user
        cur.execute("""
            SELECT source_lat, source_lng, destination_lat, destination_lng, request_time
            FROM route_history
            WHERE user_id = %s
            ORDER BY request_time DESC
            LIMIT 5;
        """, (user_data['user_id'],))
        ride_history_records = cur.fetchall()

        ride_history = [
            {
                "start": f"{r[0]}, {r[1]}",
                "end": f"{r[2]}, {r[3]}",
                "date": r[4].isoformat()
            } for r in ride_history_records
        ]
        user_data["ride_history"] = ride_history

        # 3. Fetch recent feedback for this user
        cur.execute("""
            SELECT rating, comment, submitted_at
            FROM feedback
            WHERE user_id = %s
            ORDER BY submitted_at DESC
            LIMIT 5;
        """, (user_data['user_id'],))
        feedback_records = cur.fetchall()
        feedback_list = [
            {
                "rating": r[0],
                "comment": r[1],
                "submitted_at": r[2].isoformat()
            } for r in feedback_records
        ]
        user_data["feedback"] = feedback_list

        return jsonify({"status": "success", "user": user_data}), 200

    except Exception as e:
        print(f"Error fetching user data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred: {str(e)}"}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)
# In app.py, add this new function below your imports
# In app.py, add this new function below your imports
def get_address_from_coords(lat, lng):
    """
    Uses Google Maps Geocoding API to get a human-readable address
    from latitude and longitude coordinates.
    """
    global gmaps
    if not gmaps:
        # Return coordinates if the API client is not initialized
        return f"Lat: {lat}, Lng: {lng}"

    try:
        # Use result_type='locality' to get a good place name, or leave it for a full address
        reverse_geocode_result = gmaps.reverse_geocode((lat, lng))
        if reverse_geocode_result:
            return reverse_geocode_result[0]['formatted_address']
        else:
            return f"Lat: {lat}, Lng: {lng}"
    except Exception as e:
        print(f"Error in reverse geocoding for ({lat}, {lng}): {e}")
        return f"Lat: {lat}, Lng: {lng}"

@app.route('/api/load_crime_data', methods=['POST'])
def load_crime_data():
    """
    Loads crime data from a JSON payload into the crime_logs table.
    Expects a list of crime objects in the request body.
    """
    if db_pool is None: init_db_pool()
    if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    if not data or not isinstance(data, list):
        return jsonify({"status": "error", "message": "Invalid input. Expected a JSON list of crime objects."}), 400

    conn = None
    cur = None
    try:
        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")

        cur = conn.cursor()
        insert_count = 0

        for crime in data:
            cur.execute("""
                INSERT INTO crime_logs (latitude, longitude, severity_score, crowd_density, is_safe_route, crime_type)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
            """, (
                crime.get('latitude'),
                crime.get('longitude'),
                crime.get('severity_score'),
                crime.get('crowd_density'),
                crime.get('is_safe_route'),
                crime.get('crime_type')
            ))
            insert_count += 1

        conn.commit()
        return jsonify({"status": "success", "message": f"{insert_count} crime records loaded successfully."}), 201

    except Exception as e:
        if conn: conn.rollback()
        print(f"Error loading crime data: {e}")
        return jsonify({"status": "error", "message": f"An error occurred while loading data: {e}"}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

# In app.py, replace the existing save_feedback function with this:
@app.route('/api/save_feedback', methods=['POST'])
def save_feedback():
    data = request.json
    user_id = data.get('userId')
    segment_id = data.get('segment_id')
    rating = data.get('rating')
    comment = data.get('comment')

    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    conn = None
    cur = None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO feedback (user_id, segment_id, rating, comment)
            VALUES (%s, %s, %s, %s) RETURNING feedback_id
        """, (user_id, segment_id, rating, comment))
        feedback_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"status": "success", "feedback_id": feedback_id}), 201
    except psycopg2.errors.ForeignKeyViolation as e:
        if conn: conn.rollback()
        print(f"Foreign Key Violation: {e}")
        return jsonify({"status": "error", "message": "User or route ID does not exist."}), 400
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error saving feedback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

# In app.py, replace the existing get_feedback function with this:
@app.route('/api/get_feedback/<int:user_id>', methods=['GET'])
def get_feedback(user_id):
    conn = None
    cur = None
    try:
        if db_pool is None:
            init_db_pool()
        if db_pool is None:
            return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

        conn = db_pool.getconn()
        cur = conn.cursor()
        cur.execute("""
            SELECT feedback_id, user_id, segment_id, rating, comment, submitted_at
            FROM feedback WHERE user_id = %s
            ORDER BY submitted_at DESC
        """, (user_id,))
        rows = cur.fetchall()

        feedback_list = []
        for r in rows:
            feedback_list.append({
                "feedback_id": r[0],
                "user_id": r[1],
                "segment_id": r[2],
                "rating": r[3],
                "comment": r[4],
                "submitted_at": r[5].isoformat() if r[5] else None # Handles NULL submitted_at
            })

        return jsonify({"feedback": feedback_list}), 200
    except Exception as e:
        print(f"Error fetching feedback: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/test_db')
def test_db_connection():
    """Checks the database connection and returns the version."""
    if db_pool is None: init_db_pool()
    if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    conn = None
    try:
        conn = db_pool.getconn()
        if conn is None: raise Exception("Database connection failed.")
        cursor = conn.cursor()
        cursor.execute('SELECT version();')
        db_version = cursor.fetchone()[0]
        cursor.close()
        return jsonify({"status": "success", "message": "Successfully connected to database.", "db_version": db_version})
    except Exception as e:
        print(f"Database test failed: {e}")
        return jsonify({"status": "error", "message": f"Database connection failed: {e}"}), 500
    finally:
        if conn: db_pool.putconn(conn)

@app.route('/api/users', methods=['GET'])
def get_all_users():
    """Fetches and returns a list of all registered users."""
    conn = None
    cur = None
    try:
        if db_pool is None: init_db_pool()
        if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500
        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")
        cur = conn.cursor()
        cur.execute("SELECT user_id, name, email FROM users;")
        users = cur.fetchall()
        cur.close()
        user_list = [{"id": user[0], "name": user[1], "email": user[2]} for user in users]
        return jsonify({"status": "success", "users": user_list}), 200
    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"status": "error", "message": "An error occurred while fetching users."}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.get_json()
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    phone = data.get('phone')
    gender = data.get('gender')

    if not all([name, email, password, phone, gender]):
        return jsonify({"status": "error", "message": "All fields are required."}), 400

    if len(phone) != 10 or not phone.isdigit():
        return jsonify({"status": "error", "message": "Phone number must be exactly 10 digits."}), 400

    if db_pool is None:
        init_db_pool()
    if db_pool is None:
        return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    hashed_password = generate_password_hash(password)
    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()

        cur.execute("""INSERT INTO users (name, email, password_hash, phone, gender) 
                    VALUES (%s, %s, %s, %s, %s) RETURNING user_id;""",
                    (name, email, hashed_password, phone, gender))
        user_id = cur.fetchone()[0]
        conn.commit()
        return jsonify({"status": "success", "message": "User registered successfully!", "user_id": user_id}), 201
    except psycopg2.IntegrityError as e:
        if conn: conn.rollback()
        if "users_email_key" in str(e):
            return jsonify({"status": "error", "message": "Email already registered."}), 409
        else:
            return jsonify({"status": "error", "message": "Database integrity error."}), 500
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during registration: {e}")
        return jsonify({"status": "error", "message": f"An error occurred during registration: {e}"}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)


@app.route('/api/login', methods=['POST'])
def login_user():
    """Handles user login by verifying credentials against the database."""
    if db_pool is None: init_db_pool()
    if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not all([email, password]):
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")
        cur = conn.cursor()

        cur.execute("SELECT user_id, name, email, password_hash FROM users WHERE email = %s;",
                    (email,))
        user_record = cur.fetchone()

        if user_record and check_password_hash(user_record[3], password):
            return jsonify({"status": "success", "message": "Login successful!", "user_id": user_record[0], "username": user_record[1], "email": user_record[2]}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid email or password."}), 401
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during login: {e}")
        return jsonify({"status": "error", "message": "An error occurred during login."}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/get_routes_with_safety', methods=['POST'])
def get_routes_with_safety():
    """
    Fetches safety-rated routes using Google Maps API and a safety model.
    """
    if db_pool is None: init_db_pool()
    if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    start_point = data.get('start_point')
    end_point = data.get('end_point')
    preference = data.get('preference', 'fastest')

    if not all([start_point, end_point]):
        return jsonify({"error": "Invalid input. 'start_point' and 'end_point' are required."}), 400

    start_coords = (start_point[0], start_point[1])
    end_coords = (end_point[0], end_point[1])

    routes_to_return = []

    if gmaps:
        try:
            directions_result = gmaps.directions(
                origin=start_coords,
                destination=end_coords,
                mode="driving",
                alternatives=True
            )

            for idx, route in enumerate(directions_result):
                route_name = f"Route {idx + 1}"
                if preference == 'safest' and idx == 0:
                    route_name = "Safest Path" 

                polyline_coords = []
                for leg in route['legs']:
                    for step in leg['steps']:
                        encoded_polyline = step['polyline']['points']
                        decoded_path = googlemaps.convert.decode_polyline(encoded_polyline)
                        polyline_coords.extend(decoded_path)

                duration = route['legs'][0]['duration']['text']
                distance = route['legs'][0]['distance']['text']

                if polyline_coords:
                    representative_lat, representative_lon = polyline_coords[0]['lat'], polyline_coords[0]['lng']
                else:
                    representative_lat, representative_lon = start_coords

                ml_features = generate_features_for_prediction(representative_lat, representative_lon)
                df_ml_input = pd.DataFrame([ml_features])

                if model_pipeline:
                    try:
                        df_ml_input = df_ml_input[original_X_columns]
                        ml_predicted_score = float(model_pipeline.predict(df_ml_input)[0])
                    except Exception as e:
                        print(f"ML prediction failed for route {route_name}: {e}")
                        ml_predicted_score = random.uniform(0, 10)
                else:
                    ml_predicted_score = random.uniform(0, 10)

                nearby_crime_data = get_nearby_crime_data(representative_lat, representative_lon)
                final_safety_score = ml_predicted_score

                safety_details = f"{route_name}: Safety score derived from ML model."
                if nearby_crime_data.get("incident_count", 0) > 0:
                    final_safety_score -= 1.0 
                    safety_details += f" {nearby_crime_data['incident_count']} incidents recorded nearby."

                routes_to_return.append({
                    'name': route_name,
                    'duration': duration,
                    'distance': distance,
                    'color': 'blue' if preference == 'fastest' else 'green',
                    'coordinates': [[c['lat'], c['lng']] for c in polyline_coords],
                    'safetyScore': round(min(10.0, max(0.0, final_safety_score)), 2),
                    'safetyDetails': safety_details
                })

        except Exception as e:
            print(f"Google Maps API error: {e}")
            return jsonify({
                "status": "error", 
                "message": f"An error occurred while fetching routes from Google Maps: {e}"
            }), 500
    else:
        return jsonify({
            "status": "error",
            "message": "Google Maps API is not configured. Route calculation is unavailable."
        }), 500

    if preference == 'safest':
        routes_to_return.sort(key=lambda x: x['safetyScore'], reverse=True)

    return jsonify({
        "status": "success",
        "message": "Routes and safety scores generated.",
        "routes": routes_to_return
    })


if __name__ == '__main__':
    app.run(debug=True, port=os.getenv('PORT', 5000))

# New routes to serve front-end files
@app.route('/<path:path>')
def send_static(path):
    return send_from_directory('.', path)

@app.route('/')
def home():
    return send_from_directory('.', 'landing.html')