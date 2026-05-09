from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime
import base64
import os
import re
from dotenv import load_dotenv
from supabase import create_client, Client

# ── Load env ─────────────────────────────────────────────────────────────────
load_dotenv()

app = Flask(__name__, template_folder='templates', static_folder='.')

# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError('SUPABASE_URL and SUPABASE_KEY must be set in .env')

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Config ────────────────────────────────────────────────────────────────────
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024   # 5 MB max upload

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg'}
ALLOWED_FILE_EXT  = {'png', 'jpg', 'jpeg', 'pdf'}

# ── Helpers ───────────────────────────────────────────────────────────────────

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_FILE_EXT

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXT

def encode_base64(file):
    """Read an uploaded file and return a base64 data-URI string."""
    if not file or not file.filename:
        return None
    try:
        file.seek(0)
        data = file.read()
        encoded = base64.b64encode(data).decode('utf-8')
        mime = file.content_type or 'image/jpeg'
        return f"data:{mime};base64,{encoded}"
    except Exception as e:
        print(f"base64 encode error: {e}")
        return None

def validate_phone(phone):
    """Return cleaned 10-digit Indian mobile number or None."""
    clean = re.sub(r'[\s\-\(\)]', '', phone)
    return clean if re.match(r'^[6789]\d{9}$', clean) else None

def phone_exists(phone):
    """Return True if phone already registered in Supabase."""
    try:
        res = supabase.table('riders').select('phone').eq('phone', phone).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"Duplicate check error: {e}")
        return False

def next_captain_number():
    """Return the next auto-assigned captain number."""
    try:
        res = supabase.table('riders').select('captainNumber').eq('role', 'Captain').execute()
        nums = []
        for r in res.data:
            try:
                nums.append(int(r['captainNumber']))
            except (ValueError, TypeError):
                pass
        return max(nums) + 1 if nums else 1
    except Exception as e:
        print(f"Captain number error: {e}")
        return 1

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/sounds/<filename>')
def serve_sound(filename):
    return send_from_directory('sounds', filename)

@app.route('/')
def index():
    try:
        res = supabase.table('riders').select('*').order('priority').limit(12).execute()
        riders = res.data or []
    except Exception as e:
        print(f"Index load error: {e}")
        riders = []
    return render_template('index.html', riders=riders)

@app.route('/health')
def health_check():
    try:
        res = supabase.table('riders').select('id', count='exact').execute()
        count = res.count if hasattr(res, 'count') else len(res.data)
        return jsonify({
            'status': 'healthy',
            'supabase': 'connected',
            'rider_count': count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

# ── Public: get all riders ────────────────────────────────────────────────────

@app.route('/api/riders', methods=['GET'])
def get_riders():
    try:
        res = supabase.table('riders').select('*').order('priority').execute()
        return jsonify(res.data)
    except Exception as e:
        print(f"Get riders error: {e}")
        return jsonify([]), 500

# ── Public: register ──────────────────────────────────────────────────────────

@app.route('/register', methods=['POST'])
def register():
    try:
        data               = request.form.to_dict()
        driving_license    = request.files.get('drivingLicenseFile')
        rider_photo        = request.files.get('riderPhoto')
        bike_photo         = request.files.get('bikePhoto')

        # Required fields
        for field in ['firstName', 'lastName', 'phone', 'city', 'bike']:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        phone = validate_phone(data['phone'])
        if not phone:
            return jsonify({'success': False,
                            'message': 'Invalid mobile number. Enter a valid 10-digit number starting with 6, 7, 8 or 9.'}), 400

        if phone_exists(phone):
            return jsonify({'success': False,
                            'message': 'This mobile number is already registered.'}), 400

        # Validate file types
        if driving_license and driving_license.filename and not allowed_file(driving_license.filename):
            return jsonify({'success': False, 'message': 'License: only JPG, PNG, PDF allowed'}), 400
        if rider_photo and rider_photo.filename and not allowed_image(rider_photo.filename):
            return jsonify({'success': False, 'message': 'Profile photo: only JPG, PNG allowed'}), 400
        if bike_photo and bike_photo.filename and not allowed_image(bike_photo.filename):
            return jsonify({'success': False, 'message': 'Bike photo: only JPG, PNG allowed'}), 400

        # Encode photos to base64
        rider_photo_b64 = encode_base64(rider_photo) if rider_photo and rider_photo.filename else None
        bike_photo_b64  = encode_base64(bike_photo)  if bike_photo  and bike_photo.filename  else None

        # Insert into Supabase
        supabase.table('riders').insert({
            'firstName':    data.get('firstName', '').strip(),
            'lastName':     data.get('lastName', '').strip(),
            'phone':        phone,
            'city':         data.get('city', '').strip(),
            'bike':         data.get('bike', '').strip(),
            'experience':   data.get('experience', '').strip(),
            'alias':        data.get('alias', '').strip(),
            'instagram':    data.get('instagram', '').strip(),
            'riderPhoto':   rider_photo_b64,
            'bikePhoto':    bike_photo_b64,
            'reason':       data.get('message', '').strip(),
            'role':         'Member',
            'priority':     5,
            'timestamp':    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }).execute()

        whatsapp_link = os.environ.get('WHATSAPP_LINK',
                                       'https://chat.whatsapp.com/HbRgZJa1Rqm5Kbso36WDWf')
        return jsonify({
            'success': True,
            'message': 'Welcome to the MTR Brotherhood!',
            'whatsapp_link': whatsapp_link
        })

    except Exception as e:
        print(f"Register error: {e}")
        return jsonify({'success': False, 'message': 'Something went wrong. Please try again.'}), 500

# ── Admin: login ──────────────────────────────────────────────────────────────

@app.route('/api/admin-login', methods=['POST'])
def admin_login():
    try:
        data     = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if (username == os.environ.get('ADMIN_USERNAME', 'Madmax') and
                password == os.environ.get('ADMIN_PASSWORD', 'Pa$w0rd@Madmax')):
            return jsonify({'success': True, 'message': 'Login successful'})

        return jsonify({'success': False, 'message': 'Invalid username or password'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ── Admin: change password ────────────────────────────────────────────────────

@app.route('/api/change-password', methods=['POST'])
def change_password():
    try:
        data         = request.get_json()
        old_password = data.get('oldPassword', '').strip()
        new_password = data.get('newPassword', '').strip()

        if not old_password or not new_password:
            return jsonify({'success': False, 'message': 'Both passwords are required'}), 400
        if len(new_password) < 6:
            return jsonify({'success': False, 'message': 'New password must be at least 6 characters'}), 400
        if old_password != os.environ.get('ADMIN_PASSWORD', 'Pa$w0rd@Madmax'):
            return jsonify({'success': False, 'message': 'Current password is incorrect'}), 401

        os.environ['ADMIN_PASSWORD'] = new_password
        return jsonify({'success': True, 'message': 'Password changed successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ── Admin: add rider (member / captain / co-founder) ─────────────────────────

def _build_rider_payload(data, rider_photo, bike_photo, role):
    """Build the dict to insert into Supabase for any rider type."""
    rider_photo_b64 = encode_base64(rider_photo) if rider_photo and rider_photo.filename else None
    bike_photo_b64  = encode_base64(bike_photo)  if bike_photo  and bike_photo.filename  else None

    priority = 2 if role == 'Co-Founder' else 3 if role == 'Captain' else 5

    payload = {
        'firstName':  data.get('firstName', '').strip(),
        'lastName':   data.get('lastName', '').strip(),
        'phone':      data.get('phone', '').strip(),
        'city':       data.get('city', 'Pune').strip(),
        'bike':       data.get('bike', '').strip(),
        'experience': data.get('experience', '').strip(),
        'alias':      data.get('alias', '').strip(),
        'instagram':  data.get('instagram', '').strip(),
        'riderPhoto': rider_photo_b64,
        'bikePhoto':  bike_photo_b64,
        'role':       role,
        'priority':   priority,
        'timestamp':  datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }

    if role == 'Captain':
        cap_num = data.get('captainNumber', '').strip()
        if not cap_num:
            cap_num = str(next_captain_number())
        payload['captainNumber'] = cap_num
        payload['reason'] = f"Captain {cap_num} of MTR Brotherhood"
    elif role == 'Co-Founder':
        payload['reason'] = 'Co-Founder of MTR Brotherhood'
    else:
        payload['reason'] = data.get('reason', 'Added by admin').strip()

    return payload

@app.route('/api/add-member-manual', methods=['POST'])
def add_member_manual():
    try:
        data        = request.form.to_dict() if request.content_type.startswith('multipart') else request.get_json()
        rider_photo = request.files.get('riderPhoto') if request.content_type.startswith('multipart') else None
        bike_photo  = request.files.get('bikePhoto')  if request.content_type.startswith('multipart') else None

        for field in ['firstName', 'lastName', 'phone', 'city', 'bike']:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        role    = data.get('role', 'Member')
        payload = _build_rider_payload(data, rider_photo, bike_photo, role)
        supabase.table('riders').insert(payload).execute()
        return jsonify({'success': True, 'message': f'{role} added successfully'})
    except Exception as e:
        print(f"Add member error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-captain', methods=['POST'])
def add_captain():
    try:
        data        = request.form.to_dict() if request.content_type.startswith('multipart') else request.get_json()
        rider_photo = request.files.get('riderPhoto') if request.content_type.startswith('multipart') else None
        bike_photo  = request.files.get('bikePhoto')  if request.content_type.startswith('multipart') else None

        for field in ['firstName', 'lastName', 'alias', 'bike', 'phone']:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        payload = _build_rider_payload(data, rider_photo, bike_photo, 'Captain')
        supabase.table('riders').insert(payload).execute()
        return jsonify({'success': True, 'message': 'Captain added successfully'})
    except Exception as e:
        print(f"Add captain error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/add-cofounder', methods=['POST'])
def add_cofounder():
    try:
        data        = request.form.to_dict() if request.content_type.startswith('multipart') else request.get_json()
        rider_photo = request.files.get('riderPhoto') if request.content_type.startswith('multipart') else None
        bike_photo  = request.files.get('bikePhoto')  if request.content_type.startswith('multipart') else None

        for field in ['firstName', 'lastName', 'alias', 'bike', 'phone']:
            if not data.get(field, '').strip():
                return jsonify({'success': False, 'message': f'{field} is required'}), 400

        payload = _build_rider_payload(data, rider_photo, bike_photo, 'Co-Founder')
        supabase.table('riders').insert(payload).execute()
        return jsonify({'success': True, 'message': 'Co-Founder added successfully'})
    except Exception as e:
        print(f"Add cofounder error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ── Admin: update rider ───────────────────────────────────────────────────────

@app.route('/api/update-rider', methods=['POST'])
def update_rider():
    try:
        data        = request.form.to_dict() if request.content_type.startswith('multipart') else request.get_json()
        rider_photo = request.files.get('riderPhoto') if request.content_type.startswith('multipart') else None
        bike_photo  = request.files.get('bikePhoto')  if request.content_type.startswith('multipart') else None
        section_photo = request.files.get('sectionPhoto') if request.content_type.startswith('multipart') else None

        phone     = data.get('phone', '').strip()
        timestamp = data.get('timestamp', '').strip()

        if not phone or not timestamp:
            return jsonify({'success': False, 'message': 'phone and timestamp are required'}), 400

        # Fetch existing rider
        res = supabase.table('riders').select('*').eq('phone', phone).eq('timestamp', timestamp).execute()
        if not res.data:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        existing = res.data[0]
        is_ceo   = existing.get('priority') == 1

        updates = {
            'firstName':  data.get('firstName', existing['firstName']).strip(),
            'lastName':   data.get('lastName',  existing['lastName']).strip(),
            'alias':      data.get('alias',     existing.get('alias', '')).strip(),
            'city':       data.get('city',      existing.get('city', '')).strip(),
            'bike':       data.get('bike',      existing['bike']).strip(),
            'experience': data.get('experience',existing.get('experience', '')).strip(),
            'instagram':  data.get('instagram', existing.get('instagram', '')).strip(),
            'reason':     data.get('reason',    existing.get('reason', '')).strip(),
        }

        # CEO: lock role & priority
        if is_ceo:
            updates['role']     = 'Founder'
            updates['priority'] = 1
        
        # Photos — only update if a new file was uploaded
        if rider_photo and rider_photo.filename:
            b64 = encode_base64(rider_photo)
            if b64: updates['riderPhoto'] = b64
        if bike_photo and bike_photo.filename:
            b64 = encode_base64(bike_photo)
            if b64: updates['bikePhoto'] = b64
        if section_photo and section_photo.filename:
            b64 = encode_base64(section_photo)
            if b64: updates['sectionPhoto'] = b64

        supabase.table('riders').update(updates).eq('phone', phone).eq('timestamp', timestamp).execute()
        return jsonify({'success': True, 'message': 'Rider updated successfully'})

    except Exception as e:
        print(f"Update rider error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ── Admin: update rider role ──────────────────────────────────────────────────

@app.route('/api/update-rider-role', methods=['POST'])
def update_rider_role():
    try:
        data          = request.get_json()
        phone         = data.get('phone', '').strip()
        timestamp     = data.get('timestamp', '').strip()
        new_role      = data.get('role', '').strip()
        captain_num   = data.get('captainNumber', '').strip()

        if not phone or not timestamp or not new_role:
            return jsonify({'success': False, 'message': 'phone, timestamp and role are required'}), 400

        valid_roles = ['Member', 'Co-Founder', 'Captain']
        if new_role not in valid_roles:
            return jsonify({'success': False, 'message': f'Role must be one of: {", ".join(valid_roles)}'}), 400

        # Fetch rider
        res = supabase.table('riders').select('priority').eq('phone', phone).eq('timestamp', timestamp).execute()
        if not res.data:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        if res.data[0].get('priority') == 1:
            return jsonify({'success': False, 'message': 'Cannot change role of CEO/Founder.'}), 403

        updates = {'role': new_role}
        if new_role == 'Co-Founder':
            updates['priority']      = 2
            updates['captainNumber'] = None
        elif new_role == 'Captain':
            updates['priority']      = 3
            if not captain_num:
                captain_num = str(next_captain_number())
            updates['captainNumber'] = captain_num
            updates['reason']        = f'Captain {captain_num} of MTR Brotherhood'
        else:
            updates['priority']      = 5
            updates['captainNumber'] = None

        supabase.table('riders').update(updates).eq('phone', phone).eq('timestamp', timestamp).execute()
        return jsonify({'success': True, 'message': 'Role updated successfully'})

    except Exception as e:
        print(f"Update role error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ── Admin: delete rider ───────────────────────────────────────────────────────

@app.route('/api/delete-rider', methods=['POST'])
def delete_rider():
    try:
        data      = request.get_json()
        phone     = data.get('phone', '').strip()
        timestamp = data.get('timestamp', '').strip()

        if not phone or not timestamp:
            return jsonify({'success': False, 'message': 'phone and timestamp are required'}), 400

        # Fetch rider to check CEO protection
        res = supabase.table('riders').select('priority', 'firstName', 'lastName').eq('phone', phone).eq('timestamp', timestamp).execute()
        if not res.data:
            return jsonify({'success': False, 'message': 'Rider not found'}), 404

        rider = res.data[0]
        if rider.get('priority') == 1:
            return jsonify({'success': False, 'message': 'Cannot delete CEO/Founder. This member is protected.'}), 403
        if (rider.get('firstName', '').lower() == 'rahul' and
                rider.get('lastName', '').lower() == 'choudhari'):
            return jsonify({'success': False, 'message': 'Cannot delete CEO/Founder. This member is protected.'}), 403

        supabase.table('riders').delete().eq('phone', phone).eq('timestamp', timestamp).execute()
        return jsonify({'success': True, 'message': 'Rider deleted successfully'})

    except Exception as e:
        print(f"Delete rider error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# ── Debug / health ────────────────────────────────────────────────────────────

@app.route('/debug/database')
def debug_database():
    try:
        res = supabase.table('riders').select('id', 'firstName', 'lastName', 'role', 'priority', 'timestamp').order('priority').execute()
        return jsonify({
            'supabase': 'connected',
            'total_riders': len(res.data),
            'riders': res.data
        })
    except Exception as e:
        return jsonify({'supabase': 'error', 'error': str(e)}), 500

# ── Startup: seed CEO if table is empty ──────────────────────────────────────

def seed_ceo_if_empty():
    try:
        res = supabase.table('riders').select('id').limit(1).execute()
        if not res.data:
            print("Riders table is empty — seeding CEO...")
            supabase.table('riders').insert({
                'firstName':  'Rahul',
                'lastName':   'Choudhari',
                'phone':      '9876543210',
                'city':       'Pune',
                'bike':       'Royal Enfield Classic 350',
                'experience': '10+ years',
                'alias':      'Madmax',
                'instagram':  'madmax_mtr',
                'reason':     'Founder of Mad To Ride Brotherhood',
                'role':       'Founder',
                'priority':   1,
                'timestamp':  '01 Jan 2020'
            }).execute()
            print("CEO seeded successfully.")
        else:
            print(f"Supabase has {len(res.data)}+ riders — no seeding needed.")
    except Exception as e:
        print(f"Seed error: {e}")

seed_ceo_if_empty()

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
