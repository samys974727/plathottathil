from flask import send_file, flash, redirect, url_for
from bill_generator import BillGenerator
import os

def download_bill(db, bill_id):
    try:
        # Get bill data from Firestore
        bill_ref = db.collection('bills').document(bill_id)
        bill = bill_ref.get()
        
        if not bill.exists:
            flash('Bill not found!')
            return redirect(url_for('bills'))
            
        bill_data = bill.to_dict()
        
        # Generate PDF
        generator = BillGenerator()
        pdf_path = generator.generate_bill(bill_data)
        
        # Send file to user
        return send_file(
            pdf_path,
            as_attachment=True,
            download_name=f"bill_{bill_id}.pdf"
        )
        
    except Exception as e:
        print(f"Error generating bill: {e}")
        flash('Error generating bill')
        return redirect(url_for('bills')) 