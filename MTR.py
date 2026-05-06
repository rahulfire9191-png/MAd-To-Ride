from flask import Flask, render_template, request, jsonify, send_from_directory
import json
import os
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__, template_folder='templates', static_folder='.')

REGISTRATIONS_FILE = 'registrations.json'
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_image_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg'}

def validate_mobile_number(phone):
    """Validate 10-digit Indian mobile number"""
    import re
    # Remove any spaces, dashes, or parentheses
    clean_phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    # Check if it's exactly 10 digits and starts with 6,7,8, or 9 (Indian mobile numbers)
    if re.match(r'^[6789]\d{9}$', clean_phone):
        return clean_phone
    return None

def validate_pan_number(pan):
    """Validate Indian PAN card number format"""
    import re
    # PAN format: 5 letters, 4 digits, 1 letter (e.g., ABCDE1234F)
    if re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan.upper()):
        return pan.upper()
    return None

def validate_aadhar_number(aadhar):
    """Validate Indian Aadhar card number format"""
    import re
    # Aadhar format: 12 digits (can have spaces or hyphens)
    clean_aadhar = re.sub(r'[\s\-]', '', aadhar)
    if re.match(r'^\d{12}$', clean_aadhar):
        return clean_aadhar
    return None

def check_duplicate_mobile(phone):
    """Check if mobile number already exists in registrations"""
    registrations = load_registrations()
    clean_phone = validate_mobile_number(phone)
    if clean_phone:
        for reg in registrations:
            if validate_mobile_number(reg.get('phone', '')) == clean_phone:
                return True
    return False

def get_next_captain_number():
    """Get the next available captain number"""
    registrations = load_registrations()
    captain_numbers = []
    
    for reg in registrations:
        if reg.get('role') == 'Captain' and reg.get('captainNumber'):
            try:
                captain_numbers.append(int(reg.get('captainNumber')))
            except (ValueError, TypeError):
                continue
    
    if not captain_numbers:
        return 1
    
    # Find the highest captain number and return next one
    return max(captain_numbers) + 1

def load_registrations():
    if os.path.exists(REGISTRATIONS_FILE):
        try:
            with open(REGISTRATIONS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_registration(data):
    registrations = load_registrations()
    data['id'] = len(registrations) + 1
    data['timestamp'] = datetime.now().strftime('%d %b %Y')
    registrations.append(data)
    
    with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(registrations, f, indent=2, ensure_ascii=False)

@app.route('/sounds/<filename>')
def serve_sound(filename):
    return send_from_directory('sounds', filename)

@app.route('/')
def home():
    riders = load_registrations()
    recent_riders = riders[-12:] if riders else []   # Show latest 12 joined riders
    return render_template('index.html', riders=recent_riders)

@app.route('/api/riders', methods=['GET'])
def get_riders():
    riders = load_registrations()
    return jsonify(riders)

@app.route('/api/admin-login', methods=['POST'])
def admin_login():
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        # Admin credentials
        ADMIN_USERNAME = 'Madmax'
        ADMIN_PASSWORD = 'Pa$$w0rd@Madmax'
        
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
        
        # Load registrations
        registrations = load_registrations()
        
        # Find the rider to check if it's CEO
        rider_to_delete = None
        for rider in registrations:
            if (rider.get('phone', '').strip() == phone and 
                rider.get('timestamp', '').strip() == timestamp):
                rider_to_delete = rider
                break
        
        if not rider_to_delete:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Prevent deletion of CEO/Founder (priority 1)
        if rider_to_delete.get('priority') == 1:
            return jsonify({'success': False, 'message': 'Cannot delete CEO/Founder. This member is protected.'}), 403
        
        # Find and remove the rider
        updated_registrations = []
        rider_found = False
        for rider in registrations:
            if (rider.get('phone', '').strip() == phone and 
                rider.get('timestamp', '').strip() == timestamp):
                rider_found = True
                # Don't add this rider to updated list (effectively deleting it)
            else:
                updated_registrations.append(rider)
        
        if not rider_found:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Save updated registrations
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(updated_registrations, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Rider deleted successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-cofounder', methods=['POST'])
def add_cofounder():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            # Handle form data with file upload
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            # Handle JSON data (backward compatibility)
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
                rider_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                rider_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        # Process bike photo
        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bike_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400

        # Add cofounder with special role and priority
        cofounder_data = {
            'firstName': data.get('firstName', '').strip(),
            'lastName': data.get('lastName', '').strip(),
            'phone': data.get('phone', '').strip(),
            'city': 'Pune',  # Default city for cofounder
            'bike': data.get('bike', '').strip(),
            'experience': data.get('experience', '10+ years'),
            'alias': data.get('alias', '').strip(),
            'instagram': data.get('instagram', '').strip(),
            'riderPhoto': rider_photo_filename,
            'bikePhoto': bike_photo_filename,
            'reason': 'Co-Founder of MTR Brotherhood',
            'role': data.get('role', 'Co-Founder'),
            'priority': 2,  # High priority for display
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        registrations = load_registrations()
        registrations.insert(1, cofounder_data)  # Insert after founder (index 0)
        
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(registrations, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Co-Founder added successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-captain', methods=['POST'])
def add_captain():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            # Handle form data with file upload
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            # Handle JSON data (backward compatibility)
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
                rider_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                rider_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        # Process bike photo
        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bike_photo_filename = filename
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
        captain_data = {
            'firstName': data.get('firstName', '').strip(),
            'lastName': data.get('lastName', '').strip(),
            'phone': data.get('phone', '').strip(),
            'city': 'Pune',  # Default city for captain
            'bike': data.get('bike', '').strip(),
            'experience': data.get('experience', '5+ years'),
            'alias': data.get('alias', '').strip(),
            'instagram': data.get('instagram', '').strip(),
            'riderPhoto': rider_photo_filename,
            'bikePhoto': bike_photo_filename,
            'reason': f'Captain {captain_number} of MTR Brotherhood',
            'role': data.get('role', 'Captain'),
            'captainNumber': captain_number,
            'priority': 3,  # Medium-high priority for display
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        registrations = load_registrations()
        
        # Sort by priority first, then by captain number for captains
        registrations.sort(key=lambda x: (x.get('priority', 5), 
                                       int(x.get('captainNumber', 0)) if x.get('role') == 'Captain' else 0,
                                       x.get('timestamp', '')))
        
        # Find correct position to insert captain (after founder and cofounders, in captain order)
        insert_position = 0
        for i, reg in enumerate(registrations):
            if reg.get('priority', 5) < 3:  # Founder (1) and Co-Founders (2)
                continue
            elif reg.get('role') == 'Captain':
                if int(reg.get('captainNumber', 0)) > int(captain_number):
                    insert_position = i
                    break
            else:
                insert_position = i
                break
        
        registrations.insert(insert_position, captain_data)
        
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(registrations, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Captain added successfully'})
        
    except Exception as e:
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
        registrations = load_registrations()
        rider_found = False
        
        for i, reg in enumerate(registrations):
            if reg.get('phone') == phone and reg.get('timestamp') == timestamp:
                rider_found = True
                
                # Prevent role changes for CEO/Founder (priority 1)
                if reg.get('priority') == 1:
                    return jsonify({'success': False, 'message': 'Cannot change role of CEO/Founder. This member is protected.'}), 403
                
                # Additional protection: Check if this is Rahul Choudhari by name
                if (reg.get('firstName', '').strip().lower() == 'rahul' and 
                    reg.get('lastName', '').strip().lower() == 'choudhari'):
                    return jsonify({'success': False, 'message': 'Cannot change role of CEO/Founder. This member is protected.'}), 403
                
                # Update role and priority
                registrations[i]['role'] = new_role
                
                # Set priority based on role
                if new_role == 'Co-Founder':
                    registrations[i]['priority'] = 2
                    # Remove captainNumber if no longer a captain
                    if 'captainNumber' in registrations[i]:
                        del registrations[i]['captainNumber']
                elif new_role == 'Captain':
                    registrations[i]['priority'] = 3
                    # Auto-assign captain number if not provided
                    if not captain_number:
                        captain_number = str(get_next_captain_number())
                    else:
                        # Ensure captain number is valid
                        try:
                            captain_number = str(int(captain_number))
                        except (ValueError, TypeError):
                            captain_number = str(get_next_captain_number())
                    
                    registrations[i]['captainNumber'] = captain_number
                    registrations[i]['reason'] = f'Captain {captain_number} of MTR Brotherhood'
                else:
                    registrations[i]['priority'] = 5
                    # Remove captainNumber if no longer a captain
                    if 'captainNumber' in registrations[i]:
                        del registrations[i]['captainNumber']
                
                break
        
        if not rider_found:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Sort registrations by priority, then by captain number for captains, then by timestamp
        registrations.sort(key=lambda x: (x.get('priority', 5), 
                                       int(x.get('captainNumber', 0)) if x.get('role') == 'Captain' else 0,
                                       x.get('timestamp', '')))
        
        # Save updated registrations
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(registrations, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Rider role updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-member-manual', methods=['POST'])
def add_member_manual():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            # Handle form data with file upload
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            # Handle JSON data (backward compatibility)
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
                rider_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                rider_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        # Process bike photo
        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bike_photo_filename = filename
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
            'priority': 5,  # Normal priority for display
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        registrations = load_registrations()
        registrations.append(registration_data)
        
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(registrations, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Member added successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/register', methods=['POST'])
def register():
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            # Handle form data with file upload
            data = request.form.to_dict()
            driving_license_file = request.files.get('drivingLicenseFile')
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
            instagram = data.get('instagram', '').strip()
        else:
            # Handle JSON data (backward compatibility)
            data = request.get_json()
            driving_license_file = None
            bike_photo = None

        required = ['firstName', 'lastName', 'phone', 'city', 'bike', 'idProofType', 'idProofNumber']
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

        # Validate ID proof based on type
        id_proof_type = data.get('idProofType', '').strip().lower()
        id_proof_number = data.get('idProofNumber', '').strip()
        
        if id_proof_type == 'pan':
            validated_pan = validate_pan_number(id_proof_number)
            if not validated_pan:
                return jsonify({'success': False, 'message': 'Invalid PAN card number. Please enter a valid PAN in format ABCDE1234F.'}), 400
        elif id_proof_type == 'aadhar':
            validated_aadhar = validate_aadhar_number(id_proof_number)
            if not validated_aadhar:
                return jsonify({'success': False, 'message': 'Invalid Aadhar card number. Please enter a valid 12-digit Aadhar number.'}), 400
        elif id_proof_type == 'voter':
            # Basic validation for voter ID (can vary by state, so basic length check)
            if len(id_proof_number.replace(' ', '')) < 10 or len(id_proof_number.replace(' ', '')) > 20:
                return jsonify({'success': False, 'message': 'Invalid Voter ID number. Please enter a valid Voter ID.'}), 400

        # Handle driving license file upload (mandatory)
        driving_license_filename = None
        if driving_license_file and driving_license_file.filename:
            if allowed_file(driving_license_file.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_license_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{driving_license_file.filename}")
                driving_license_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                driving_license_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid file type. Allowed: JPG, PNG, PDF'}), 400
        else:
            return jsonify({'success': False, 'message': 'Driving license is required'}), 400

        rider_photo_filename = None
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                rider_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400

        bike_photo_filename = None
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bike_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400

        save_registration({
            'firstName': data.get('firstName', '').strip(),
            'lastName': data.get('lastName', '').strip(),
            'phone': validated_phone,  # Use validated phone number
            'city': data.get('city', '').strip(),
            'bike': data.get('bike', '').strip(),
            'idProofType': data.get('idProofType', '').strip(),
            'idProofNumber': id_proof_number.upper() if id_proof_type == 'pan' else id_proof_number.replace(' ', '').replace('-', ''),  # Normalize ID proof
            'drivingLicenseFile': driving_license_filename,
            'experience': data.get('experience', '').strip(),
            'alias': data.get('alias', '').strip(),
            'instagram': instagram,
            'riderPhoto': rider_photo_filename,
            'bikePhoto': bike_photo_filename,
            'reason': data.get('message', '').strip()
        })

        whatsapp_link = "https://chat.whatsapp.com/HbRgZJa1Rqm5Kbso36WDWf?mode=hqctcla"

        return jsonify({
            'success': True,
            'message': 'Welcome to the MTR Brotherhood!',
            'whatsapp_link': whatsapp_link
        })

    except Exception as e:
        return jsonify({'success': False, 'message': 'Something went wrong. Please try again.'}), 500

@app.route('/api/update-rider', methods=['POST'])
def update_rider():
    if not check_admin_auth():
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    try:
        # Check if form data or JSON
        if request.content_type.startswith('multipart/form-data'):
            # Handle form data with file upload
            data = request.form.to_dict()
            rider_photo = request.files.get('riderPhoto')
            bike_photo = request.files.get('bikePhoto')
        else:
            # Handle JSON data (backward compatibility)
            data = request.get_json()
            rider_photo = None
            bike_photo = None
        
        # Get identifying information
        original_phone = data.get('phone', '').strip()
        original_timestamp = data.get('timestamp', '').strip()
        
        if not original_phone or not original_timestamp:
            return jsonify({'success': False, 'message': 'Original phone and timestamp are required'}), 400
        
        # Load registrations
        registrations = load_registrations()
        
        # Find the rider to update
        rider_index = None
        for i, rider in enumerate(registrations):
            if (rider.get('phone', '').strip() == original_phone and 
                rider.get('timestamp', '').strip() == original_timestamp):
                rider_index = i
                break
        
        if rider_index is None:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404
        
        # Process rider photo if provided
        rider_photo_filename = registrations[rider_index].get('riderPhoto')  # Keep existing photo by default
        if rider_photo and rider_photo.filename:
            if allowed_image_file(rider_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rider_photo.filename}")
                rider_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                rider_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid photo file type. Allowed: JPG, PNG'}), 400
        
        # Process bike photo if provided
        bike_photo_filename = registrations[rider_index].get('bikePhoto')  # Keep existing photo by default
        if bike_photo and bike_photo.filename:
            if allowed_image_file(bike_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_bike_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{bike_photo.filename}")
                bike_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                bike_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid bike photo file type. Allowed: JPG, PNG'}), 400
        
        # Process section photo if provided
        section_photo_filename = registrations[rider_index].get('sectionPhoto')  # Keep existing photo by default
        section_photo = request.files.get('sectionPhoto')
        if section_photo and section_photo.filename:
            if allowed_image_file(section_photo.filename):
                filename = secure_filename(f"{data.get('firstName', '')}_{data.get('lastName', '')}_section_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{section_photo.filename}")
                section_photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                section_photo_filename = filename
            else:
                return jsonify({'success': False, 'message': 'Invalid section photo file type. Allowed: JPG, PNG'}), 400
        
        # Prevent role and priority changes for CEO/Founder
        rider_data = registrations[rider_index]
        
        # Additional protection: Check if this is Rahul Choudhari by name (even if priority was changed)
        if (rider_data.get('firstName', '').strip().lower() == 'rahul' and 
            rider_data.get('lastName', '').strip().lower() == 'choudhari'):
            # Only allow basic info updates for CEO, not role/priority changes
            registrations[rider_index].update({
                'firstName': data.get('firstName', rider_data.get('firstName', '')).strip(),
                'lastName': data.get('lastName', rider_data.get('lastName', '')).strip(),
                'alias': data.get('alias', rider_data.get('alias', '')).strip(),
                'phone': data.get('phone', rider_data.get('phone', '')).strip(),
                'city': data.get('city', rider_data.get('city', '')).strip(),
                'bike': data.get('bike', rider_data.get('bike', '')).strip(),
                'experience': data.get('experience', rider_data.get('experience', '')).strip(),
                'instagram': data.get('instagram', rider_data.get('instagram', '')).strip(),
                'reason': data.get('reason', rider_data.get('reason', '')).strip(),
                'riderPhoto': rider_photo_filename,
                'bikePhoto': bike_photo_filename,
                'sectionPhoto': section_photo_filename,
                'role': 'Founder',  # Force role to remain Founder
                'priority': 1        # Force priority to remain 1
            })
        elif rider_data.get('priority') == 1:
            # Only allow basic info updates for CEO, not role/priority changes
            registrations[rider_index].update({
                'firstName': data.get('firstName', rider_data.get('firstName', '')).strip(),
                'lastName': data.get('lastName', rider_data.get('lastName', '')).strip(),
                'alias': data.get('alias', rider_data.get('alias', '')).strip(),
                'phone': data.get('phone', rider_data.get('phone', '')).strip(),
                'city': data.get('city', rider_data.get('city', '')).strip(),
                'bike': data.get('bike', rider_data.get('bike', '')).strip(),
                'experience': data.get('experience', rider_data.get('experience', '')).strip(),
                'instagram': data.get('instagram', rider_data.get('instagram', '')).strip(),
                'reason': data.get('reason', rider_data.get('reason', '')).strip(),
                'riderPhoto': rider_photo_filename,
                'bikePhoto': bike_photo_filename,
                'sectionPhoto': section_photo_filename,
                'role': 'Founder',  # Force role to remain Founder
                'priority': 1        # Force priority to remain 1
            })
        else:
            # Allow all updates for regular riders
            registrations[rider_index].update({
                'firstName': data.get('firstName', registrations[rider_index].get('firstName', '')).strip(),
                'lastName': data.get('lastName', registrations[rider_index].get('lastName', '')).strip(),
                'alias': data.get('alias', registrations[rider_index].get('alias', '')).strip(),
                'phone': data.get('phone', registrations[rider_index].get('phone', '')).strip(),
                'city': data.get('city', registrations[rider_index].get('city', '')).strip(),
                'bike': data.get('bike', registrations[rider_index].get('bike', '')).strip(),
                'experience': data.get('experience', registrations[rider_index].get('experience', '')).strip(),
                'instagram': data.get('instagram', registrations[rider_index].get('instagram', '')).strip(),
                'reason': data.get('reason', registrations[rider_index].get('reason', '')).strip(),
                'riderPhoto': rider_photo_filename,
                'bikePhoto': bike_photo_filename,
                'sectionPhoto': section_photo_filename
            })
        
        # Save updated registrations
        with open(REGISTRATIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(registrations, f, indent=2, ensure_ascii=False)
        
        return jsonify({'success': True, 'message': 'Rider information updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    if not os.path.exists(REGISTRATIONS_FILE):
        with open(REGISTRATIONS_FILE, 'w') as f:
            json.dump([], f)
    app.run(debug=True, host='0.0.0.0', port=5000)