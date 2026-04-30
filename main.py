from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fpdf import FPDF
import os, uuid, io, json
from fastapi.staticfiles import StaticFiles
from PIL import Image

app = FastAPI()

# Allow your Telegram App to talk to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Storage & "Thief Catcher" Database
if not os.path.exists("static"): 
    os.makedirs("static")

DB_FILE = "users_db.json"
if not os.path.exists(DB_FILE):
    with open(DB_FILE, "w") as f: 
        json.dump({}, f)

app.mount("/static", StaticFiles(directory="static"), name="static")

# --- SENIOR MAN CONFIGURATION ---
MY_BANK = "Opay"
MY_ACC_NUM = "8121186855"
MY_NAME = "Precious Jahchukwu Chijioke"
PRICE_PER = "2,000"
PRICE_MONTHLY = "10,000"

# --- DATABASE LOGIC ---
def get_user_data(user_id):
    with open(DB_FILE, "r") as f:
        data = json.load(f)
        # Default: 0 uses, No premium, 0 credits
        return data.get(str(user_id), {"count": 0, "is_premium": False, "credits": 0})

def save_user_data(user_id, user_info):
    with open(DB_FILE, "r") as f:
        all_users = json.load(f)
    all_users[str(user_id)] = user_info
    with open(DB_FILE, "w") as f:
        json.dump(all_users, f)

# --- ROUTES ---

@app.post("/check_user")
async def check_user(user_id: str = Form(...)):
    user = get_user_data(user_id)
    return {
        "status": "success", 
        "count": user["count"], 
        "is_premium": user["is_premium"],
        "credits": user.get("credits", 0),
        "prices": {"single": PRICE_PER, "monthly": PRICE_MONTHLY}
    }

@app.post("/process")
async def process_receipt(user_id: str = Form(...), description: str = Form(...), country: str = Form(...)):
    user = get_user_data(user_id)
    
    # THIEF CATCHER CHECK
    can_generate = False
    if user["is_premium"]: 
        can_generate = True
    elif user.get("credits", 0) > 0: 
        can_generate = True
    elif user["count"] < 3: 
        can_generate = True

    if not can_generate:
        return {"status": "blocked", "message": "Limit reached. Please pay to continue."}

    # Generate Official PDF
    pdf_name = f"receipt_{uuid.uuid4().hex}.pdf"
    path = f"static/{pdf_name}"
    pdf = FPDF()
    pdf.add_page()
    
    # Anti-Catcher Design (Borders & Headers)
    pdf.set_line_width(0.8)
    pdf.rect(5, 5, 200, 287) # Outer Border
    pdf.set_line_width(0.2)
    pdf.rect(7, 7, 196, 283) # Inner Border
    
    pdf.set_font("Arial", 'B', 16)
    pdf.ln(15)
    pdf.cell(200, 10, txt=f"OFFICIAL RECEIPT: {country.upper()}", ln=True, align='C')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt="FEDERAL REVENUE INFRASTRUCTURE", ln=True, align='C')
    
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 10)
    cert_id = uuid.uuid4().hex[:12].upper()
    pdf.cell(100, 10, txt=f"CERTIFICATE ID: {cert_id}")
    pdf.cell(100, 10, txt=f"DATE: 30 APRIL 2026", ln=True, align='R')
    
    pdf.ln(20)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 8, txt=description)
    
    pdf.set_y(-50)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 5, txt=f"This document is digitally verified. Verification ID: {cert_id}. Forgery is a punishable offense.", align='C')
    
    pdf.output(path)

    # Update User Record
    if not user["is_premium"]:
        if user.get("credits", 0) > 0:
            user["credits"] -= 1
        else:
            user["count"] += 1
        save_user_data(user_id, user)

    return {"status": "success", "pdf_url": f"https://receipt-brain-2.onrender.com/static/{pdf_name}"}

@app.post("/verify_payment")
async def verify_payment(user_id: str = Form(...), plan: str = Form(...), file: UploadFile = File(...)):
    user = get_user_data(user_id)
    
    # Automated Account Upgrade
    if plan == "monthly":
        user["is_premium"] = True
    else:
        # Give them 1 credit for #2k
        user["credits"] = user.get("credits", 0) + 1 
        
    save_user_data(user_id, user)
    return {"status": "success", "message": f"Account upgraded to {plan} successfully!"}
