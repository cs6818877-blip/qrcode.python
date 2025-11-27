# qrcode.python
"""
============================================
QR ATTENDANCE SYSTEM - PYTHON VERSION
============================================
"""

import sqlite3
import qrcode
from datetime import datetime, timedelta
import uuid
import os
from io import BytesIO
import base64
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
PORT = 3000
DB_FILE = 'attendance.db'

# ============================================
# DATABASE SETUP
# ============================================

def get_db_connection():
    """Create database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Initialize database tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create sessions table
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT UNIQUE,
        start_time DATETIME,
        end_time DATETIME,
        status TEXT,
        class_id TEXT
    )''')
    
    # Create students table
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        roll_no TEXT UNIQUE,
        name TEXT,
        email TEXT
    )''')
    
    # Create attendance table
    cursor.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        roll_no TEXT,
        timestamp DATETIME
    )''')
    
    conn.commit()
    conn.close()
    print('✅ Database tables created!')

# Initialize database on startup
init_database()

# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_session_id():
    """Generate unique session ID"""
    return f'SESSION_{str(uuid.uuid4())[:8].upper()}'

def get_current_time():
    """Get current time in ISO format"""
    return datetime.now().isoformat()

def get_time_after_5_minutes():
    """Get time after 5 minutes in ISO format"""
    return (datetime.now() + timedelta(minutes=5)).isoformat()

def generate_qr_code(data):
    """Generate QR code and return as base64"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    img_base64 = base64.b64encode(img_io.getvalue()).decode()
    return f"data:image/png;base64,{img_base64}"

# ============================================
# TEACHER ROUTES
# ============================================

@app.route('/teacher', methods=['GET'])
def teacher_dashboard():
    """Teacher Dashboard - Shows QR code and attendance list"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM sessions WHERE status = "active" ORDER BY start_time DESC LIMIT 1')
    session = cursor.fetchone()
    
    qr_code_url = None
    attendance_list = []
    
    if session:
        # Generate QR code
        student_url = f"http://localhost:{PORT}/student?session={session['session_id']}"
        qr_code_url = generate_qr_code(student_url)
        
        # Get attendance for this session
        cursor.execute('''SELECT s.name, s.roll_no, a.timestamp 
                         FROM attendance a 
                         JOIN students s ON a.roll_no = s.roll_no 
                         WHERE a.session_id = ? 
                         ORDER BY a.timestamp DESC''', (session['session_id'],))
        attendance_list = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        'session': dict(session) if session else None,
        'qr_code': qr_code_url,
        'attendance': [dict(row) for row in attendance_list]
    })

# API: Start Attendance Session
@app.route('/api/start-session', methods=['POST'])
def start_session():
    """Start a new attendance session"""
    session_id = generate_session_id()
    start_time = get_current_time()
    end_time = get_time_after_5_minutes()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Close any active sessions
        cursor.execute('UPDATE sessions SET status = "closed" WHERE status = "active"')
        
        # Create new session
        cursor.execute('''INSERT INTO sessions (session_id, start_time, end_time, status, class_id) 
                         VALUES (?, ?, ?, "active", "10-A")''',
                      (session_id, start_time, end_time))
        conn.commit()
        
        return jsonify({'success': True, 'session_id': session_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# API: Stop Attendance Session
@app.route('/api/stop-session', methods=['POST'])
def stop_session():
    """Stop the current attendance session"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('UPDATE sessions SET status = "closed" WHERE status = "active"')
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# API: Get Attendance List
@app.route('/api/attendance', methods=['GET'])
def get_attendance():
    """Get current session attendance list"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT session_id FROM sessions WHERE status = "active" LIMIT 1')
        session = cursor.fetchone()
        
        if not session:
            return jsonify([])
        
        cursor.execute('''SELECT s.name, s.roll_no, a.timestamp 
                         FROM attendance a 
                         JOIN students s ON a.roll_no = s.roll_no 
                         WHERE a.session_id = ? 
                         ORDER BY a.timestamp DESC''', (session['session_id'],))
        rows = cursor.fetchall()
        
        return jsonify([dict(row) for row in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# ============================================
# STUDENT ROUTES
# ============================================

@app.route('/student', methods=['GET'])
def student_page():
    """Student Attendance Page"""
    session_id = request.args.get('session', '')
    return jsonify({'session_id': session_id})

# API: Mark Attendance
@app.route('/api/mark-attendance', methods=['POST'])
def mark_attendance():
    """Mark student attendance"""
    data = request.get_json()
    session_id = data.get('session_id')
    roll_no = data.get('roll_no')
    
    if not session_id or not roll_no:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Validate session
        cursor.execute('SELECT * FROM sessions WHERE session_id = ? AND status = "active"', (session_id,))
        session = cursor.fetchone()
        
        if not session:
            return jsonify({'success': False, 'error': 'Session not found or expired'}), 400
        
        # Check if session expired (5 minutes)
        now = datetime.now()
        end_time = datetime.fromisoformat(session['end_time'])
        if now > end_time:
            return jsonify({'success': False, 'error': 'Attendance window closed (5 minutes expired)'}), 400
        
        # Check if student exists
        cursor.execute('SELECT * FROM students WHERE roll_no = ?', (roll_no,))
        student = cursor.fetchone()
        if not student:
            return jsonify({'success': False, 'error': 'Student not found'}), 400
        
        # Check if already marked
        cursor.execute('SELECT * FROM attendance WHERE session_id = ? AND roll_no = ?', 
                      (session_id, roll_no))
        existing = cursor.fetchone()
        if existing:
            return jsonify({'success': False, 'error': 'Attendance already marked'}), 400
        
        # Mark attendance
        cursor.execute('INSERT INTO attendance (session_id, roll_no, timestamp) VALUES (?, ?, ?)',
                      (session_id, roll_no, get_current_time()))
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Attendance marked successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ============================================
# ADMIN ROUTES
# ============================================

@app.route('/admin', methods=['GET'])
def admin_panel():
    """Admin Panel - Manage students"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('SELECT * FROM students ORDER BY roll_no')
        students = cursor.fetchall()
        return jsonify([dict(row) for row in students])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

# API: Add Student
@app.route('/api/add-student', methods=['POST'])
def add_student():
    """Add a new student"""
    data = request.get_json()
    roll_no = data.get('roll_no')
    name = data.get('name')
    email = data.get('email', '')
    
    if not roll_no or not name:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('INSERT INTO students (roll_no, name, email) VALUES (?, ?, ?)',
                      (roll_no, name, email))
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Student already exists'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        conn.close()

# ============================================
# START SERVER
# ============================================

if __name__ == '__main__':
    print('')
    print('================================================')
    print('🎓 QR ATTENDANCE SYSTEM RUNNING!')
    print('================================================')
    print('')
    print(f'👨‍🏫 Teacher Dashboard: http://localhost:{PORT}/teacher')
    print(f'📱 Student Page: http://localhost:{PORT}/student')
    print(f'👨‍💼 Admin Panel: http://localhost:{PORT}/admin')
    print('')
    print('Press CTRL+C to stop the server')
    print('================================================')
    app.run(debug=True, port=PORT)
