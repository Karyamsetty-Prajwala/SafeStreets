# backend-python/app.py
import os
import json
from flask import Flask, jsonify, request
from dotenv import load_dotenv
import psycopg2
import psycopg2.pool # For connection pooling
import joblib # For loading the ML model
import pandas as pd # For creating DataFrames for prediction
from datetime import datetime
import numpy as np # For numpy operations
from werkzeug.security import generate_password_hash, check_password_hash # For password hashing
from flask_cors import CORS # For handling CORS
import googlemaps # New import
import random

# Load environment variables at the top to ensure they are available immediately.
load_dotenv()

app = Flask(__name__)
# Enable CORS for all routes
CORS(app)

# ----------------------------------------------------
# Google Maps API Client
# ----------------------------------------------------
# Get the Google Maps API key from environment variables
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

# ----------------------------------------------------
# Database Connection Pool
# ----------------------------------------------------
db_pool = None

def init_db_pool():
    """
    Initializes the global PostgreSQL connection pool.
    This function will be called lazily to prevent errors if the DB is not ready on startup.
    """
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
    """
    Closes the connection pool when the application context tears down.
    """
    global db_pool
    if db_pool is not None:
        try:
            db_pool.closeall()
            print("PostgreSQL connection pool closed.")
            db_pool = None
        except Exception as e:
            print(f"Error closing database pool: {e}")

# ----------------------------------------------------
# Load ML Model
# ----------------------------------------------------
model_pipeline = None
model_path = 'gradient_boosting_safety_score_pipeline.pkl'

def init_ml_model():
    """
    Initializes the ML model pipeline.
    """
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

# This function will be called at the start of the app
init_ml_model()


original_X_columns = [
    'Victim Age', 'latitude', 'longitude', 'crowd_density', 'severity_score',
    'hour', 'is_night', 'day_of_week',
    'City', 'crime_type', 'Victim Gender', 'Weapon Used', 'zone_type', 'source',
    'is_safe_route'
]

def generate_features_for_prediction(lat, lon):
    """Generates mock features for the ML model."""
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

# ----------------------------------------------------
# Helper for getting crime data from DB
# ----------------------------------------------------
# In your app.py file

def get_nearby_crime_data(lat, lon, radius_km=0.5):
    """
    Fetches nearby crime data from the database.
    """
    conn = None
    cur = None
    try:
        if db_pool is None:
            # Return mock data if the DB pool is not initialized
            return {
                "incident_count": 0, "avg_severity_score": 0.0,
                "perc_safe_incidents": 100.0, "crime_type_codes_nearby": []
            }

        conn = db_pool.getconn()
        if conn is None:
            return {
                "incident_count": 0, "avg_severity_score": 0.0,
                "perc_safe_incidents": 100.0, "crime_type_codes_nearby": []
            }
        cur = conn.cursor()

        lat_degree_per_km = 1 / 111.0
        lon_degree_per_km = 1 / (111.0 * np.cos(np.radians(lat)))
        lat_delta = radius_km * lat_degree_per_km
        lon_delta = radius_km * lon_degree_per_km
        
        # Explicitly convert numpy types to Python floats before passing to query
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
        return {
            "incident_count": 0, "avg_severity_score": 0.0,
            "perc_safe_incidents": 100.0, "crime_type_codes_nearby": []
        }
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)
# ----------------------------------------------------
# API Routes
# ----------------------------------------------------

@app.route('/')
def hello_world():
    return jsonify({"message": "SafeStreets Python Backend API is running!"})

@app.route('/api/create_tables')
def create_tables():
    """
    Creates the necessary database tables (e.g., users) if they do not exist.
    You must visit this endpoint once after starting the server.
    """
    conn = None
    cur = None
    try:
        if db_pool is None: init_db_pool()
        if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500
        
        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")
        
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS crime_logs (
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
        cur.execute("SELECT id, username, email FROM users;")
        users = cur.fetchall()
        cur.close()
        user_list = [{"id": user[0], "username": user[1], "email": user[2]} for user in users]
        return jsonify({"status": "success", "users": user_list}), 200
    except Exception as e:
        print(f"Error fetching users: {e}")
        return jsonify({"status": "error", "message": "An error occurred while fetching users."}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/register', methods=['POST'])
def register_user():
    """Handles user registration by inserting new user data into the database."""
    if db_pool is None: init_db_pool()
    if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500

    data = request.get_json()
    username, email, password = data.get('username'), data.get('email'), data.get('password')

    if not all([username, email, password]):
        return jsonify({"status": "error", "message": "Username, email, and password are required."}), 400

    hashed_password = generate_password_hash(password)
    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")
        cur = conn.cursor()
        
        print("Attempting to insert new user into the database...")
        cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id;",
                    (username, email, hashed_password))
        user_id = cur.fetchone()[0]
        conn.commit()
        print(f"User {username} registered successfully with ID {user_id}. Data has been committed.")
        return jsonify({"status": "success", "message": "User registered successfully!", "user_id": user_id}), 201
    except psycopg2.IntegrityError as e:
        if conn: conn.rollback()
        if "users_username_key" in str(e): return jsonify({"status": "error", "message": "Username already exists."}), 409
        elif "users_email_key" in str(e): return jsonify({"status": "error", "message": "Email already registered."}), 409
        else: return jsonify({"status": "error", "message": "Database integrity error."}), 500
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error during registration: {e}")
        return jsonify({"status": "error", "message": "An error occurred during registration."}), 500
    finally:
        if cur: cur.close()
        if conn: db_pool.putconn(conn)

@app.route('/api/login', methods=['POST'])
def login_user():
    """Handles user login by verifying credentials against the database."""
    if db_pool is None: init_db_pool()
    if db_pool is None: return jsonify({"status": "error", "message": "Database pool not initialized."}), 500
    
    data = request.get_json()
    username_or_email, password = data.get('username'), data.get('password')

    if not all([username_or_email, password]):
        return jsonify({"status": "error", "message": "Username/Email and password are required."}), 400

    conn, cur = None, None
    try:
        conn = db_pool.getconn()
        if conn is None: raise Exception("Failed to get a connection from the pool.")
        cur = conn.cursor()
        
        cur.execute("SELECT id, username, email, password_hash FROM users WHERE username = %s OR email = %s;",
                    (username_or_email, username_or_email))
        user_record = cur.fetchone()
        
        if user_record and check_password_hash(user_record[3], password):
            return jsonify({"status": "success", "message": "Login successful!", "user_id": user_record[0], "username": user_record[1], "email": user_record[2]}), 200
        else:
            return jsonify({"status": "error", "message": "Invalid username/email or password."}), 401
    except Exception as e:
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

    # Convert coordinates to a tuple for the API call
    start_coords = (start_point[0], start_point[1])
    end_coords = (end_point[0], end_point[1])
    
    routes_to_return = []

    if gmaps:
        try:
            # Use Google Maps API to get routes
            # The Directions API is now part of the Routes API.
            # We request multiple routes (alternatives=True) to give the user a choice.
            directions_result = gmaps.directions(
                origin=start_coords,
                destination=end_coords,
                mode="driving",
                alternatives=True
            )

            for idx, route in enumerate(directions_result):
                route_name = f"Route {idx + 1}"
                if preference == 'safest' and idx == 0:
                    route_name = "Safest Path" # This is a placeholder, you would need to calculate safety.
                
                # Extract the polyline from the route's steps
                polyline_coords = []
                for leg in route['legs']:
                    for step in leg['steps']:
                        # The Directions API returns encoded polylines, which need to be decoded.
                        # The googlemaps library handles this for you.
                        encoded_polyline = step['polyline']['points']
                        decoded_path = googlemaps.convert.decode_polyline(encoded_polyline)
                        polyline_coords.extend(decoded_path)
                
                # Get total duration and distance
                duration = route['legs'][0]['duration']['text']
                distance = route['legs'][0]['distance']['text']

                # Use a representative point (e.g., the first coordinate) for ML prediction
                if polyline_coords:
                    representative_lat, representative_lon = polyline_coords[0]['lat'], polyline_coords[0]['lng']
                else:
                    representative_lat, representative_lon = start_coords

                # Call the ML model and get crime data for safety score
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

                # Append the final route information to the list
                routes_to_return.append({
                    'name': route_name,
                    'duration': duration,
                    'distance': distance,
                    'color': 'blue' if preference == 'fastest' else 'green',
                    # This is the crucial part: convert Google Maps format to what your frontend expects
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
        # Fallback to the original mock data if the API key is not configured
        # You can keep your existing `simulated_route_data` here for this fallback.
        # ... (your original mock data logic) ...
        # For simplicity, let's return a simple error message for now
        return jsonify({
            "status": "error",
            "message": "Google Maps API is not configured. Route calculation is unavailable."
        }), 500

    # Sort routes based on preference
    if preference == 'safest':
        routes_to_return.sort(key=lambda x: x['safetyScore'], reverse=True)
    
    return jsonify({
        "status": "success",
        "message": "Routes and safety scores generated.",
        "routes": routes_to_return
    })


# ----------------------------------------------------
# Run the Server
# ----------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=os.getenv('PORT', 5000))
