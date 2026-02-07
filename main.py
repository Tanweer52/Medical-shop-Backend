from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import json
import os

app = FastAPI(title="Medical Shop Backend", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)


DATA_FILE = "medicines.json"
SALES_FILE = "sales.json"

# Load data from file and ensure consistent fields
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            data = json.load(f)
            # Add missing fields with defaults for consistency
            for item in data:
                item.setdefault('cost', 0.0)
                item.setdefault('price', 0.0)
                item.setdefault('min_stock', 10)
                # Calculate needed qty
                item['needed_qty'] = max(0, item.get('min_stock', 10) - item['qty'])
            return data
    return [
        {"id": 1, "name": "Paracetamol 500mg", "generic": "Paracetamol", "batch": "A1", "rack": "A1", "qty": 5, "expiry": "2026-02-15", "cost": 10.0, "price": 15.0, "min_stock": 10, "needed_qty": 5},
        {"id": 2, "name": "Amoxicillin 250mg", "generic": "Amoxicillin", "batch": "B2", "rack": "B1", "qty": 0, "expiry": "2024-12-01", "cost": 20.0, "price": 25.0, "min_stock": 5, "needed_qty": 5},
        {"id": 3, "name": "Cetirizine 10mg", "generic": "Cetirizine", "batch": "C3", "rack": "A2", "qty": 50, "expiry": "2026-08-10", "cost": 5.0, "price": 8.0, "min_stock": 20, "needed_qty": 0},
        {"id": 4, "name": "Aspirin 75mg", "generic": "Aspirin", "batch": "D4", "rack": "B2", "qty": 2, "expiry": "2026-01-20", "cost": 3.0, "price": 5.0, "min_stock": 15, "needed_qty": 13}
    ]

# Save data to file
def save_data():
    for item in medicines_db:
        item['needed_qty'] = max(0, item.get('min_stock', 10) - item['qty'])
    with open(DATA_FILE, "w") as f:
        json.dump(medicines_db, f, indent=2)

# Load sales data
def load_sales():
    if os.path.exists(SALES_FILE):
        with open(SALES_FILE, "r") as f:
            return json.load(f)
    return []

# Save sales data
def save_sales():
    with open(SALES_FILE, "w") as f:
        json.dump(sales_db, f, indent=2)

medicines_db = load_data()
sales_db = load_sales()

class Medicine(BaseModel):
    id: int
    name: str
    generic: str
    batch: str
    rack: str
    qty: int
    expiry: str
    cost: float
    price: float
    min_stock: int
    needed_qty: int

class StockUpdate(BaseModel):
    add_qty: int

class Batch(BaseModel):
    batch: str
    expiry: str
    qty: int
    cost: float
    price: float

class NewMedicine(BaseModel):
    name: str
    generic: str
    rack: str
    min_stock: int
    batches: List[Batch]

class SaleItem(BaseModel):
    medicine_id: int
    qty: int
    price: float

class Sale(BaseModel):
    customer_name: str
    items: List[SaleItem]
    payment_method: str
    total: float

@app.get("/medicines", response_model=List[Medicine])
def get_medicines(q: Optional[str] = None):
    if q:
        query = q.lower()
        return [m for m in medicines_db if query in m["name"].lower() or query in m["generic"].lower()]
    return medicines_db

@app.post("/medicines/{medicine_id}/add-stock")
def add_stock(medicine_id: int, update: StockUpdate):
    medicine = next((m for m in medicines_db if m["id"] == medicine_id), None)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    medicine["qty"] += update.add_qty
    save_data()
    return {"message": f"Added {update.add_qty} to {medicine['name']}. New qty: {medicine['qty']}"}

@app.post("/medicines/{medicine_id}/sell-stock")
def sell_stock(medicine_id: int, update: StockUpdate):
    medicine = next((m for m in medicines_db if m["id"] == medicine_id), None)
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    if medicine["qty"] < update.add_qty:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    medicine["qty"] -= update.add_qty
    save_data()
    return {"message": f"Sold {update.add_qty} from {medicine['name']}. Remaining qty: {medicine['qty']}"}

@app.post("/sales")
def process_sale(sale: Sale):
    for item in sale.items:
        medicine = next((m for m in medicines_db if m["id"] == item.medicine_id), None)
        if not medicine:
            raise HTTPException(status_code=404, detail=f"Medicine {item.medicine_id} not found")
        if medicine["qty"] < item.qty:
            raise HTTPException(status_code=400, detail=f"Insufficient stock for {medicine['name']}")
        medicine["qty"] -= item.qty
    
    # Save sale to sales_db
    new_sale_id = max([s['id'] for s in sales_db]) + 1 if sales_db else 1
    sale_data = {
        "id": new_sale_id,
        "date": datetime.now().isoformat(),
        "customer_name": sale.customer_name,
        "items": [item.dict() for item in sale.items],
        "payment_method": sale.payment_method,
        "total": sale.total
    }
    sales_db.append(sale_data)
    save_sales()
    save_data()  # Save updated medicine stock
    return {"message": "Sale processed successfully", "sale_id": new_sale_id}

@app.get("/sales")
def get_sales():
    return sales_db

@app.get("/medicines/summary")
def get_summary():
    low_stock = [m for m in medicines_db if m["qty"] <= m.get("min_stock", 10)]
    expiring_soon = [m for m in medicines_db if days_until(m["expiry"]) <= 60]
    total_medicines = len(medicines_db)
    
    # Compute restock list
    restock = []
    for m in medicines_db:
        status = 'green'
        if m['qty'] <= 0:
            status = 'red'
        elif m['qty'] <= m.get('min_stock', 10):
            status = 'yellow'
        days = days_until(m['expiry'])
        if days < 0:
            status = 'red'  # expired
        elif days <= 30:
            if status == 'green':
                status = 'yellow'  # expiring soon but stock ok
        if status != 'green':
            suggested = max(0, m.get('min_stock', 10) - m['qty']) if m['qty'] <= m.get('min_stock', 10) else 0
            restock.append({
                'id': m['id'],
                'name': m['name'],
                'batch': m['batch'],
                'suggested': suggested,
                'qty': m['qty'],
                'expiry': m['expiry'],
                'status': status
            })
    
    urgent = restock  # Use restock as urgent items
    
    return {
        "totalMedicines": total_medicines,
        "lowStockCount": len(low_stock),
        "expiringCount": len(expiring_soon),
        "pendingPrescriptions": 0,  # Placeholder
        "urgent": urgent,
        "restock": restock
    }

@app.get("/suggest")
def suggest_medicines(q: Optional[str] = None):
    if not q:
        return []
    query = q.lower()
    return [m for m in medicines_db if query in m["name"].lower() or query in m["generic"].lower()]

@app.post("/medicines")
def add_medicine(medicine: NewMedicine):
    created_or_updated = []
    for batch in medicine.batches:
        if batch.qty <= 0:
            continue 
        
        existing = next((m for m in medicines_db if m["name"] == medicine.name and m["batch"] == batch.batch), None)
        if existing:
            existing["qty"] += batch.qty
            existing["expiry"] = batch.expiry 
            existing["cost"] = batch.cost
            existing["price"] = batch.price
            existing["rack"] = medicine.rack
            existing["min_stock"] = medicine.min_stock
            created_or_updated.append(existing)
        else:
            new_id = max([m["id"] for m in medicines_db]) + 1 if medicines_db else 1
            new_med = {
                "id": new_id,
                "name": medicine.name,
                "generic": medicine.generic,
                "batch": batch.batch,
                "rack": medicine.rack,
                "qty": batch.qty,
                "expiry": batch.expiry,
                "cost": batch.cost,
                "price": batch.price,
                "min_stock": medicine.min_stock
            }
            medicines_db.append(new_med)
            created_or_updated.append(new_med)
    save_data()
    return {"message": f"Processed {len(created_or_updated)} batches", "details": created_or_updated}

def days_until(date_str: str) -> int:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    now = datetime.now()
    return (d - now).days