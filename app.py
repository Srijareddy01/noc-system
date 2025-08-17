from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, make_response
from flask import Flask, render_template, request, flash, redirect, url_for, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import datetime
import os
import secrets
from weasyprint import HTML
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from io import BytesIO
from flask_socketio import SocketIO, emit
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from io import BytesIO
import datetime
from flask_moment import Moment


load_dotenv()

app = Flask(__name__)
moment = Moment(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///noc_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')

db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app)

# Database Models
class Student(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)

    def get_id(self):
        return f"student_{self.id}"
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    department = db.Column(db.String(50), nullable=False)
    roll_no = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    noc_requests = db.relationship('NOCRequest', backref='student', lazy=True)

    @property
    def is_admin(self):
        return False

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)

    def get_id(self):
        return f"admin_{self.id}"
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    @property
    def is_admin(self):
        return True

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    head_name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # e.g., 'academic', 'administrative'
    designation = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f"Department('{self.name}', '{self.type}')"

class NOCRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.String(20), db.ForeignKey('student.roll_no'), nullable=False)
    request_number = db.Column(db.String(20), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.timezone.utc))
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    completed = db.Column(db.Boolean, default=False)
    statuses = db.relationship('NOCStatus', backref='noc_request', lazy=True)

class NOCStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    noc_request_id = db.Column(db.Integer, db.ForeignKey('noc_request.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    reason = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.now(datetime.timezone.utc), onupdate=datetime.datetime.now(datetime.timezone.utc))
    approved_by = db.Column(db.String(100))
    approval_token = db.Column(db.String(100), unique=True, nullable=False)
    department = db.relationship('Department', backref='noc_statuses', lazy=True)

@login_manager.user_loader
def load_user(user_id):
    # Check if user_id contains 'admin_' prefix
    if str(user_id).startswith('admin_'):
        return Admin.query.get(int(user_id.split('_')[1]))
    # If not admin, check for student prefix or treat as raw ID
    if str(user_id).startswith('student_'):
        return Student.query.get(int(user_id.split('_')[1]))
    else:
        # Fallback for cases where user_id might be a raw integer (e.g., from old sessions or direct ID usage)
        try:
            return Student.query.get(int(user_id))
        except ValueError:
            return None

def initialize_admin():
    with app.app_context():
        if not Admin.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash('srija1234') # You should change this to a strong password
            admin = Admin(username='admin', email='srijapalla01@gmail.com', password_hash=hashed_password)
            db.session.add(admin)
            db.session.commit()


def initialize_departments():
        if Department.query.first():
            return # Departments already exist, do not re-initialize
        departments_to_add = [
            {'name': 'Training & Placement Cell', 'email': 'shivanipqtturi22@gmail.com', 'head_name': 'Dr. S. P. Singh', 'type': 'administrative', 'designation': None},
            {'name': 'Sports / Games', 'email': '226y1a66e3@gmail.com', 'head_name': 'Dr. P. V. Ramana', 'type': 'administrative', 'designation': None},
            {'name': 'Examination Branch', 'email': '226y1a66e8@gmail.com', 'head_name': 'Dr. K. L. N. Rao', 'type': 'administrative', 'designation': None},
            {'name': 'Library', 'email': 'pallasrija.edunet@gmail.com', 'head_name': 'Dr. M. K. Sharma', 'type': 'administrative', 'designation': None},
            {'name': 'Alumni Association', 'email': 'pallapranavika18@gmail.com', 'head_name': 'Mr. R. K. Gupta', 'type': 'administrative', 'designation': None},
            {'name': 'IEEE / ISTE / CSI', 'email': 'pallasrija8724@gmail.com', 'head_name': 'Dr. V. K. Singh', 'type': 'academic', 'designation': None},
            {'name': 'Mentor', 'email': 'psrija27@gmail.com', 'head_name': 'Dr. S. K. Singh', 'type': 'administrative', 'designation': None},
            
        ]

        with app.app_context():
            for dept_data in departments_to_add:
                if not Department.query.filter_by(name=dept_data['name']).first():
                    new_dept = Department(name=dept_data['name'], email=dept_data['email'], head_name=dept_data['head_name'], type=dept_data['type'], designation=dept_data['designation'])
                    db.session.add(new_dept)
            db.session.commit()



@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form['full_name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        department = request.form['department']
        roll_no = request.form['roll_no']

        if password != confirm_password:
            flash('Passwords do not match!', 'error')
            return redirect(url_for('register'))

        if Student.query.filter_by(email=email).first():
            flash('Email already registered!', 'error')
            return redirect(url_for('register'))

        if Student.query.filter_by(roll_no=roll_no).first():
            flash('Roll Number already exists!', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        student = Student(
            full_name=full_name,
            email=email,
            password_hash=hashed_password,
            department=department,
            roll_no=roll_no
        )
        db.session.add(student)
        db.session.commit()

        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = Student.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')

    return render_template('login.html')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = Admin.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid email or password!', 'error')

    return render_template('admin_login.html')

@app.route('/edit_department/<int:dept_id>', methods=['GET', 'POST'])
@login_required
def edit_department(dept_id):
    department = Department.query.get_or_404(dept_id)
    if request.method == 'POST':
        department.name = request.form['name']
        department.email = request.form['email']
        department.head_name = request.form['head_name']
        department.type = request.form['type']
        department.designation = request.form.get('designation')
        db.session.commit()
        flash('Department updated successfully!', 'success')
        return redirect(url_for('admin_dashboard'))
    return render_template('edit_department.html', department=department)


@app.route('/delete_department/<int:dept_id>', methods=['POST'])
@login_required
def delete_department(dept_id):
    department = Department.query.get_or_404(dept_id)
    db.session.delete(department)
    db.session.commit()
    flash('Department/Faculty deleted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    noc_requests = NOCRequest.query.filter_by(roll_no=current_user.roll_no).all()
    return render_template('dashboard.html', noc_requests=noc_requests)

@app.route('/request-noc', methods=['GET', 'POST'])
@login_required
def request_noc():
    if request.method == 'POST':
        # Generate unique request number
        request_number = f"NOC-{datetime.datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

        
        # Create NOC request
        noc_request = NOCRequest(
            roll_no=current_user.roll_no,
            request_number=request_number
        )
        db.session.add(noc_request)
        db.session.flush()

        # Get selected departments from the form
        selected_department_names = request.form.getlist('departments')

        # Add only selected departments with approval tokens
        for dept_name in selected_department_names:
            dept = Department.query.filter_by(name=dept_name).first()
            if dept:
                approval_token = secrets.token_urlsafe(32)
                noc_status = NOCStatus(
                    noc_request_id=noc_request.id,
                    department_id=dept.id,
                    approval_token=approval_token
                )
                db.session.add(noc_status)

                # Send email with approval links
                send_approval_email([dept.email], current_user, request_number, dept.name, approval_token, current_user.email)

        db.session.commit()
        
        flash('NOC request submitted successfully!', 'success')
        return redirect(url_for('dashboard'))

    departments = Department.query.all()
    return render_template('request_noc.html', departments=departments)

def send_approval_email(to_emails, student, request_number, department_name, approval_token, sender_email):
    try:
        approve_url = url_for('approve_noc', token=approval_token, _external=True)
        reject_url = url_for('reject_noc', token=approval_token, _external=True)
        
        msg = Message(
            subject=f'NOC Request #{request_number} - Action Required',
            sender=sender_email,
            recipients=to_emails,
            body=f"""
Dear Department Head,

A new NOC request has been submitted by:
Student: {student.full_name}
Student ID: {student.roll_no}
Email: {student.email}
Department: {student.department}

Request Number: {request_number}
Department: {department_name}

Please review and take action on this request:

APPROVE: {approve_url}
REJECT: {reject_url}

If rejecting, you will be prompted to provide a reason.

"""
        )
        mail.send(msg)
    except Exception as e:
        app.logger.error(f"Error sending email: {e}") # Log the error

def send_completion_email(to_email, request_number, sender_email):
    try:
        msg = Message(
            subject=f'NOC Request #{request_number} - Completed',
            sender=sender_email,
            recipients=[to_email],
            body=f"""
Dear Student,

Your NOC Request #{request_number} has been completed and approved by all departments.

You can now download your NOC from the dashboard.

"""
        )
        mail.send(msg)
    except Exception as e:
        pass # Or add appropriate error handling

def send_rejection_email(to_email, request_number, sender_email):
    try:
        msg = Message(
            subject=f'NOC Request #{request_number} - Rejected',
            sender=sender_email,
            recipients=[to_email],
            body=f"""
Dear Student,

Your NOC Request #{request_number} has been rejected by one or more departments.

Please check the dashboard for details.

"""
        )
        mail.send(msg)
    except Exception as e:
        pass # Or add appropriate error handling

@app.route('/track_request/<int:request_id>')


@login_required
def track_request(request_id):
    noc_request = NOCRequest.query.get_or_404(request_id)
    statuses = NOCStatus.query.filter_by(noc_request_id=noc_request.id).all()
    departments = Department.query.all()
    return render_template('track.html', noc_request=noc_request, statuses=statuses, departments=departments)

@app.route('/noc_form')
def noc_form():
    return render_template('noc_form.html')

@app.route('/admin_download_noc', methods=['POST'])
@login_required
def admin_download_noc():
    if not isinstance(current_user, Admin) or not current_user.is_admin:
        flash('Unauthorized access! Only administrators can download NOCs.', 'error')
        return redirect(url_for('admin_dashboard'))

    roll_no = request.form.get('roll_no')
    request_number = request.form.get('request_number')

    if not roll_no or not request_number:
        flash('Please provide both Roll Number and Request Number.', 'error')
        return redirect(url_for('admin_dashboard'))

    return download_noc(request_number, roll_no)

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    # In a real application, you'd want to add role-based access control here
    # For example, only allow users with an 'admin' role to access this page
    departments = Department.query.all()
    noc_requests = NOCRequest.query.all()
    return render_template('admin_dashboard.html', departments=departments, noc_requests=noc_requests)

@app.route('/add_department', methods=['POST'])
@login_required
def add_department():
    # Again, add role-based access control
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        head_name = request.form['head_name']
        dept_type = request.form.get('type', 'academic')
        designation = request.form.get('designation')

        new_department = Department(name=name, email=email, head_name=head_name, type=dept_type, designation=designation)
        db.session.add(new_department)
        db.session.commit()
        flash('Department/Faculty added successfully!', 'success')
    return redirect(url_for('admin_dashboard'))




    try:
        msg = Message(
            subject=f'NOC Request #{request_number} - Rejected',
            recipients=[student_email],
            body=f"""
Dear Student,

Your NOC request #{request_number} has been rejected by one or more departments.
Please check your dashboard for details.

Best regards,
NOC System
            """
        )
        mail.send(msg)
    except Exception as e:
        print(f"Error sending rejection email: {e}")

@app.route('/download-noc/<request_number>/<roll_no>')
@login_required
def download_noc(request_number, roll_no):
    if not current_user.is_admin:
        # If a student tries to access this, redirect them to a contact admin page
        return redirect(url_for('contact_admin'))

    student = Student.query.filter_by(roll_no=roll_no).first()
    if not student:
        flash('Student not found!', 'error')
        return redirect(url_for('admin_dashboard'))

    noc_request = NOCRequest.query.filter_by(request_number=request_number, roll_no=roll_no).first_or_404()
    
    if not noc_request.completed or noc_request.status != 'approved':
        flash('NOC not ready for download!', 'error')
        return redirect(url_for('admin_dashboard'))

    logo_path = 'file:///' + os.path.join(app.root_path, 'static', 'logo3.png').replace('\\', '/')

    rendered_html = render_template('noc_certificate.html', noc_request=noc_request, student=student, logo_path=logo_path)
    pdf_content = HTML(string=rendered_html).write_pdf()

    response = make_response(pdf_content)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=NOC-{noc_request.request_number}-{noc_request.student.roll_no}.pdf'
    return response



@app.route('/contact_admin')
@login_required
def contact_admin():
    return render_template('contact_admin.html')



    # Specific fee details for Accounts (assuming these are part of accounts approval)
    # These coordinates need careful adjustment based on the actual table layout and dynamic content
    # For now, placing them relative to the Accounts row, but this might need a more robust table drawing logic.
    # Find the y_position for the Accounts row
    accounts_row_index = -1
    for i, dept_info in enumerate(departments_data):
        if dept_info["name"] == "Accounts":
            accounts_row_index = i
            break

    if accounts_row_index != -1:
        accounts_y_pos_start = height - 230 - (accounts_row_index * 20) # Y-position for Accounts row
        c.drawString(150, accounts_y_pos_start - 20, "Tuition Fee:")
        c.drawString(250, accounts_y_pos_start - 20, noc_request.tuition_fee if hasattr(noc_request, 'tuition_fee') else "N/A")
        c.drawString(150, accounts_y_pos_start - 40, "Bus Fee:")
        c.drawString(250, accounts_y_pos_start - 40, noc_request.bus_fee if hasattr(noc_request, 'bus_fee') else "N/A")
        c.drawString(150, accounts_y_pos_start - 60, "Hostel fee:")
        c.drawString(250, accounts_y_pos_start - 60, noc_request.hostel_fee if hasattr(noc_request, 'hostel_fee') else "N/A")
        c.drawString(150, accounts_y_pos_start - 80, "Other Fee:")
        c.drawString(250, accounts_y_pos_start - 80, noc_request.other_fee if hasattr(noc_request, 'other_fee') else "N/A")

    # Scholarship section
    # Adjust y_position for scholarship section to be below the departmental approvals and fee details
    scholarship_y_start = y_position - 100 # Start below the last departmental approval entry

    c.drawString(120, scholarship_y_start, "If Scholarship (RTF) Holder")
    c.drawString(70, scholarship_y_start - 20, "9.")
    c.drawString(120, scholarship_y_start - 20, "Scholarship Application No.")
    c.drawString(350, scholarship_y_start - 20, noc_request.scholarship_application_no if hasattr(noc_request, 'scholarship_application_no') else "")
    c.drawString(70, scholarship_y_start - 40, "10.")
    c.drawString(120, scholarship_y_start - 40, "Scholarship Status")
    c.drawString(120, scholarship_y_start - 50, "(Attach Status Report)")
    c.drawString(350, scholarship_y_start - 40, noc_request.scholarship_status if hasattr(noc_request, 'scholarship_status') else "")

    # Remarks and Signatures
    c.drawString(70, y_position - 90, "Remarks of the HoD (if any):")
    c.drawString(70, y_position - 130, "Head of the Department")
    c.drawString(280, y_position - 130, "Administrative Officer")
    c.drawString(480, y_position - 130, "PRINCIPAL")
    

    
    c.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"NOC-{noc_request.request_number}.pdf",
        mimetype='application/pdf'
    )

@app.route('/api/track/<request_number>')
@login_required
def api_track_request(request_number):
    noc_request = NOCRequest.query.filter_by(request_number=request_number).first_or_404()
    
    if noc_request.roll_no != current_user.roll_no:
        return jsonify({'error': 'Unauthorized'}), 401

    statuses = []
    for status in noc_request.statuses:
        statuses.append({
            'department': status.department.name,
            'status': status.status,
            'reason': status.reason,
            'updated_at': status.updated_at.strftime('%Y-%m-%d %H:%M:%S')
        })

    return jsonify({
        'request_number': noc_request.request_number,
        'status': noc_request.status,
        'completed': noc_request.completed,
        'statuses': statuses
    })

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

def init_db():
    with app.app_context():
        db.create_all()
        
        # Add default departments if not exists
        departments = [
            {'name': 'Training & Placement Cell', 'email': 'shivanipatturi22@gmail.com', 'head_name': 'TPO Head'},
            {'name': 'Library', 'email': 'kopperaanu7@gmail.com', 'head_name': 'Librarian'},
            {'name': 'IEEE', 'email': 'sahithyagandhe@gmail.com', 'head_name': 'IEEE Coordinator'},
            {'name': 'Sports', 'email': 'pasunuthiheshwanthini@gmail.com', 'head_name': 'Sports Director'},
            {'name': 'Mentor', 'email': 'poojithathikka98@gmail.com', 'head_name': 'Mentor Coordinator'}
        ]
        
        for dept_data in departments:
            if not Department.query.filter_by(name=dept_data['name']).first():
                dept = Department(**dept_data)
                db.session.add(dept)
        
        db.session.commit()

@app.route('/approve/<token>')
def approve_noc(token):
    noc_status = NOCStatus.query.filter_by(approval_token=token).first_or_404()
    
    if noc_status.status != 'pending':
        return "This request has already been processed.", 400
    
    noc_status.status = 'approved'
    noc_status.approved_by = f"Department {noc_status.department.name}"
    noc_status.updated_at = datetime.datetime.utcnow()
    
    noc_request = noc_status.noc_request
    
    # Check if all departments have approved
    all_approved = all(s.status == 'approved' for s in noc_request.statuses)
    any_rejected = any(s.status == 'rejected' for s in noc_request.statuses)
    
    if all_approved:
        noc_request.status = 'approved'
        noc_request.completed = True
        send_completion_email(noc_request.student.email, noc_request.request_number, current_user.email)
    elif any_rejected:
        noc_request.status = 'rejected'
        noc_request.completed = True
        send_rejection_email(noc_request.student.email, noc_request.request_number)
    
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('status_update', {
        'request_id': noc_request.id,
        'status': 'approved',
        'department': noc_status.department.name
    })
    
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
        <h2 style="color: green;">Request Approved Successfully!</h2>
        <p>NOC Request #{noc_request.request_number} for {noc_request.student.full_name} has been approved by {noc_status.department.name}.</p>
        <p>You can close this window now.</p>
    </body>
    </html>
    """

@app.route('/reject/<token>')
def reject_noc(token):
    noc_status = NOCStatus.query.filter_by(approval_token=token).first_or_404()
    
    if noc_status.status != 'pending':
        return "This request has already been processed.", 400
    
    reason = request.args.get('reason', '')
    
    if not reason:
        return f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
            <h2 style="color: red;">Reject NOC Request</h2>
            <p>NOC Request #{noc_status.noc_request.request_number} for {noc_status.noc_request.student.full_name}</p>
            <p>Department: {noc_status.department.name}</p>
            
            <form action="{url_for('reject_noc', token=token)}" method="GET">
                <div style="margin: 20px 0;">
                    <label for="reason">Reason for rejection:</label><br>
                    <textarea name="reason" id="reason" rows="4" style="width: 100%; padding: 10px;" required></textarea>
                </div>
                <button type="submit" style="background-color: red; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;">Submit Rejection</button>
                <a href="{url_for('index')}" style="margin-left: 10px; padding: 10px 20px; background-color: #ccc; color: black; text-decoration: none; border-radius: 5px;">Cancel</a>
            </form>
        </body>
        </html>
        """
    
    noc_status.status = 'rejected'
    noc_status.reason = reason
    noc_status.approved_by = f"Department {noc_status.department.name}"
    noc_status.updated_at = datetime.utcnow()
    
    noc_request = noc_status.noc_request
    noc_request.status = 'rejected'
    noc_request.completed = True
    
    send_rejection_email(noc_request.student.email, noc_request.request_number)
    
    db.session.commit()
    
    # Emit real-time update
    socketio.emit('status_update', {
        'request_id': noc_request.id,
        'status': 'rejected',
        'department': noc_status.department.name
    })
    
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; text-align: center; margin-top: 50px;">
        <h2 style="color: red;">Request Rejected</h2>
        <p>NOC Request #{noc_request.request_number} for {noc_request.student.full_name} has been rejected by {noc_status.department.name}.</p>
        <p>Reason: {reason}</p>
        <p>You can close this window now.</p>
    </body>
    </html>
    """

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        initialize_admin() # Ensure admin user is created
        initialize_departments() # Initialize faculty on startup
    socketio.run(app, debug=True, host='0.0.0.0', port=10000)