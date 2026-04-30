from fastapi import FastAPI, Form, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fpdf import FPDF
import os
import json
import uuid
from datetime import datetime, timedelta
from PIL import Image, ImageOps, ImageFilter
import pytesseract
from fastapi.staticfiles import StaticFiles

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

    desc_lower = description.lower()
    is_pos = any(word in desc_lower for word in ["pos", "store", "market", "shop", "thermal", "slip"])

    if is_pos:
        pdf = FPDF(format=(80, 200)) 
        pdf.add_page()
        pdf.set_font("Courier", 'B', 14)
        pdf.cell(0, 10, f"{country.upper()} OFFICIAL SLIP", ln=True, align='C')
        pdf.set_font("Courier", size=9)
        pdf.cell(0, 5, "--------------------------------", ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Courier", size=10)
        lines = description.split('\n')
        for line in lines:
            pdf.multi_cell(0, 6, line.upper(), align='L')
        pdf.ln(10)
        pdf.cell(0, 5, "DATE: " + datetime.now().strftime('%Y-%m-%d %H:%M'), ln=True)
        pdf.cell(0, 5, "REF: " + uuid.uuid4().hex[:12].upper(), ln=True)
        pdf.ln(5)
        pdf.set_font("Courier", 'B', 10)
        pdf.cell(0, 10, "*** THANK YOU FOR YOUR PATRONAGE ***", ln=True, align='C')
    else:
        pdf = FPDF(format='A4')
        pdf.add_page()
        pdf.set_fill_color(30, 40, 60)
        pdf.rect(0, 0, 210, 45, 'F')
        pdf.set_text_color(212, 175, 55)
        pdf.set_font("Arial", 'B', 26)
        pdf.cell(0, 25, "TRANSACTION RECEIPT", ln=True, align='C')
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", 'I', 11)
        pdf.cell(0, 5, f"Jurisdiction: {country.upper()}", ln=True, align='C')
        pdf.ln(25)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"Issued Date: {datetime.now().strftime('%d %B, %Y')}", ln=True)
        pdf.cell(0, 10, f"Auth Code: RS-{uuid.uuid4().hex[:10].upper()}", ln=True)
        pdf.ln(5)
        pdf.set_fill_color(240, 240, 240)
        lines = description.split('\n')
        for i, line in enumerate(lines):
            fill = True if i % 2 == 0 else False
            pdf.cell(0, 12, f"  {line}", ln=True, fill=fill)
        pdf.ln(30)
        pdf.set_font("Arial", 'B', 9)
        pdf.set_text_color(160, 160, 160)
        pdf.cell(0, 5, "STRICTLY CONFIDENTIAL - ELECTRONIC DOCUMENT", ln=True, align='C')
        pdf.set_text_color(30, 40, 60)
        pdf.cell(0, 5, "VERIFIED BY RECEIPTSTUDIO PRO DIGITAL SYSTEMS", ln=True, align='C')

    file_name = f"receipt_{uuid.uuid4().hex[:8]}.pdf"
    file_path = f"static/{file_name}"
    os.makedirs("static", exist_ok=True)
    pdf.output(file_path)

    if not user["is_premium"]:
        if user["credits"] > 0: user["credits"] -= 1
        else: user["count"] += 1
    
    save_db(db)
    return {"status": "success", "pdf_url": f"https://receipt-brain-2.onrender.com/{file_path}"}

# --- THE HARD-CORE SECURITY VERIFICATION ---
@app.post("/verify_payment")
async def verify(user_id: str = Form(...), plan: str = Form(...), file: UploadFile = File(...)):
    db = load_db()
    
    try:
        # Step 1: Open and optimize image
        img = Image.open(file.file).convert('L') # Gray
        img = ImageOps.autocontrast(img) # Sharp contrast
        img = img.filter(ImageFilter.SHARPEN) # Sharpen text
        
        # Step 2: OCR Extraction
        text = pytesseract.image_to_string(img)
        text_clean = text.replace(" ", "").lower() # Remove spaces for strict check

        # Step 3: Strict Logic Checks
        # We check for the number, the name, and keywords
        has_account = "8121186855" in text_clean
        has_precious = "precious" in text_clean
        has_success = any(x in text_clean for x in ["success", "completed", "transaction", "delivered"])

        # THE GATE: Must have Account Number AND (Name OR Success)
        # Also ensure text isn't empty nonsense
        if len(text_clean) > 20 and has_account and (has_precious or has_success):
            user = db.setdefault(user_id, {"count": 0, "is_premium": False, "credits": 0})
            if plan == "monthly":
                user["is_premium"] = True
                expiry_date = datetime.now() + timedelta(days=30)
                user["expiry_date"] = expiry_date.strftime("%Y-%m-%d %H:%M:%S")
            else:
                user["credits"] += 1
            save_db(db)
            return {"status": "success"}
        
        # If it fails, return the "Pepper" message
        return {
            "status": "error", 
            "message": "❌ SECURITY REJECTION: This is not a valid Opay receipt for account 8121186855 (Precious). System logs flagged this as a random image. Pay real money to unlock!"
        }

    except Exception as e:
        return {"status": "error", "message": "❌ SYSTEM ERROR: Could not process image. Please upload a clear PNG/JPG receipt."}

app.mount("/static", StaticFiles(directory="static"), name="static")
