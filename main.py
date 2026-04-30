from fastapi import FastAPI, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fpdf import FPDF
import os, uuid, pytesseract
from PIL import Image
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

if not os.path.exists("static"): os.makedirs("static")
app.mount("/static", StaticFiles(directory="static"), name="static")

# My Account Details
MY_BANK = "Opay / Kuda"
MY_ACC_NUM = "0123456789"
MY_NAME = "ReceiptStudio Admin"

@app.post("/process")
async def process_receipt(description: str = Form(...), country: str = Form(...)):
    # Receipt Generation Logic
    pdf_name = f"receipt_{uuid.uuid4().hex}.pdf"
    path = f"static/{pdf_name}"
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt=f"GOVERNMENT OF {country.upper()}", ln=True, align='C')
    pdf.multi_cell(0, 10, txt=f"\nDetails: {description}")
    pdf.output(path)
    return {"status": "success", "pdf_url": f"https://receipt-brain-2.onrender.com/static/{pdf_name}"}

@app.post("/verify_payment")
async def verify_payment(file: UploadFile = File(...)):
    # OCR Logic to confirm payment
    try:
        img = Image.open(file.file)
        text = pytesseract.image_to_string(img).lower()
        
        # Simple Check for payment keywords
        keywords = ["successful", "transfer", "amount", "completed"]
        if any(word in text for word in keywords):
            return {"status": "paid", "message": "Payment Verified! You can now generate more."}
        return {"status": "error", "message": "Payment not detected in image."}
    except:
        return {"status": "error", "message": "Could not read image."}
