from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import motor.motor_asyncio
from bson import ObjectId
from fastapi.middleware.cors import CORSMiddleware  # <--- THIS WAS MISSING
import certifi # Import this to fix the SSL error
import os                       # <--- NEW
from dotenv import load_dotenv  # <--- NEW
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows ALL frontends (safest for hackathon demos)
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# ==========================================
# 1. CONNECT TO MONGODB ATLAS
# ==========================================
# ⚠️ REPLACE THIS WITH YOUR REAL CONNECTION STRING
MONGO_URL = os.getenv("MONGO_URL")

# We add 'tlsCAFile=certifi.where()' to fix the SSL/Connection Error
client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URL, tlsCAFile=certifi.where())
db = client.techathon_db

users_collection = db.users
vehicles_collection = db.vehicles

# ==========================================
# 2. DATA MODELS (The Structure)
# ==========================================

# A. User Model
class UserSchema(BaseModel):
    user_id: str       # e.g., "parth_01"
    name: str          # e.g., "Parth Sharma"
    email: str         # e.g., "parth@gmail.com"
    phone: str         # e.g., "9876543210"

# B. Vehicle Model (THE DETAILED SCHEMA WE DECIDED ON)
class VehicleSchema(BaseModel):
    vehicle_id: str    # e.g., "MH-01-AB-1234"
    user_id: str       # LINKS TO THE USER ABOVE
    model: str         # e.g., "XUV 700"
    fuel_type: str     # e.g., "Petrol"
    
    # 1. Status Flags
    status: str = "OK"                 # "OK" or "ALERT"
    is_service_needed: bool = False    # True/False
    recommended_action: str = "System Healthy"

    # 2. The 10 Sensors (Default "Healthy" Values)
    sensors: Dict[str, float] = {
        "brake_pad_wear_mm": 10.0,      # >3.0 is good
        "battery_voltage_v": 12.6,      # >12.0 is good
        "engine_temp_c": 90.0,          # <105 is good
        "oil_pressure_psi": 35.0,
        "tire_pressure_fl_psi": 32.0,
        "tire_pressure_fr_psi": 32.0,
        "vibration_level_hz": 2.0,
        "coolant_level_pct": 100.0,
        "o2_sensor_voltage_v": 0.9,
        "transmission_temp_c": 80.0
    }

    # 3. AI Data (Empty by default, populated by your Logic later)
    predictions: List[Dict[str, Any]] = [
        # Dummy prediction for testing the UI
        {
            "component": "Suspension",
            "issue": "Minor Wear",
            "prediction": {"days_left": 45, "certainty": 65}
        }
    ]
    
    summary: str = "Vehicle is operating within normal parameters."

# --- Helper to fix the 'ObjectId not iterable' error ---
def fix_id(document):
    if document and "_id" in document:
        document["_id"] = str(document["_id"])
    return document

# ==========================================
# 3. API ENDPOINTS
# ==========================================

# --- ACTION 1: Create a User ---
@app.post("/create-user")
async def create_user(user: UserSchema):
    existing = await users_collection.find_one({"user_id": user.user_id})
    if existing:
        raise HTTPException(status_code=400, detail="User ID already exists")
    
    user_dict = user.dict()
    # Insert and Fix ID
    result = await users_collection.insert_one(user_dict)
    user_dict["_id"] = str(result.inserted_id)
    
    return {"message": "User Created", "user": user_dict}

# --- ACTION 2: Add a Vehicle (With the Detailed Schema) ---
@app.post("/add-vehicle")
async def add_vehicle(vehicle: VehicleSchema):
    # Check User Exists
    user = await users_collection.find_one({"user_id": vehicle.user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found! Create user first.")

    # Check Duplicate Vehicle
    existing_car = await vehicles_collection.find_one({"vehicle_id": vehicle.vehicle_id})
    if existing_car:
        raise HTTPException(status_code=400, detail="Vehicle ID already registered")

    vehicle_dict = vehicle.dict()
    # Insert and Fix ID
    result = await vehicles_collection.insert_one(vehicle_dict)
    vehicle_dict["_id"] = str(result.inserted_id)
    
    return {"message": "Vehicle Added to Fleet", "vehicle": vehicle_dict}

# --- ACTION 3: Get Dashboard (With Detailed Schema) ---
@app.get("/get-dashboard/{user_id}")
async def get_dashboard(user_id: str):
    user = await users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    cursor = vehicles_collection.find({"user_id": user_id})
    fleet = []
    async for doc in cursor:
        fleet.append(fix_id(doc))

    # print(fix_id(user))
    
    return {
        "user_profile": fix_id(user),
        "my_fleet": fleet,
        "total_vehicles": len(fleet)
    }