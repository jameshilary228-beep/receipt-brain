from fastapi import FastAPI, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fpdf import FPDF
import os
import json
import uuid
from datetime import datetime, timedelta
from PIL import Image
import pytesseract

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "users_db.json"

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=4)

def check_expiry(user_id, db):
    user = db.get(user_id)
    if user and user.get("is_premium"):
        expiry_str = user.get("expiry_date")
        if expiry_str:
            expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > expiry_date:
                user["is_premium"] = False
                user["expiry_date"] = None
                return True
    return False

@app.post("/check_user")
async def check_user(user_id: str = Form(...)):
    db = load_db()
    check_expiry(user_id, db)
    save_db(db)
    user = db.get(user_id, {"count": 0, "is_premium": False, "credits": 0})
    return user

@app.post("/process")
async def process_receipt(user_id: str = Form(...), description: str = Form(...), country: str = Form(...)):
    db = load_db()
    check_expiry(user_id, db)
    user = db.setdefault(user_id, {"count": 0, "is_premium": False, "credits": 0})

    if not user["is_premium"] and user["credits"] <= 0 and user["count"] >= 3:
        return {"status": "error", "message": "Limit reached!"}

    # --- THE "REAL LOOK" PDF LOGIC ---
    pdf = FPDF()
    pdf.add_page()
    
    # Header Bar
    pdf.set_fill_color(30, 40, 60) # Dark Professional Blue
    pdf.rect(0, 0, 210, 40, 'F')
    
    pdf.set_text_color(212, 175, 55) # Gold Color
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 20, "TRANSACTION RECEIPT", ln=True, align='C')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, f"Issued in: {country.upper()}", ln=True, align='C')
    pdf.ln(20)

    # Receipt Body
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Date: {datetime.now().strftime('%d %b, %Y | %H:%M')}", ln=True)
    pdf.cell(0, 10, f"Receipt ID: RS-{uuid.uuid4().hex[:10].upper()}", ln=True)
    pdf.ln(5)

    # Details Table
    pdf.set_fill_color(240, 240, 240) # Light Grey
    lines = description.split('\n')
    for i, line in enumerate(lines):
        if i % 2 == 0:
            pdf.cell(0, 12, f"  {line}", ln=True, fill=True)
        else:
            pdf.cell(0, 12, f"  {line}", ln=True, fill=False)

    # Footer / Security Stamp
    pdf.ln(20)
    pdf.set_font("Arial", 'B', 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, "------------------------------------------------------------------", ln=True, align='C')
    pdf.cell(0, 5, "ELECTRONICALLY GENERATED - NO SIGNATURE REQUIRED", ln=True, align='C')
    pdf.set_text_color(30, 40, 60)
    pdf.cell(0, 5, "VERIFIED BY RECEIPTSTUDIO PRO SYSTEM", ln=True, align='C')

    file_name = f"receipt_{uuid.uuid4().hex[:8]}.pdf"
    file_path = f"static/{file_name}"
    os.makedirs("static", exist_ok=True)
    pdf.output(file_path)

    if not user["is_premium"]:
        if user["credits"] > 0: user["credits"] -= 1
        else: user["count"] += 1
    
    save_db(db)
    return {"status": "success", "pdf_url": f"https://receipt-brain-2.onrender.com/{file_path}"}

@app.post("/verify_payment")
async def verify(user_id: str = Form(...), plan: str = Form(...), file: UploadFile = File(...)):
    db = load_db()
    img = Image.open(file.file)
    text = pytesseract.image_to_string(img)
    keywords = ["8121186855", "Precious", "Successful", "Opay"]
    is_valid = any(word.lower() in text.lower() for word in keywords)

    if is_valid:
        user = db.setdefault(user_id, {"count": 0, "is_premium": False, "credits": 0})
        if plan == "monthly":
            user["is_premium"] = True
            expiry_date = datetime.now() + timedelta(days=30)
            user["expiry_date"] = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
        else:
            user["credits"] += 1
        save_db(db)
        return {"status": "success"}
    return {"status": "error", "message": "Invalid screenshot"}

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="static"), name="static")
