import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from bill_generator import BillGenerator  # Assuming you have this module
import pytz

load_dotenv()

# Initialize Firebase Admin with environment variables
cred = credentials.Certificate({
    "type": "service_account",
    "project_id": os.getenv('FIREBASE_PROJECT_ID'),
    "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),
    "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.getenv('FIREBASE_CLIENT_ID'),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL')
})

# Initialize Firebase
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    if request.method == 'POST':
        try:
            # Check if customer ID already exists
            customer_id = str(request.form['customer_id'])
            existing_bills = db.collection('bills').where('customer_id', '==', customer_id).stream()
            
            # Convert to list to check if any bills exist
            existing_bills_list = list(existing_bills)
            if existing_bills_list:
                # Get the first bill to get customer details
                existing_customer = existing_bills_list[0].to_dict()
                return {
                    'status': 'error',
                    'message': 'Customer ID already exists',
                    'customer': {
                        'name': existing_customer['customer_name'],
                        'phone': existing_customer['phone'],
                        'id': existing_customer['customer_id']
                    }
                }, 400
            
            # If customer ID is unique, proceed with bill creation
            doc_ref = db.collection('bills').document()
            
            # Calculate balance
            total_amount = float(request.form['total_amount'])
            amount_paid = float(request.form['amount_paid'])
            balance = total_amount - amount_paid
            
            # Prepare billing data
            billing_data = {
                'customer_id': customer_id,
                'customer_name': str(request.form['customer_name']),
                'phone': str(request.form['phone']) if request.form['phone'] else None,
                'tree_id': str(request.form['tree_id']),
                'tree_measurement': str(request.form['tree_measurement']),
                'tree_quantity': int(request.form['tree_quantity']) if request.form['tree_quantity'] else 1,
                'total_amount': total_amount,
                'amount_paid': amount_paid,
                'balance': balance,
                'timestamp': firestore.SERVER_TIMESTAMP,
                'bill_id': doc_ref.id,
                'status': 'active'
            }

            doc_ref.set(billing_data)
            return {'status': 'success', 'message': 'Bill saved successfully!'}, 200
            
        except Exception as e:
            print(f"Error saving to Firestore: {e}")
            return {'status': 'error', 'message': str(e)}, 500

    return render_template('billing.html')

# Add the new bills route here
@app.route('/bills')
def bills():
    try:
        # Get all bills from Firestore
        bills_ref = db.collection('bills').order_by('timestamp', direction=firestore.Query.DESCENDING)
        bills = bills_ref.stream()
        bills_list = []
        for bill in bills:
            bill_data = bill.to_dict()
            # Convert timestamp to readable format
            if bill_data.get('timestamp'):
                bill_data['date'] = bill_data['timestamp'].strftime('%d/%m/%Y')
            bills_list.append(bill_data)
        return render_template('bills.html', bills=bills_list)
    except Exception as e:
        print(f"Error fetching bills: {e}")
        flash('Error fetching bills')
        return redirect(url_for('home'))

# Add the edit bill route here
@app.route('/edit_bill/<string:bill_id>', methods=['GET', 'POST'])
def edit_bill(bill_id):
    try:
        bill_ref = db.collection('bills').document(bill_id)
        
        if request.method == 'POST':
            # Calculate new balance
            total_amount = float(request.form['total_amount'])
            amount_paid = float(request.form['amount_paid'])
            balance = total_amount - amount_paid
            
            # Update bill data
            bill_data = {
                'customer_id': str(request.form['customer_id']),
                'customer_name': str(request.form['customer_name']),
                'phone': str(request.form['phone']),
                'tree_id': str(request.form['tree_id']),
                'tree_measurement': str(request.form['tree_measurement']),
                'tree_quantity': int(request.form['tree_quantity']) if request.form['tree_quantity'] else 1,
                'total_amount': float(total_amount),
                'amount_paid': float(amount_paid),
                'balance': float(balance),
                'last_edited': firestore.SERVER_TIMESTAMP
            }
            
            # Update the document
            bill_ref.update(bill_data)
            
            flash('Bill updated successfully!')
            return redirect(url_for('bills'))
        
        # GET request - show edit form
        bill = bill_ref.get()
        if bill.exists:
            return render_template('editbill.html', bill=bill.to_dict())
        else:
            flash('Bill not found!')
            return redirect(url_for('bills'))
            
    except Exception as e:
        print(f"Error updating bill: {e}")
        flash(f'Error: {str(e)}')
        return redirect(url_for('bills'))

# Add the download route
@app.route('/download_bill/<string:bill_id>')
def download_bill_route(bill_id):
    try:
        # Get bill data from Firestore
        bill_ref = db.collection('bills').document(bill_id)
        bill = bill_ref.get()
        
        if not bill.exists:
            flash('Bill not found!')
            return redirect(url_for('bills'))
            
        bill_data = bill.to_dict()
        
        # Format the timestamp to date string
        if bill_data.get('timestamp'):
            bill_data['date'] = bill_data['timestamp'].strftime('%d/%m/%Y')
        else:
            bill_data['date'] = datetime.datetime.now().strftime('%d/%m/%Y')
        
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

# Add customers route
@app.route('/customers')
def customers():
    try:
        # Get all bills from Firestore
        bills_ref = db.collection('bills').stream()
        
        # Create a dictionary to store unique customers
        customers_dict = {}
        
        # Extract unique customers from bills
        for bill in bills_ref:
            bill_data = bill.to_dict()
            customer_id = bill_data.get('customer_id')
            
            if customer_id not in customers_dict:
                customers_dict[customer_id] = {
                    'customer_id': customer_id,
                    'customer_name': bill_data.get('customer_name'),
                    'phone': bill_data.get('phone'),
                    'total_bills': 1,
                    'total_balance': bill_data.get('balance', 0)
                }
            else:
                customers_dict[customer_id]['total_bills'] += 1
                customers_dict[customer_id]['total_balance'] += bill_data.get('balance', 0)
        
        # Convert dictionary to list
        customers_list = list(customers_dict.values())
        
        return render_template('customers.html', customers=customers_list)
    except Exception as e:
        print(f"Error fetching customers: {e}")
        flash('Error fetching customers')
        return redirect(url_for('home'))

# Add customer lookup endpoint
@app.route('/get_customer')
def get_customer():
    try:
        search_by = request.args.get('searchBy')
        value = request.args.get('value')
        
        if not search_by or not value:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        # Debug logging
        print(f"Search request - searchBy: {search_by}, value: {value}")

        if search_by == 'id':
            customer_id = str(value).strip()
            print(f"Searching for customer_id: {customer_id}")
            
            bills = list(db.collection('bills')
                        .where('customer_id', '==', customer_id)
                        .limit(1)
                        .stream())
            
            print(f"Found {len(bills)} matching records for ID search")
        else:
            value = str(value).strip()
            print(f"Searching for customer_name: {value}")
            
            bills = list(db.collection('bills')
                        .where('customer_name', '==', value)
                        .limit(1)
                        .stream())
            
            print(f"Found {len(bills)} matching records for name search")

        if bills:
            customer_data = bills[0].to_dict()
            print(f"Found customer data: {customer_data}")
            response_data = {
                'status': 'success',
                'customer': {
                    'id': customer_data['customer_id'],
                    'name': customer_data['customer_name'],
                    'phone': customer_data.get('phone', '')
                }
            }
            print(f"Sending response: {response_data}")
            return jsonify(response_data)
        
        print("No matching records found")
        return jsonify({'status': 'success', 'customer': None})
        
    except Exception as e:
        print(f"Error in get_customer: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# Add tree management routes
@app.route('/trees')
def trees():
    try:
        # Get all trees from trees collection
        trees_ref = db.collection('trees').order_by('tree_id').stream()
        trees_dict = {tree.to_dict()['tree_id']: tree.to_dict() for tree in trees_ref}
        
        # Get trees from bills collection
        bills_ref = db.collection('bills').stream()
        
        # Update tree information from bills
        for bill in bills_ref:
            bill_data = bill.to_dict()
            tree_id = bill_data.get('tree_id')
            
            if tree_id:
                if tree_id not in trees_dict:
                    # Add new tree from bill
                    trees_dict[tree_id] = {
                        'tree_id': tree_id,
                        'size': bill_data.get('tree_measurement', 'N/A'),
                        'status': 'sold',
                        'customer_name': bill_data.get('customer_name'),
                        'bill_date': bill_data.get('timestamp'),
                        'bill_id': bill_data.get('bill_id'),
                        'amount': bill_data.get('total_amount')
                    }
                else:
                    # Update existing tree status if it was sold
                    trees_dict[tree_id].update({
                        'status': 'sold',
                        'customer_name': bill_data.get('customer_name'),
                        'bill_date': bill_data.get('timestamp'),
                        'bill_id': bill_data.get('bill_id'),
                        'amount': bill_data.get('total_amount')
                    })
        
        # Convert dictionary to list and sort by tree_id
        trees_list = list(trees_dict.values())
        trees_list.sort(key=lambda x: x['tree_id'])
        
        return render_template('trees.html', trees=trees_list)
    except Exception as e:
        print(f"Error fetching trees: {e}")
        flash('Error fetching trees')
        return redirect(url_for('home'))

@app.route('/add_tree', methods=['POST'])
def add_tree():
    try:
        # Create new tree document
        doc_ref = db.collection('trees').document()
        
        tree_data = {
            'tree_id': str(request.form['tree_id']),
            'size': str(request.form['size']),
            'description': str(request.form['description']),
            'status': 'available',
            'timestamp': firestore.SERVER_TIMESTAMP,
            'document_id': doc_ref.id
        }
        
        # Add to Firestore
        doc_ref.set(tree_data)
        
        flash('Tree added successfully!')
        return redirect(url_for('trees'))
    except Exception as e:
        print(f"Error adding tree: {e}")
        flash(f'Error: {str(e)}')
        return redirect(url_for('trees'))

@app.route('/get_customer_bills/<customer_id>')
def get_customer_bills(customer_id):
    try:
        bills = db.collection('bills').where('customer_id', '==', customer_id).stream()
        bills_list = [bill.to_dict() for bill in bills]
        return jsonify(bills_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/analytics')
def analytics():
    try:
        # Fetch all bills
        bills_ref = db.collection('bills').stream()
        bills = [bill.to_dict() for bill in bills_ref]
        
        # Initialize dictionaries for aggregation
        daily = {}
        weekly = {}
        monthly = {}
        
        # Define timezone
        tz = pytz.timezone('Asia/Kolkata')  # Adjust to your timezone
        
        for bill in bills:
            timestamp = bill.get('timestamp')
            if not timestamp:
                continue
            dt = timestamp.astimezone(tz)
            date_str = dt.strftime('%Y-%m-%d')
            
            # Daily aggregation
            daily[date_str] = daily.get(date_str, 0) + bill.get('total_amount', 0)
            
            # Weekly aggregation (ISO week number)
            year, week, _ = dt.isocalendar()
            week_str = f"{year}-W{week}"
            weekly[week_str] = weekly.get(week_str, 0) + bill.get('total_amount', 0)
            
            # Monthly aggregation
            month_str = dt.strftime('%Y-%m')
            monthly[month_str] = monthly.get(month_str, 0) + bill.get('total_amount', 0)
        
        # Sort the data
        daily_sorted = dict(sorted(daily.items()))
        weekly_sorted = dict(sorted(weekly.items()))
        monthly_sorted = dict(sorted(monthly.items()))
        
        return render_template('analytics.html',
                               daily=daily_sorted,
                               weekly=weekly_sorted,
                               monthly=monthly_sorted)
    except Exception as e:
        print(f"Error fetching analytics data: {e}")
        flash('Error fetching analytics data')
        return redirect(url_for('home'))

@app.route('/api/analytics')
def api_analytics():
    try:
        # Fetch all bills
        bills_ref = db.collection('bills').stream()
        bills = [bill.to_dict() for bill in bills_ref]
        
        # Initialize dictionaries for aggregation
        daily = {}
        weekly = {}
        monthly = {}
        
        # Define timezone
        tz = pytz.timezone('Asia/Kolkata')  # Adjust to your timezone
        
        for bill in bills:
            timestamp = bill.get('timestamp')
            if not timestamp:
                continue
            dt = timestamp.astimezone(tz)
            date_str = dt.strftime('%Y-%m-%d')
            
            # Daily aggregation
            daily[date_str] = daily.get(date_str, 0) + bill.get('total_amount', 0)
            
            # Weekly aggregation (ISO week number)
            year, week, _ = dt.isocalendar()
            week_str = f"{year}-W{week}"
            weekly[week_str] = weekly.get(week_str, 0) + bill.get('total_amount', 0)
            
            # Monthly aggregation
            month_str = dt.strftime('%Y-%m')
            monthly[month_str] = monthly.get(month_str, 0) + bill.get('total_amount', 0)
        
        # Sort the data
        daily_sorted = dict(sorted(daily.items()))
        weekly_sorted = dict(sorted(weekly.items()))
        monthly_sorted = dict(sorted(monthly.items()))
        
        return jsonify({
            'daily': daily_sorted,
            'weekly': weekly_sorted,
            'monthly': monthly_sorted
        })
    except Exception as e:
        print(f"Error fetching analytics data: {e}")
        return jsonify({'error': 'Error fetching analytics data'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)