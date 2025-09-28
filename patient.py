# ambulance_full_map_app.py

import threading
import time
import math
import requests
import tkinter as tk
from tkinter import messagebox
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import uvicorn
import folium
from tkhtmlview import HTMLLabel
import io
import base64

# ----------------- Database Setup -----------------
Base = declarative_base()
engine = create_engine("sqlite:///ambulance.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    phone = Column(String, unique=True)

class Driver(Base):
    __tablename__ = "drivers"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    phone = Column(String, unique=True)
    vehicle_number = Column(String)
    is_available = Column(Boolean, default=True)
    current_lat = Column(Float, default=0.0)
    current_lon = Column(Float, default=0.0)

class AmbulanceRequest(Base):
    __tablename__ = "requests"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    emergency_type = Column(String)
    pickup_lat = Column(Float)
    pickup_lon = Column(Float)
    status = Column(String, default="pending")

Base.metadata.create_all(engine)

# ----------------- FastAPI Setup -----------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Utility -----------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# ----------------- WebSocket -----------------
active_connections = {}

@app.websocket("/ws/driver/{driver_id}")
async def driver_ws(websocket: WebSocket, driver_id: int):
    await websocket.accept()
    active_connections[driver_id] = websocket
    try:
        while True:
            data = await websocket.receive_json()
            db = SessionLocal()
            driver = db.query(Driver).filter(Driver.id==int(driver_id)).first()
            if driver:
                driver.current_lat = data["lat"]
                driver.current_lon = data["lon"]
                db.commit()
            db.close()
    except WebSocketDisconnect:
        del active_connections[driver_id]

# ----------------- API Endpoints -----------------
@app.post("/add_driver")
def add_driver(name: str, phone: str, vehicle_number: str, db: Session = Depends(get_db)):
    driver = Driver(name=name, phone=phone, vehicle_number=vehicle_number)
    db.add(driver)
    db.commit()
    return {"message": "Driver added", "driver_id": driver.id}

@app.post("/add_user")
def add_user(name: str, phone: str, db: Session = Depends(get_db)):
    user = User(name=name, phone=phone)
    db.add(user)
    db.commit()
    return {"message": "User added", "user_id": user.id}

@app.post("/request_ambulance")
def request_ambulance(user_id: int, lat: float, lon: float, emergency_type: str, db: Session = Depends(get_db)):
    drivers = db.query(Driver).filter(Driver.is_available==True).all()
    if not drivers:
        return {"error": "No drivers available"}
    nearest_driver = min(drivers, key=lambda d: haversine(lat, lon, d.current_lat, d.current_lon))
    ambulance_request = AmbulanceRequest(
        user_id=user_id,
        driver_id=nearest_driver.id,
        pickup_lat=lat,
        pickup_lon=lon,
        emergency_type=emergency_type,
        status="enroute"
    )
    db.add(ambulance_request)
    nearest_driver.is_available = False
    db.commit()
    return {"message": "Ambulance dispatched", "driver": nearest_driver.name, "driver_id": nearest_driver.id,
            "pickup_lat": lat, "pickup_lon": lon}

@app.get("/update_driver_location")
def update_driver_location(driver_id: int, lat: float, lon: float, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter(Driver.id==driver_id).first()
    if driver:
        driver.current_lat = lat
        driver.current_lon = lon
        db.commit()
        return {"message": "Location updated"}
    return {"error": "Driver not found"}

@app.get("/")
def home():
    return HTMLResponse("<h2>Ambulance Service API Running</h2>")

# ----------------- Run FastAPI in Thread -----------------
def start_server():
    uvicorn.run(app, host="0.0.0.0", port=8000)

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()

# ----------------- Tkinter GUI with Live Map -----------------
API_URL = "http://127.0.0.1:8000"

def generate_map(driver_lat, driver_lon, patient_lat, patient_lon):
    m = folium.Map(location=[(driver_lat+patient_lat)/2, (driver_lon+patient_lon)/2], zoom_start=14)
    folium.Marker([patient_lat, patient_lon], popup="Patient", icon=folium.Icon(color='red')).add_to(m)
    folium.Marker([driver_lat, driver_lon], popup="Driver", icon=folium.Icon(color='blue')).add_to(m)
    data = io.BytesIO()
    m.save(data, close_file=False)
    return data.getvalue().decode()

def patient_map_gui(pickup_lat, pickup_lon, driver_id):
    map_window = tk.Toplevel()
    map_window.title("Live Map")

    html_content = HTMLLabel(map_window, html=generate_map(23.8103, 90.4125, pickup_lat, pickup_lon))
    html_content.pack(fill="both", expand=True)

    def update_map():
        try:
            response = requests.get(f"{API_URL}/update_driver_location", params={"driver_id": driver_id, "lat": 23.8103, "lon": 90.4125})
            # fetch updated driver location from DB
            db = SessionLocal()
            driver = db.query(Driver).filter(Driver.id==driver_id).first()
            db.close()
            if driver:
                html_content.set_html(generate_map(driver.current_lat, driver.current_lon, pickup_lat, pickup_lon))
        except:
            pass
        map_window.after(2000, update_map)

    update_map()

# ----------------- Patient GUI -----------------
def request_ambulance_gui():
    def send_request():
        try:
            user_id = int(user_id_entry.get())
            lat = float(lat_entry.get())
            lon = float(lon_entry.get())
            emergency_type = emergency_entry.get()
            response = requests.post(f"{API_URL}/request_ambulance",
                                     params={"user_id": user_id, "lat": lat, "lon": lon, "emergency_type": emergency_type})
            data = response.json()
            if "error" in data:
                messagebox.showerror("Error", data["error"])
            else:
                messagebox.showinfo("Success", f"Ambulance dispatched!\nDriver: {data['driver']}")
                patient_map_gui(lat, lon, data['driver_id'])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    patient_window = tk.Toplevel()
    patient_window.title("Patient App")

    tk.Label(patient_window, text="User ID:").grid(row=0, column=0)
    user_id_entry = tk.Entry(patient_window)
    user_id_entry.grid(row=0, column=1)

    tk.Label(patient_window, text="Latitude:").grid(row=1, column=0)
    lat_entry = tk.Entry(patient_window)
    lat_entry.grid(row=1, column=1)

    tk.Label(patient_window, text="Longitude:").grid(row=2, column=0)
    lon_entry = tk.Entry(patient_window)
    lon_entry.grid(row=2, column=1)

    tk.Label(patient_window, text="Emergency Type:").grid(row=3, column=0)
    emergency_entry = tk.Entry(patient_window)
    emergency_entry.grid(row=3, column=1)

    tk.Button(patient_window, text="Request Ambulance", command=send_request).grid(row=4, column=0, columnspan=2)

# ----------------- Driver GUI -----------------
def driver_gui():
    def start_tracking():
        try:
            driver_id = int(driver_id_entry.get())
            def send_location():
                lat = float(lat_entry.get())
                lon = float(lon_entry.get())
                while tracking[0]:
                    requests.get(f"{API_URL}/update_driver_location",
                                 params={"driver_id": driver_id, "lat": lat, "lon": lon})
                    lat += 0.0005  # simulate movement
                    lon += 0.0005
                    lat_entry.delete(0, tk.END)
                    lat_entry.insert(0, str(lat))
                    lon_entry.delete(0, tk.END)
                    lon_entry.insert(0, str(lon))
                    time.sleep(2)
            tracking[0] = True
            threading.Thread(target=send_location, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def stop_tracking():
        tracking[0] = False
        messagebox.showinfo("Stopped", "Tracking stopped.")

    driver_window = tk.Toplevel()
    driver_window.title("Driver App")

    tk.Label(driver_window, text="Driver ID:").grid(row=0, column=0)
    driver_id_entry = tk.Entry(driver_window)
    driver_id_entry.grid(row=0, column=1)

    tk.Label(driver_window, text="Latitude:").grid(row=1, column=0)
    lat_entry = tk.Entry(driver_window)
    lat_entry.insert(0, "23.8103")
    lat_entry.grid(row=1, column=1)

    tk.Label(driver_window, text="Longitude:").grid(row=2, column=0)
    lon_entry = tk.Entry(driver_window)
    lon_entry.insert(0, "90.4125")
    lon_entry.grid(row=2, column=1)

    tracking = [False]
    tk.Button(driver_window, text="Start Tracking", command=start_tracking).grid(row=3, column=0)
    tk.Button(driver_window, text="Stop Tracking", command=stop_tracking).grid(row=3, column=1)

# ----------------- Main GUI -----------------
root = tk.Tk()
root.title("Ambulance Service Simulator")

tk.Label(root, text="Ambulance Service Simulator", font=("Arial", 16)).pack(pady=10)
tk.Button(root, text="Patient App", width=20, command=request_ambulance_gui).pack(pady=5)
tk.Button(root, text="Driver App", width=20, command=driver_gui).pack(pady=5)

root.mainloop()

