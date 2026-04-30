import os
import time
import uuid
import sqlite3
import easyocr
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load OCR Eyes
reader = easyocr.Reader(['en'])

# Setup Database
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id TEXT PRIMARY KEY, device_id TEXT, free_used INTEGER, sub_end REAL)''')
    conn.commit()
    conn.close()

init_db()

@app.post("/process")
async def process_request(
    user_id: str = Form(...),
    device_id: str = Form(...),
    country: str = Form(...),
    description: str = Form(...),
    screenshot: UploadFile = File(None)
):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    
    if not user:
        c.execute("INSERT INTO users VALUES (?, ?, 0, 0)", (user_id, device_id))
        conn.commit()
        user = (user_id, device_id, 0, 0)

    u_id, d_id, free_used, sub_end = user
    now = time.time()
    
    # OCR PAYMENT CHECK
    if free_used >= 3 and sub_end < now:
        if not screenshot:
            return {"status": "pay_required", "message": "Access Locked. Pay 2k to Precious Jahchukwu."}
        
        img_bytes = await screenshot.read()
        results = reader.readtext(img_bytes, detail=0)
        full_text = " ".join(results).upper()
        
        if "PRECIOUS JAHCHUKWU CHIJIOKE" in full_text or "8121186855" in full_text:
            sub_end = now + (30 * 86400)
            c.execute("UPDATE users SET sub_end=? WHERE user_id=?", (sub_end, user_id))
            conn.commit()
        else:
            return {"status": "error", "message": "Wrong Receipt. Send to 8121186855 Opay."}

    # GENERATE OFFICIAL PDF
    receipt_id = f"REF-{uuid.uuid4().hex[:10].upper()}"
    if not os.path.exists('static'): os.makedirs('static')
    file_path = f"static/{receipt_id}.pdf"
    
    can = canvas.Canvas(file_path, pagesize=A4)
    
    # --- ADD LOGO ---
    # This part go look for 'logo.png' for your GitHub/Render folder
    try:
        can.drawImage("logo.png", 50, 750, width=60, height=60, mask='auto')
    except:
        # If logo no dey, e go just draw a small box
        can.rect(50, 750, 60, 60)
        can.drawString(55, 775, "LOGO")

    # --- HEADER ---
    can.setFont("Helvetica-Bold", 16)
    can.drawCentredString(300, 780, f"GOVERNMENT OF {country.upper()}")
    can.setFont("Helvetica", 10)
    can.drawCentredString(300, 765, "OFFICIAL REVENUE & TRANSACTION DOCUMENT")
    can.line(50, 745, 550, 745)
    
    # --- DETAILS ---
    can.setFont("Helvetica-Bold", 12)
    can.drawString(50, 710, f"RECEIPT ID: {receipt_id}")
    can.setFont("Helvetica", 12)
    can.drawString(50, 690, f"DATE ISSUED: {datetime.now().strftime('%d %B, %Y')}")
    can.drawString(50, 670, f"COUNTRY ORIGIN: {country}")
    
    can.rect(50, 580, 500, 70) # Box for description
    can.drawString(60, 630, "DESCRIPTION OF TRANSACTION:")
    can.setFont("Helvetica-Oblique", 11)
    can.drawString(60, 610, f"{description}")
    
    # --- FOOTER ---
    can.setFont("Helvetica-Bold", 10)
    can.setStrokeColor(colors.green)
    can.drawCentredString(300, 200, "VERIFIED BY DIGITAL ENERGY SYSTEMS")
    can.setFont("Helvetica", 8)
    can.drawCentredString(300, 185, "This document is valid for international verification purposes.")
    
    can.save()

    if sub_end < now:
        c.execute("UPDATE users SET free_used=? WHERE user_id=?", (free_used + 1, user_id))
        conn.commit()
    conn.close()
    
    # NOTE: You must change 'your-app-name' to your real Render link
    return {
        "status": "success", 
        "pdf_url": f"https://your-app-name.onrender.com/{file_path}"
    }
