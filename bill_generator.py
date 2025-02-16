from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image
import os
from datetime import datetime

class BillGenerator:
    def __init__(self):
        self.width, self.height = A4
        
    def generate_bill(self, bill_data):
        # Create PDF filename with bill ID
        filename = f"bills/bill_{bill_data['bill_id']}.pdf"
        os.makedirs('bills', exist_ok=True)
        
        # Create canvas
        c = canvas.Canvas(filename, pagesize=A4)
        
        # Add watermark
        self._add_watermark(c)
        
        # Add header
        self._add_header(c, bill_data)
        
        # Add customer details
        self._add_customer_details(c, bill_data)
        
        # Add bill details
        self._add_bill_details(c, bill_data)
        
        # Add footer
        self._add_footer(c)
        
        c.save()
        return filename

    def _add_watermark(self, c):
        # Load and convert the image to grayscale
        img_path = "images/logo.png"
        try:
            with Image.open(img_path) as img:
                # Convert to grayscale
                img = img.convert('L')
                # Save temporary grayscale image
                temp_path = "images/temp_logo_gray.png"
                img.save(temp_path)

            # Calculate center position
            img_width = 700  # Adjust size as needed
            img_height = 800  # Adjust size as needed
            x = (self.width - img_width) / 2
            y = (self.height - img_height) / 2

            # Draw watermark with transparency
            c.saveState()
            c.setFillAlpha(0.1)  # Set transparency (0.1 = 10% opacity)
            c.drawImage(temp_path, x, y, width=img_width, height=img_height)
            c.restoreState()

            # Clean up temporary file
            os.remove(temp_path)
            
        except Exception as e:
            print(f"Error adding watermark: {e}")

    def _add_header(self, c, bill_data):
        # Company details
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, self.height - 50, "PLATHOTTATHIL TIMBER & SAWMILL")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, self.height - 70, "bill")
        c.drawString(50, self.height - 85, "Address Line 1")
        c.drawString(50, self.height - 100, "City, State, PIN")
        c.drawString(50, self.height - 115, "Phone: +91 XXXXXXXXXX")
        
        # Bill details on right
        c.drawString(400, self.height - 70, f"Bill No: {bill_data.get('bill_id', 'N/A')}")
        date_str = bill_data.get('date', datetime.now().strftime('%d/%m/%Y'))
        c.drawString(400, self.height - 85, f"Date: {date_str}")

    def _add_customer_details(self, c, bill_data):
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, self.height - 150, "Customer Details:")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, self.height - 170, f"Name: {bill_data['customer_name']}")
        c.drawString(50, self.height - 185, f"ID: {bill_data['customer_id']}")
        if bill_data.get('phone'):
            c.drawString(50, self.height - 200, f"Phone: {bill_data['phone']}")

    def _add_bill_details(self, c, bill_data):
        # Create table data
        data = [
            ['Description', 'Measurement', 'Quantity', 'Amount'],
            [
                f"Tree ID: {bill_data['tree_id']}", 
                bill_data['tree_measurement'],
                bill_data['tree_quantity'],
                f"₹{bill_data['total_amount']}"
            ]
        ]
        
        # Create table
        table = Table(data, colWidths=[200, 100, 100, 100])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        table.wrapOn(c, self.width, self.height)
        table.drawOn(c, 50, self.height - 300)
        
        # Add totals
        y_position = self.height - 350
        c.setFont("Helvetica-Bold", 12)
        c.drawString(350, y_position, f"Total Amount: ₹{bill_data['total_amount']}")
        c.drawString(350, y_position - 20, f"Amount Paid: ₹{bill_data['amount_paid']}")
        c.drawString(350, y_position - 40, f"Balance: ₹{bill_data['balance']}")

    def _add_footer(self, c):
        c.setFont("Helvetica", 10)
        c.drawString(50, 50, "Thank you for your business!")
        c.drawString(50, 35, "Terms & Conditions Apply")
        
        # Add signature space
        c.drawString(400, 100, "Authorized Signature")
        c.line(400, 90, 550, 90) 