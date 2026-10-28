from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database import get_db, init_db, seed_sample_data
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'my_society_ultra_secret_key_2024'

# Initialize database on startup
init_db()

# Auto-seed sample demo data if database is fresh
try:
    seed_sample_data()
except Exception as e:
    print(f"Seed note: {e}")


# ============== CONTEXT PROCESSOR ==============
@app.context_processor
def inject_global_vars():
    """Inject current year and user info to all templates"""
    return {
        'current_year': datetime.now().year,
        'current_month': datetime.now().month
    }


# ============== DECORATORS ==============
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def president_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        if session.get('role') != 'president':
            flash('Access restricted. President privileges required.', 'danger')
            return redirect(url_for('member_dashboard'))
        return f(*args, **kwargs)
    return decorated_function


# ============== PUBLIC ROUTES ==============
@app.route('/')
def index():
    db = get_db()
    # Fetch live stats for landing page social proof
    societies_count = db.execute('SELECT COUNT(*) as cnt FROM societies').fetchone()['cnt']
    members_count = db.execute('SELECT COUNT(*) as cnt FROM users WHERE role = "member"').fetchone()['cnt']
    complaints_resolved = db.execute('SELECT COUNT(*) as cnt FROM complaints WHERE status = "Resolved"').fetchone()['cnt']
    facilities_count = db.execute('SELECT COUNT(*) as cnt FROM facilities').fetchone()['cnt']
    
    # Get active sample society if exists
    sample_society = db.execute('SELECT * FROM societies ORDER BY id ASC LIMIT 1').fetchone()
    db.close()
    
    return render_template(
        'index.html',
        societies_count=societies_count,
        members_count=members_count,
        complaints_resolved=complaints_resolved,
        facilities_count=facilities_count,
        sample_society=sample_society
    )


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['role'] = user['role']
            session['society_id'] = user['society_id']
            session['flat_no'] = user['flat_no']
            session['flat_status'] = user['flat_status']
            
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['role'] == 'president':
                return redirect(url_for('president_dashboard'))
            else:
                return redirect(url_for('member_dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            
    return render_template('login.html')


@app.route('/quick_login/<role>')
def quick_login(role):
    """Convenient 1-click demo login for reviewers and presentation"""
    db = get_db()
    if role == 'president':
        user = db.execute('SELECT * FROM users WHERE role = "president" ORDER BY id ASC LIMIT 1').fetchone()
    else:
        user = db.execute('SELECT * FROM users WHERE role = "member" ORDER BY id ASC LIMIT 1').fetchone()
    db.close()

    if user:
        session['user_id'] = user['id']
        session['user_name'] = user['name']
        session['user_email'] = user['email']
        session['role'] = user['role']
        session['society_id'] = user['society_id']
        session['flat_no'] = user['flat_no']
        session['flat_status'] = user['flat_status']
        flash(f'Demo Login successful as {user["name"]} ({user["role"].title()})', 'info')
        if user['role'] == 'president':
            return redirect(url_for('president_dashboard'))
        else:
            return redirect(url_for('member_dashboard'))
    else:
        flash('No demo user found. Please register or seed sample data.', 'warning')
        return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    db = get_db()
    societies = db.execute('SELECT * FROM societies ORDER BY name ASC').fetchall()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        role = request.form.get('role', 'member')
        
        # Society, flat, status
        society_id = request.form.get('society_id') or None
        flat_no = request.form.get('flat_no', '').strip() or None
        flat_status = request.form.get('flat_status', 'owned')

        if not name or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            db.close()
            return render_template('register.html', societies=societies)

        # Check existing email
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('An account with this email address already exists. Please log in.', 'warning')
            db.close()
            return redirect(url_for('login'))

        hashed_password = generate_password_hash(password)
        try:
            cursor = db.execute('''
                INSERT INTO users (name, email, password, phone, role, society_id, flat_no, flat_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (name, email, hashed_password, phone, role, society_id, flat_no, flat_status))
            db.commit()
            
            # Auto log in the new user
            new_id = cursor.lastrowid
            session['user_id'] = new_id
            session['user_name'] = name
            session['user_email'] = email
            session['role'] = role
            session['society_id'] = society_id
            session['flat_no'] = flat_no
            session['flat_status'] = flat_status
            db.close()
            
            flash('Registration successful! Welcome to My Society.', 'success')
            if role == 'president':
                return redirect(url_for('president_dashboard'))
            else:
                return redirect(url_for('member_dashboard'))
        except Exception as e:
            flash(f'Registration error: {e}', 'danger')
            
    db.close()
    return render_template('register.html', societies=societies)


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('index'))


@app.route('/seed_demo')
def trigger_seed():
    """Manual trigger to seed demo data if desired"""
    seeded = seed_sample_data()
    if seeded:
        flash('Demo data populated successfully! You can now test with demo accounts.', 'success')
    else:
        flash('Demo data already exists in the database.', 'info')
    return redirect(url_for('index'))


# ============== PRESIDENT ROUTES ==============
@app.route('/president/dashboard')
@president_required
def president_dashboard():
    db = get_db()
    
    # Reload fresh user info
    user_record = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    society_id = user_record['society_id'] if user_record else session.get('society_id')
    if society_id != session.get('society_id'):
        session['society_id'] = society_id
        
    society = db.execute('SELECT * FROM societies WHERE id = ?', (society_id,)).fetchone() if society_id else None

    # Key statistics
    total_members = db.execute('SELECT COUNT(*) as cnt FROM users WHERE society_id = ? AND role = "member"', (society_id,)).fetchone()['cnt'] if society_id else 0
    total_facilities = db.execute('SELECT COUNT(*) as cnt FROM facilities WHERE society_id = ?', (society_id,)).fetchone()['cnt'] if society_id else 0
    
    # Complaints metrics
    total_complaints = db.execute('SELECT COUNT(*) as cnt FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ?', (society_id,)).fetchone()['cnt'] if society_id else 0
    pending_complaints = db.execute('SELECT COUNT(*) as cnt FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ? AND c.status = "Pending"', (society_id,)).fetchone()['cnt'] if society_id else 0
    in_progress_complaints = db.execute('SELECT COUNT(*) as cnt FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ? AND c.status = "In Progress"', (society_id,)).fetchone()['cnt'] if society_id else 0
    resolved_complaints = db.execute('SELECT COUNT(*) as cnt FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ? AND c.status = "Resolved"', (society_id,)).fetchone()['cnt'] if society_id else 0

    # Flat breakdown
    owned_flats = db.execute('SELECT COUNT(*) as cnt FROM users WHERE society_id = ? AND flat_status = "owned" AND role = "member"', (society_id,)).fetchone()['cnt'] if society_id else 0
    rented_flats = db.execute('SELECT COUNT(*) as cnt FROM users WHERE society_id = ? AND flat_status = "rented" AND role = "member"', (society_id,)).fetchone()['cnt'] if society_id else 0
    empty_flats = db.execute('SELECT COUNT(*) as cnt FROM users WHERE society_id = ? AND flat_status = "empty" AND role = "member"', (society_id,)).fetchone()['cnt'] if society_id else 0
    
    total_flats_capacity = society['total_flats'] if society and society['total_flats'] else (owned_flats + rented_flats + empty_flats)
    occupancy_pct = round(((owned_flats + rented_flats) / max(total_flats_capacity, 1)) * 100, 1)

    # Financial overview (Current Month)
    curr_month = datetime.now().month
    curr_year = datetime.now().year
    
    rev_paid = db.execute('''
        SELECT COALESCE(SUM(total_amount), 0) as total FROM maintenance m
        JOIN users u ON m.user_id = u.id
        WHERE u.society_id = ? AND m.month = ? AND m.year = ? AND m.paid_status = "Paid"
    ''', (society_id, curr_month, curr_year)).fetchone()['total'] if society_id else 0

    rev_unpaid = db.execute('''
        SELECT COALESCE(SUM(total_amount), 0) as total FROM maintenance m
        JOIN users u ON m.user_id = u.id
        WHERE u.society_id = ? AND m.month = ? AND m.year = ? AND m.paid_status != "Paid"
    ''', (society_id, curr_month, curr_year)).fetchone()['total'] if society_id else 0

    recent_complaints = db.execute('''
        SELECT c.*, u.name as member_name, u.flat_no, f.name as facility_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN facilities f ON c.facility_id = f.id
        WHERE u.society_id = ?
        ORDER BY c.created_at DESC LIMIT 5
    ''', (society_id,)).fetchall() if society_id else []

    recent_members = db.execute('''
        SELECT * FROM users WHERE society_id = ? AND role = "member"
        ORDER BY created_at DESC LIMIT 5
    ''', (society_id,)).fetchall() if society_id else []

    db.close()
    return render_template(
        'president/dashboard.html',
        society=society,
        total_members=total_members,
        total_facilities=total_facilities,
        total_complaints=total_complaints,
        pending_complaints=pending_complaints,
        in_progress_complaints=in_progress_complaints,
        resolved_complaints=resolved_complaints,
        owned_flats=owned_flats,
        rented_flats=rented_flats,
        empty_flats=empty_flats,
        total_flats_capacity=total_flats_capacity,
        occupancy_pct=occupancy_pct,
        rev_paid=rev_paid,
        rev_unpaid=rev_unpaid,
        recent_complaints=recent_complaints,
        recent_members=recent_members
    )


@app.route('/president/add_society', methods=['GET', 'POST'])
@president_required
def add_society():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        city = request.form.get('city', '').strip()
        total_flats = int(request.form.get('total_flats', 0))

        if not name or not address or not city:
            flash('Please complete all society details.', 'danger')
            return render_template('president/add_society.html')

        db = get_db()
        cursor = db.execute(
            'INSERT INTO societies (name, address, city, total_flats) VALUES (?, ?, ?, ?)',
            (name, address, city, total_flats)
        )
        society_id = cursor.lastrowid
        # Update president's society
        db.execute('UPDATE users SET society_id = ? WHERE id = ?', (society_id, session['user_id']))
        db.commit()
        session['society_id'] = society_id
        db.close()
        
        flash(f'Society "{name}" created successfully! Now you can add facilities and invite members.', 'success')
        return redirect(url_for('president_dashboard'))
        
    return render_template('president/add_society.html')


@app.route('/president/manage_members')
@president_required
def manage_members():
    db = get_db()
    society_id = session.get('society_id')
    members = db.execute('''
        SELECT u.*,
               (SELECT COUNT(*) FROM flat_facilities ff WHERE ff.user_id = u.id) as facility_count,
               (SELECT COUNT(*) FROM complaints c WHERE c.user_id = u.id) as complaint_count
        FROM users u
        WHERE u.society_id = ? AND u.role = "member"
        ORDER BY u.flat_no ASC, u.name ASC
    ''', (society_id,)).fetchall()
    db.close()
    return render_template('president/manage_members.html', members=members)


@app.route('/president/update_member_status/<int:member_id>', methods=['POST'])
@president_required
def update_member_status(member_id):
    flat_status = request.form.get('flat_status', 'owned')
    flat_no = request.form.get('flat_no', '').strip()
    
    db = get_db()
    if flat_no:
        db.execute('UPDATE users SET flat_status = ?, flat_no = ? WHERE id = ?', (flat_status, flat_no, member_id))
    else:
        db.execute('UPDATE users SET flat_status = ? WHERE id = ?', (flat_status, member_id))
    db.commit()
    db.close()
    flash('Resident details updated successfully.', 'success')
    return redirect(url_for('manage_members'))


@app.route('/president/delete_member/<int:member_id>')
@president_required
def delete_member(member_id):
    db = get_db()
    # Clean up associated records
    db.execute('DELETE FROM flat_facilities WHERE user_id = ?', (member_id,))
    db.execute('DELETE FROM complaints WHERE user_id = ?', (member_id,))
    db.execute('DELETE FROM maintenance WHERE user_id = ?', (member_id,))
    db.execute('DELETE FROM users WHERE id = ? AND role = "member"', (member_id,))
    db.commit()
    db.close()
    flash('Resident account removed.', 'info')
    return redirect(url_for('manage_members'))


@app.route('/president/manage_facilities', methods=['GET', 'POST'])
@president_required
def manage_facilities():
    db = get_db()
    society_id = session.get('society_id')
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        monthly_cost = float(request.form.get('monthly_cost', 0))

        if not name:
            flash('Facility name cannot be empty.', 'danger')
        else:
            db.execute(
                'INSERT INTO facilities (name, description, monthly_cost, society_id) VALUES (?, ?, ?, ?)',
                (name, description, monthly_cost, society_id)
            )
            db.commit()
            flash(f'Facility "{name}" added successfully with monthly charge ₹{monthly_cost:.2f}.', 'success')

    facilities = db.execute('''
        SELECT f.*,
               (SELECT COUNT(*) FROM flat_facilities ff WHERE ff.facility_id = f.id) as availed_count,
               ((SELECT COUNT(*) FROM flat_facilities ff WHERE ff.facility_id = f.id) * f.monthly_cost) as total_revenue
        FROM facilities f
        WHERE f.society_id = ?
        ORDER BY f.name ASC
    ''', (society_id,)).fetchall()
    db.close()
    return render_template('president/manage_facilities.html', facilities=facilities)


@app.route('/president/delete_facility/<int:facility_id>')
@president_required
def delete_facility(facility_id):
    db = get_db()
    db.execute('DELETE FROM flat_facilities WHERE facility_id = ?', (facility_id,))
    db.execute('DELETE FROM complaints WHERE facility_id = ?', (facility_id,))
    db.execute('DELETE FROM facilities WHERE id = ?', (facility_id,))
    db.commit()
    db.close()
    flash('Facility and linked subscriptions deleted successfully.', 'info')
    return redirect(url_for('manage_facilities'))


@app.route('/president/facility_usage')
@president_required
def facility_usage():
    db = get_db()
    society_id = session.get('society_id')
    facilities = db.execute('SELECT * FROM facilities WHERE society_id = ? ORDER BY name ASC', (society_id,)).fetchall()
    
    facility_data = []
    total_opted_count = 0
    total_facility_revenue = 0
    
    for f in facilities:
        users = db.execute('''
            SELECT u.name, u.flat_no, u.flat_status, u.phone, ff.availed_date
            FROM flat_facilities ff
            JOIN users u ON ff.user_id = u.id
            WHERE ff.facility_id = ?
            ORDER BY u.flat_no ASC
        ''', (f['id'],)).fetchall()
        
        rev = len(users) * f['monthly_cost']
        total_opted_count += len(users)
        total_facility_revenue += rev
        
        facility_data.append({
            'facility': f,
            'users': users,
            'user_count': len(users),
            'revenue': rev
        })
        
    db.close()
    return render_template(
        'president/facility_usage.html',
        facility_data=facility_data,
        total_opted_count=total_opted_count,
        total_facility_revenue=total_facility_revenue
    )


@app.route('/president/flat_status')
@president_required
def flat_status():
    db = get_db()
    society_id = session.get('society_id')
    
    owned = db.execute('''
        SELECT u.*, (SELECT COUNT(*) FROM flat_facilities ff WHERE ff.user_id = u.id) as facility_count
        FROM users u WHERE society_id = ? AND flat_status = "owned" AND role = "member"
        ORDER BY flat_no ASC
    ''', (society_id,)).fetchall()
    
    rented = db.execute('''
        SELECT u.*, (SELECT COUNT(*) FROM flat_facilities ff WHERE ff.user_id = u.id) as facility_count
        FROM users u WHERE society_id = ? AND flat_status = "rented" AND role = "member"
        ORDER BY flat_no ASC
    ''', (society_id,)).fetchall()
    
    empty = db.execute('''
        SELECT u.*, (SELECT COUNT(*) FROM flat_facilities ff WHERE ff.user_id = u.id) as facility_count
        FROM users u WHERE society_id = ? AND flat_status = "empty" AND role = "member"
        ORDER BY flat_no ASC
    ''', (society_id,)).fetchall()
    
    society = db.execute('SELECT * FROM societies WHERE id = ?', (society_id,)).fetchone() if society_id else None
    db.close()
    
    return render_template(
        'president/flat_status.html',
        owned=owned,
        rented=rented,
        empty=empty,
        society=society
    )


@app.route('/president/view_complaints')
@president_required
def view_complaints():
    db = get_db()
    society_id = session.get('society_id')
    status_filter = request.args.get('status')
    
    query = '''
        SELECT c.*, u.name as member_name, u.flat_no, u.phone as member_phone, f.name as facility_name
        FROM complaints c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN facilities f ON c.facility_id = f.id
        WHERE u.society_id = ?
    '''
    params = [society_id]
    
    if status_filter in ['Pending', 'In Progress', 'Resolved']:
        query += ' AND c.status = ?'
        params.append(status_filter)
        
    query += ' ORDER BY c.created_at DESC'
    complaints = db.execute(query, params).fetchall()
    
    counts = {
        'all': db.execute('SELECT COUNT(*) FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ?', (society_id,)).fetchone()[0],
        'pending': db.execute('SELECT COUNT(*) FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ? AND c.status = "Pending"', (society_id,)).fetchone()[0],
        'in_progress': db.execute('SELECT COUNT(*) FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ? AND c.status = "In Progress"', (society_id,)).fetchone()[0],
        'resolved': db.execute('SELECT COUNT(*) FROM complaints c JOIN users u ON c.user_id = u.id WHERE u.society_id = ? AND c.status = "Resolved"', (society_id,)).fetchone()[0]
    }
    db.close()
    
    return render_template('president/view_complaints.html', complaints=complaints, counts=counts, current_filter=status_filter)


@app.route('/president/update_complaint/<int:complaint_id>', methods=['POST'])
@president_required
def update_complaint(complaint_id):
    status = request.form.get('status', 'Pending')
    response = request.form.get('response', '').strip()
    
    db = get_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if status == 'Resolved':
        db.execute(
            'UPDATE complaints SET status = ?, response = ?, resolved_at = ? WHERE id = ?',
            (status, response, now_str, complaint_id)
        )
    else:
        db.execute(
            'UPDATE complaints SET status = ?, response = ? WHERE id = ?',
            (status, response, complaint_id)
        )
    db.commit()
    db.close()
    flash(f'Complaint #{complaint_id} marked as "{status}".', 'success')
    return redirect(url_for('view_complaints'))


@app.route('/president/maintenance_overview')
@president_required
def maintenance_overview():
    db = get_db()
    society_id = session.get('society_id')
    month = request.args.get('month', type=int) or datetime.now().month
    year = request.args.get('year', type=int) or datetime.now().year
    
    members = db.execute('SELECT * FROM users WHERE society_id = ? AND role = "member" ORDER BY flat_no ASC', (society_id,)).fetchall()
    
    maintenance_data = []
    total_billed = 0
    total_collected = 0
    total_pending = 0
    
    for m in members:
        facilities = db.execute('''
            SELECT f.name, f.monthly_cost
            FROM flat_facilities ff
            JOIN facilities f ON ff.facility_id = f.id
            WHERE ff.user_id = ?
        ''', (m['id'],)).fetchall()
        
        total_facility_cost = sum(f['monthly_cost'] for f in facilities)
        base = 500.0
        calculated_total = base + total_facility_cost
        
        # Check if record generated for this month
        bill_record = db.execute('''
            SELECT * FROM maintenance
            WHERE user_id = ? AND month = ? AND year = ?
        ''', (m['id'], month, year)).fetchone()
        
        if bill_record:
            total_billed += bill_record['total_amount']
            if bill_record['paid_status'] == 'Paid':
                total_collected += bill_record['total_amount']
            else:
                total_pending += bill_record['total_amount']
                
        maintenance_data.append({
            'member': m,
            'facilities': facilities,
            'base_amount': base,
            'facility_charges': total_facility_cost,
            'calculated_total': calculated_total,
            'bill': bill_record
        })
        
    db.close()
    return render_template(
        'president/maintenance_overview.html',
        maintenance_data=maintenance_data,
        selected_month=month,
        selected_year=year,
        total_billed=total_billed,
        total_collected=total_collected,
        total_pending=total_pending
    )


@app.route('/president/generate_maintenance', methods=['POST'])
@president_required
def generate_maintenance():
    month = int(request.form.get('month', datetime.now().month))
    year = int(request.form.get('year', datetime.now().year))
    
    db = get_db()
    society_id = session.get('society_id')
    members = db.execute('SELECT * FROM users WHERE society_id = ? AND role = "member"', (society_id,)).fetchall()
    
    generated_count = 0
    for m in members:
        existing = db.execute(
            'SELECT id FROM maintenance WHERE user_id = ? AND month = ? AND year = ?',
            (m['id'], month, year)
        ).fetchone()
        
        if not existing:
            facilities = db.execute('''
                SELECT f.monthly_cost FROM flat_facilities ff
                JOIN facilities f ON ff.facility_id = f.id
                WHERE ff.user_id = ?
            ''', (m['id'],)).fetchall()
            
            facility_charges = sum(f['monthly_cost'] for f in facilities)
            base = 500.0
            total = base + facility_charges
            
            db.execute('''
                INSERT INTO maintenance (user_id, month, year, base_amount, facility_charges, total_amount, paid_status)
                VALUES (?, ?, ?, ?, ?, ?, "Unpaid")
            ''', (m['id'], month, year, base, facility_charges, total))
            generated_count += 1
            
    db.commit()
    db.close()
    
    if generated_count > 0:
        flash(f'Successfully generated {generated_count} maintenance bills for {month}/{year}.', 'success')
    else:
        flash(f'Maintenance bills for {month}/{year} were already generated.', 'info')
        
    return redirect(url_for('maintenance_overview', month=month, year=year))


@app.route('/president/toggle_payment/<int:maintenance_id>')
@president_required
def toggle_payment(maintenance_id):
    """Allows president to mark payment as Paid/Unpaid offline"""
    db = get_db()
    bill = db.execute('SELECT * FROM maintenance WHERE id = ?', (maintenance_id,)).fetchone()
    
    if bill:
        new_status = 'Unpaid' if bill['paid_status'] == 'Paid' else 'Paid'
        paid_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S') if new_status == 'Paid' else None
        
        db.execute('UPDATE maintenance SET paid_status = ?, paid_date = ? WHERE id = ?', (new_status, paid_date, maintenance_id))
        db.commit()
        flash(f'Bill #{maintenance_id} payment status toggled to "{new_status}".', 'success')
        
    db.close()
    return redirect(url_for('maintenance_overview'))


# ============== MEMBER ROUTES ==============
@app.route('/member/dashboard')
@login_required
def member_dashboard():
    db = get_db()
    user_id = session['user_id']
    
    # Reload fresh record
    user = db.execute('''
        SELECT u.*, s.name as society_name, s.address as society_address, s.city as society_city
        FROM users u
        LEFT JOIN societies s ON u.society_id = s.id
        WHERE u.id = ?
    ''', (user_id,)).fetchone()
    
    my_facilities = db.execute('''
        SELECT f.*, ff.availed_date
        FROM flat_facilities ff
        JOIN facilities f ON ff.facility_id = f.id
        WHERE ff.user_id = ?
        ORDER BY f.name ASC
    ''', (user_id,)).fetchall()
    
    pending_complaints = db.execute('SELECT COUNT(*) as cnt FROM complaints WHERE user_id = ? AND status = "Pending"', (user_id,)).fetchone()['cnt']
    total_complaints = db.execute('SELECT COUNT(*) as cnt FROM complaints WHERE user_id = ?', (user_id,)).fetchone()['cnt']
    
    # Current month's bill or latest
    curr_month = datetime.now().month
    curr_year = datetime.now().year
    
    curr_maintenance = db.execute('''
        SELECT * FROM maintenance
        WHERE user_id = ? AND month = ? AND year = ?
    ''', (user_id, curr_month, curr_year)).fetchone()
    
    latest_maintenance = db.execute('''
        SELECT * FROM maintenance WHERE user_id = ? ORDER BY year DESC, month DESC LIMIT 1
    ''', (user_id,)).fetchone()
    
    # Live calculated costs
    total_facility_cost = sum(f['monthly_cost'] for f in my_facilities)
    base_amount = 500.0
    estimated_monthly = base_amount + total_facility_cost

    recent_complaints = db.execute('''
        SELECT c.*, f.name as facility_name
        FROM complaints c
        LEFT JOIN facilities f ON c.facility_id = f.id
        WHERE c.user_id = ?
        ORDER BY c.created_at DESC LIMIT 3
    ''', (user_id,)).fetchall()

    db.close()
    return render_template(
        'member/dashboard.html',
        user=user,
        my_facilities=my_facilities,
        pending_complaints=pending_complaints,
        total_complaints=total_complaints,
        curr_maintenance=curr_maintenance,
        latest_maintenance=latest_maintenance,
        total_facility_cost=total_facility_cost,
        base_amount=base_amount,
        estimated_monthly=estimated_monthly,
        recent_complaints=recent_complaints
    )


@app.route('/member/my_facilities', methods=['GET', 'POST'])
@login_required
def my_facilities():
    db = get_db()
    user_id = session['user_id']
    user = db.execute('SELECT society_id FROM users WHERE id = ?', (user_id,)).fetchone()
    society_id = user['society_id'] if user else session.get('society_id')
    
    if request.method == 'POST':
        facility_id = request.form.get('facility_id')
        action = request.form.get('action', 'add')
        
        if action == 'add':
            try:
                db.execute('INSERT INTO flat_facilities (user_id, facility_id) VALUES (?, ?)', (user_id, facility_id))
                db.commit()
                flash('Facility opted in successfully! Charges will be included in your monthly maintenance.', 'success')
            except Exception:
                flash('You are already subscribed to this facility.', 'warning')
        elif action == 'remove':
            db.execute('DELETE FROM flat_facilities WHERE user_id = ? AND facility_id = ?', (user_id, facility_id))
            db.commit()
            flash('Facility removed from your subscriptions.', 'info')

    all_facilities = db.execute('SELECT * FROM facilities WHERE society_id = ? ORDER BY name ASC', (society_id,)).fetchall() if society_id else []
    my_facility_ids = [row['facility_id'] for row in db.execute('SELECT facility_id FROM flat_facilities WHERE user_id = ?', (user_id,)).fetchall()]
    
    my_fac = db.execute('''
        SELECT f.*, ff.availed_date
        FROM flat_facilities ff
        JOIN facilities f ON ff.facility_id = f.id
        WHERE ff.user_id = ?
        ORDER BY f.name ASC
    ''', (user_id,)).fetchall()
    
    total_opted_cost = sum(f['monthly_cost'] for f in my_fac)
    
    db.close()
    return render_template(
        'member/my_facilities.html',
        all_facilities=all_facilities,
        my_facility_ids=my_facility_ids,
        my_facilities=my_fac,
        total_opted_cost=total_opted_cost
    )


@app.route('/member/raise_complaint', methods=['GET', 'POST'])
@login_required
def raise_complaint():
    db = get_db()
    user = db.execute('SELECT society_id FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    society_id = user['society_id'] if user else session.get('society_id')
    
    facilities = db.execute('SELECT * FROM facilities WHERE society_id = ? ORDER BY name ASC', (society_id,)).fetchall() if society_id else []
    
    if request.method == 'POST':
        subject = request.form.get('subject', '').strip()
        description = request.form.get('description', '').strip()
        facility_id = request.form.get('facility_id') or None
        
        if not subject or not description:
            flash('Please provide both a subject and a description for your complaint.', 'danger')
        else:
            db.execute(
                'INSERT INTO complaints (user_id, facility_id, subject, description) VALUES (?, ?, ?, ?)',
                (session['user_id'], facility_id, subject, description)
            )
            db.commit()
            flash('Your complaint has been submitted to the society president. You can track status here.', 'success')
            db.close()
            return redirect(url_for('my_complaints'))

    db.close()
    return render_template('member/raise_complaint.html', facilities=facilities)


@app.route('/member/my_complaints')
@login_required
def my_complaints():
    db = get_db()
    complaints = db.execute('''
        SELECT c.*, f.name as facility_name
        FROM complaints c
        LEFT JOIN facilities f ON c.facility_id = f.id
        WHERE c.user_id = ?
        ORDER BY c.created_at DESC
    ''', (session['user_id'],)).fetchall()
    db.close()
    return render_template('member/my_complaints.html', complaints=complaints)


@app.route('/member/my_maintenance')
@login_required
def my_maintenance():
    db = get_db()
    user_id = session['user_id']
    
    maintenance_records = db.execute('''
        SELECT * FROM maintenance
        WHERE user_id = ?
        ORDER BY year DESC, month DESC
    ''', (user_id,)).fetchall()
    
    my_facilities = db.execute('''
        SELECT f.name, f.monthly_cost
        FROM flat_facilities ff
        JOIN facilities f ON ff.facility_id = f.id
        WHERE ff.user_id = ?
        ORDER BY f.name ASC
    ''', (user_id,)).fetchall()
    
    total_facility_cost = sum(f['monthly_cost'] for f in my_facilities)
    base_amount = 500.0
    total = base_amount + total_facility_cost
    
    db.close()
    return render_template(
        'member/my_maintenance.html',
        records=maintenance_records,
        facilities=my_facilities,
        base_amount=base_amount,
        facility_cost=total_facility_cost,
        total=total
    )


@app.route('/member/pay_maintenance/<int:maintenance_id>', methods=['POST'])
@login_required
def pay_maintenance(maintenance_id):
    """Simulate instant online payment of maintenance bill"""
    db = get_db()
    user_id = session['user_id']
    
    bill = db.execute('SELECT * FROM maintenance WHERE id = ? AND user_id = ?', (maintenance_id, user_id)).fetchone()
    
    if bill:
        if bill['paid_status'] == 'Paid':
            flash('This bill has already been paid.', 'info')
        else:
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            db.execute('UPDATE maintenance SET paid_status = "Paid", paid_date = ? WHERE id = ?', (now_str, maintenance_id))
            db.commit()
            flash(f'Payment of ₹{bill["total_amount"]:.2f} received successfully! Receipt generated.', 'success')
    else:
        flash('Bill record not found.', 'danger')
        
    db.close()
    return redirect(url_for('my_maintenance'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
