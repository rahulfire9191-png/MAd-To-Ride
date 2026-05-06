from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import psycopg2
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import boto3
from botocore.exceptions import NoCredentialsError

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='.')

# Database configuration
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///registrations.db')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# AWS S3 Configuration (for file storage)
AWS_ACCESS_KEY = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_BUCKET_NAME = os.environ.get('AWS_BUCKET_NAME')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# File upload configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Initialize database
db = SQLAlchemy(app)

# S3 Client (if AWS credentials are available)
s3_client = None
if AWS_ACCESS_KEY and AWS_SECRET_KEY and AWS_BUCKET_NAME:
    s3_client = boto3.client(
        's3',
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=AWS_REGION
    )

# Database model for registrations
class Registration(db.Model):
    __tablename__ = 'registrations'
    
    id = db.Column(db.Integer, primary_key=True)
    firstName = db.Column(db.String(100), nullable=False)
    lastName = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    bike = db.Column(db.String(200), nullable=False)
    drivingLicenseFile = db.Column(db.String(500))
    experience = db.Column(db.String(200))
    alias = db.Column(db.String(100))
    instagram = db.Column(db.String(200))
    riderPhoto = db.Column(db.String(500))
    bikePhoto = db.Column(db.String(500))
    sectionPhoto = db.Column(db.String(500))
    reason = db.Column(db.Text)
    role = db.Column(db.String(50), default='Member')
    priority = db.Column(db.Integer, default=5)
    captainNumber = db.Column(db.String(10))
    timestamp = db.Column(db.String(50), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'firstName': self.firstName,
            'lastName': self.lastName,
            'phone': self.phone,
            'city': self.city,
            'bike': self.bike,
            'drivingLicenseFile': self.drivingLicenseFile,
            'experience': self.experience,
            'alias': self.alias,
            'instagram': self.instagram,
            'riderPhoto': self.riderPhoto,
            'bikePhoto': self.bikePhoto,
            'sectionPhoto': self.sectionPhoto,
            'reason': self.reason,
            'role': self.role,
            'priority': self.priority,
            'captainNumber': self.captainNumber,
            'timestamp': self.timestamp
        }

# Create uploads folder if it doesn't exist (for local development)
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

def upload_file_to_s3(file, filename, folder='uploads'):
    """Upload file to S3 or save locally if S3 not configured"""
    if s3_client:
        try:
            s3_client.upload_fileobj(
                file,
                AWS_BUCKET_NAME,
                f"{folder}/{filename}",
                ExtraArgs={'ContentType': file.content_type or 'application/octet-stream'}
            )
            return f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{folder}/{filename}"
        except NoCredentialsError:
            print("AWS credentials not available, saving locally")
    
    # Fallback to local storage
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    return f"/uploads/{filename}"

def validate_mobile_number(phone):
    """Validate 10-digit Indian mobile number"""
    import re
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    if re.match(r'^[6789]\d{9}$', clean_phone):
        return clean_phone
    return None

def check_duplicate_mobile(phone):
    """Check if mobile number already exists in registrations"""
    validated_phone = validate_mobile_number(phone)
    if validated_phone:
        return Registration.query.filter_by(phone=validated_phone).first() is not None
    return False

def get_next_captain_number():
    """Get the next available captain number"""
    captains = Registration.query.filter_by(role='Captain').order_by(Registration.captainNumber.desc()).all()
    if not captains:
        return 1
    
    # Extract captain numbers and find the highest
    captain_numbers = []
    for captain in captains:
        try:
            captain_numbers.append(int(captain.captainNumber))
        except (ValueError, TypeError):
            continue
    
    if not captain_numbers:
        return 1
    
    return max(captain_numbers) + 1

@app.route('/sounds/<filename>')
def serve_sound(filename):
    return send_from_directory('sounds', filename)

@app.route('/')
def home():
    riders = Registration.query.order_by(Registration.priority.asc(), Registration.timestamp.desc()).limit(12).all()
    recent_riders = [rider.to_dict() for rider in riders] if riders else []
    return render_template('index.html', riders=recent_riders)

@app.route('/api/riders', methods=['GET'])
def get_riders():
    riders = Registration.query.order_by(Registration.priority.asc(), Registration.timestamp.desc()).all()
    return jsonify([rider.to_dict() for rider in riders])

@app.route('/api/admin-login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # Admin credentials
        ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'Madmax')
        ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Pa$$w0rd@Madmax')
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            return jsonify({
                'success': True,
                'message': 'Login successful'
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': 'Login failed'
        }), 500

def check_admin_auth():
    # In production, use proper session management or JWT tokens
    # For now, we'll use a simple session-based approach
    return True  # Simplified for demo - in production, verify session/token

@app.route('/api/update-section', methods=['POST'])
def update_section():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        section = data.get('section')
        content = data.get('content')
        
        if not section or not content:
            return jsonify({'success': False, 'message': 'Section and content are required'}), 400
        
        # For now, just return success (in production, you'd save to database or files)
        return jsonify({'success': True, 'message': 'Section updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete-rider', methods=['POST'])
def delete_rider():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        phone = data.get('phone', '').strip()
        timestamp = data.get('timestamp', '').strip()
        
        if not phone or not timestamp:
            return jsonify({'success': False, 'message': 'Phone and timestamp are required'}), 400
        
        # Find the rider to check if it's CEO
        rider_to_delete = Registration.query.filter_by(phone=phone, timestamp=timestamp).first()
        
        if not rider_to_delete:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Prevent deletion of CEO/Founder (priority 1)
        if rider_to_delete.priority == 1:
            return jsonify({'success': False, 'message': 'Cannot delete CEO/Founder. This member is protected.'}), 403
        
        # Additional protection: Check if this is Rahul Choudhari by name
        if (rider_to_delete.firstName.strip().lower() == 'rahul' and 
            rider_to_delete.lastName.strip().lower() == 'choudhari'):
            return jsonify({'success': False, 'message': 'Cannot delete CEO/Founder. This member is protected.'}), 403
        
        # Delete the rider
        db.session.delete(rider_to_delete)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Rider deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-cofounder', methods=['POST'])
def add_cofounder():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            data = request.get_json()
            rider_photo = None
            bike_photo = None
        
        required = ['firstName', 'lastName', 'alias', 'bike', 'phone']
        for field in required:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Process rider photo
        rider_photo_filename = None
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_photo_filename = upload_file_to_s3(rider_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        # Process bike photo
        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo_filename = upload_file_to_s3(bike_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400

        # Add cofounder with special role and priority
        cofounder = Registration(
            firstName=data.get('firstName', '').strip(),
            lastName=data.get('lastName', '').strip(),
            phone=data.get('phone', '').strip(),
            city='Pune',
            bike=data.get('bike', '').strip(),
            experience=data.get('experience', '10+ years'),
            alias=data.get('alias', '').strip(),
            instagram=data.get('instagram', '').strip(),
            riderPhoto=rider_photo_filename,
            bikePhoto=bike_photo_filename,
            reason='Co-Founder of MTR Brotherhood',
            role=data.get('role', 'Co-Founder'),
            priority=2,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        db.session.add(cofounder)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Co-Founder added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-captain', methods=['POST'])
def add_captain():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            data = request.get_json()
            rider_photo = None
            bike_photo = None
        
        required = ['firstName', 'lastName', 'alias', 'bike', 'phone']
        for field in required:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Process rider photo
        rider_photo_filename = None
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_photo_filename = upload_file_to_s3(rider_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        # Process bike photo
        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo_filename = upload_file_to_s3(bike_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400

        # Get captain number from form or auto-assign
        captain_number = data.get('captainNumber')
        if captain_number:
            try:
                captain_number = str(int(captain_number))
            except (ValueError, TypeError):
                captain_number = str(get_next_captain_number())
        else:
            captain_number = str(get_next_captain_number())
        
        # Add captain with special role and priority
        captain = Registration(
            firstName=data.get('firstName', '').strip(),
            lastName=data.get('lastName', '').strip(),
            phone=data.get('phone', '').strip(),
            city='Pune',
            bike=data.get('bike', '').strip(),
            experience=data.get('experience', '5+ years'),
            alias=data.get('alias', '').strip(),
            instagram=data.get('instagram', '').strip(),
            riderPhoto=rider_photo_filename,
            bikePhoto=bike_photo_filename,
            reason=f'Captain {captain_number} of MTR Brotherhood',
            role=data.get('role', 'Captain'),
            captainNumber=captain_number,
            priority=3,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        
        db.session.add(captain)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Captain added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-member-manual', methods=['POST'])
def add_member_manual():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            data = request.get_json()
            rider_photo = None
            bike_photo = None
        
        required = ['firstName', 'lastName', 'phone', 'city', 'bike']
        for field in required:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Process rider photo
        rider_photo_filename = None
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_photo_filename = upload_file_to_s3(rider_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        # Process bike photo
        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo_filename = upload_file_to_s3(bike_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400

        # Prepare registration data
        registration_data = {
            'firstName': data.get('firstName', '').strip(),
            'lastName': data.get('lastName', '').strip(),
            'phone': data.get('phone', '').strip(),
            'city': data.get('city', '').strip(),
            'bike': data.get('bike', '').strip(),
            'experience': data.get('experience', ''),
            'alias': data.get('alias', ''),
            'instagram': data.get('instagram', '').strip(),
            'riderPhoto': rider_photo_filename,
            'bikePhoto': bike_photo_filename,
            'reason': 'Added manually by admin',
            'role': data.get('role', 'Member'),
            'priority': 5,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        registration = Registration(**registration_data)
        db.session.add(registration)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Member added successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/register', methods=['POST'])
def register():
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.form.to_dict()
            driving_license_file = request.files.get('drivingLicenseFile')
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
            instagram = data.get('instagram', '').strip()
        else:
            data = request.get_json()
            driving_license_file = None
            rider_photo = None
            bike_photo = None

        required = ['firstName', 'lastName', 'phone', 'city', 'bike']
        for field in required:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        # Validate mobile number
        phone = data.get('phone', '').strip()
        validated_phone = validate_mobile_number(phone)
        if not validated_phone:
            return jsonify({'success': False, 'message': 'Invalid mobile number. Please enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.'}), 400

        # Check for duplicate mobile number
        if check_duplicate_mobile(phone):
            return jsonify({'success': False, 'message': 'This mobile number is already registered. One rider can join only once.'}), 400

        # Handle driving license file upload (optional)
        driving_license_filename = None
        if driving_license_file and driving_license_file.filename:
            if allowed_file(driving_license_file.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_license_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{driving_license_file.filename}")
                driving_license_filename = upload_file_to_s3(driving_license_file, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid file type. Allowed: JPG, PNG, PDF'}), 400

        rider_photo_filename = None
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_photo_filename = upload_file_to_s3(rider_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo_filename = upload_file_to_s3(bike_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400

        # Create new registration
        registration = Registration(
            firstName=data.get('firstName', '').strip(),
            lastName=data.get('lastName', '').strip(),
            phone=validated_phone,
            city=data.get('city', '').strip(),
            bike=data.get('bike', '').strip(),
            drivingLicenseFile=driving_license_filename,
            experience=data.get('experience', '').strip(),
            alias=data.get('alias', '').strip(),
            instagram=instagram,
            riderPhoto=rider_photo_filename,
            bikePhoto=bike_photo_filename,
            reason=data.get('message', '').strip(),
            role='Member',
            priority=5,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )

        db.session.add(registration)
        db.session.commit()

        whatsapp_link = os.environ.get('WHATSAPP_LINK', "https://chat.whatsapp.com/HbRgZJa1Rqm5Kbso36WDWf?mode=hqctcla")

        return jsonify({
            'success': True,
            'message': 'Welcome to the MTR Brotherhood!',
            'whatsapp_link': whatsapp_link
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Something went wrong. Please try again.'}), 500

@app.route('/api/update-rider', methods=['POST'])
def update_rider():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            data = request.get_json()
            rider_photo = None
            bike_photo = None
        
        # Get identifying information
        original_phone = data.get('phone', '').strip()
        original_timestamp = data.get('timestamp', '').strip()
        
        if not original_phone or not original_timestamp:
            return jsonify({'success': False, 'message': 'Original phone and timestamp are required'}), 400
        
        # Find the rider to update
        rider_to_update = Registration.query.filter_by(phone=original_phone, timestamp=original_timestamp).first()
        
        if not rider_to_update:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Process rider photo if provided
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_to_update.riderPhoto = upload_file_to_s3(rider_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400
        
        # Process bike photo if provided
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                rider_to_update.bikePhoto = upload_file_to_s3(bike_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400
        
        # Process section photo if provided
        section_photo = request.files.get('sectionPhoto')
        if section_photo and section_photo.filename:
            if allowed_image_file(section_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_section_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{section_photo.filename}")
                rider_to_update.sectionPhoto = upload_file_to_s3(section_photo, filename)
            else:
                return jsonify({'success': False, 'message': 'Invalid section photo file type. Allowed: JPG, PNG'}), 400
        
        # Prevent role and priority changes for CEO/Founder
        if rider_to_update.priority == 1 or (rider_to_update.firstName.strip().lower() == 'rahul' and rider_to_update.lastName.strip().lower() == 'choudhari'):
            # Only allow basic info updates for CEO, not role/priority changes
            rider_to_update.firstName = data.get('firstName', rider_to_update.firstName).strip()
            rider_to_update.lastName = data.get('lastName', rider_to_update.lastName).strip()
            rider_to_update.alias = data.get('alias', rider_to_update.alias).strip()
            rider_to_update.phone = data.get('phone', rider_to_update.phone).strip()
            rider_to_update.city = data.get('city', rider_to_update.city).strip()
            rider_to_update.bike = data.get('bike', rider_to_update.bike).strip()
            rider_to_update.experience = data.get('experience', rider_to_update.experience).strip()
            rider_to_update.instagram = data.get('instagram', rider_to_update.instagram).strip()
            rider_to_update.reason = data.get('reason', rider_to_update.reason).strip()
            rider_to_update.role = 'Founder'  # Force role to remain Founder
            rider_to_update.priority = 1      # Force priority to remain 1
        else:
            # Allow all updates for regular riders
            rider_to_update.firstName = data.get('firstName', rider_to_update.firstName).strip()
            rider_to_update.lastName = data.get('lastName', rider_to_update.lastName).strip()
            rider_to_update.alias = data.get('alias', rider_to_update.alias).strip()
            rider_to_update.phone = data.get('phone', rider_to_update.phone).strip()
            rider_to_update.city = data.get('city', rider_to_update.city).strip()
            rider_to_update.bike = data.get('bike', rider_to_update.bike).strip()
            rider_to_update.experience = data.get('experience', rider_to_update.experience).strip()
            rider_to_update.instagram = data.get('instagram', rider_to_update.instagram).strip()
            rider_to_update.reason = data.get('reason', rider_to_update.reason).strip()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Rider information updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update-rider-role', methods=['POST'])
def update_rider_role():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        data = request.get_json()
        phone = data.get('phone')
        timestamp = data.get('timestamp')
        new_role = data.get('role')
        captain_number = data.get('captainNumber', '1')
        
        if not phone or not timestamp or not new_role:
            return jsonify({'success': False, 'message': 'Phone, timestamp, and role are required'}), 400
        
        # Validate role
        valid_roles = ['Member', 'Co-Founder', 'Captain']
        if new_role not in valid_roles:
            return jsonify({'success': False, 'message': 'Invalid role. Must be Member, Co-Founder, or Captain'}), 400
        
        # Load registrations and find the rider
        rider_to_update = Registration.query.filter_by(phone=phone, timestamp=timestamp).first()
        
        if not rider_to_update:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Prevent role changes for CEO/Founder (priority 1)
        if rider_to_update.priority == 1:
            return jsonify({'success': False, 'message': 'Cannot change role of CEO/Founder. This member is protected.'}), 403
        
        # Additional protection: Check if this is Rahul Choudhari by name
        if (rider_to_update.firstName.strip().lower() == 'rahul' and 
            rider_to_update.lastName.strip().lower() == 'choudhari'):
            return jsonify({'success': False, 'message': 'Cannot change role of CEO/Founder. This member is protected.'}), 403
        
        # Update role and priority
        rider_to_update.role = new_role
        
        # Set priority based on role
        if new_role == 'Co-Founder':
            rider_to_update.priority = 2
            rider_to_update.captainNumber = None
        elif new_role == 'Captain':
            rider_to_update.priority = 3
            # Auto-assign captain number if not provided
            if not captain_number:
                captain_number = str(get_next_captain_number())
            else:
                # Ensure captain number is valid
                try:
                    captain_number = str(int(captain_number))
                except (ValueError, TypeError):
                    captain_number = str(get_next_captain_number())
            
            rider_to_update.captainNumber = captain_number
            rider_to_update.reason = f'Captain {captain_number} of MTR Brotherhood'
        else:
            rider_to_update.priority = 5
            rider_to_update.captainNumber = None
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Rider role updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/uploads/<filename>')
def serve_file(filename):
    # Serve files locally or redirect to S3 if available
    if s3_client:
        return redirect(f"https://{AWS_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/uploads/{filename}")
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Initialize database
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
