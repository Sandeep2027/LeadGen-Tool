from flask import Flask, render_template, request, Response, redirect, url_for
import sqlite3
import csv
from io import StringIO
import os
import re
from datetime import datetime

app = Flask(__name__)

# Initialize or migrate SQLite3 database
def init_db():
    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL UNIQUE,
            website TEXT,
            contact_email TEXT,
            industry TEXT NOT NULL,
            revenue REAL NOT NULL,
            score INTEGER,
            created_at TEXT NOT NULL
        )
    ''')
    # Check if score column exists; if not, add it
    cursor.execute("PRAGMA table_info(leads)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'score' not in columns:
        cursor.execute('ALTER TABLE leads ADD COLUMN score INTEGER')
        # Update existing rows with scores
        cursor.execute('SELECT id, revenue FROM leads')
        for row in cursor.fetchall():
            score = calculate_score(row[1])
            cursor.execute('UPDATE leads SET score = ? WHERE id = ?', (score, row[0]))
    conn.commit()
    conn.close()

# Validate email format
def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, email)) if email else True

# Calculate lead score based on revenue
def calculate_score(revenue):
    if revenue >= 15000000:
        return 5
    elif revenue >= 10000000:
        return 4
    elif revenue >= 5000000:
        return 3
    elif revenue >= 3000000:
        return 2
    return 1

# Populate database from CSV
def populate_leads():
    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM leads')  # Clear existing data
    seen_names = set()
    
    with open('sample_leads.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            company_name = row['company_name'].strip()
            if company_name in seen_names or not is_valid_email(row['contact_email']):
                continue
            try:
                revenue = float(row['revenue'])
                if revenue < 0:
                    continue
                score = calculate_score(revenue)
                cursor.execute('''
                    INSERT OR IGNORE INTO leads (company_name, website, contact_email, industry, revenue, score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    company_name,
                    row['website'].strip(),
                    row['contact_email'].strip(),
                    row['industry'].strip(),
                    revenue,
                    score,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ))
                seen_names.add(company_name)
            except ValueError:
                continue
    conn.commit()
    conn.close()

# Routes
@app.route('/', methods=['GET', 'POST'])
def lead_list():
    page = int(request.args.get('page', 1))
    per_page = 5
    industry = request.args.get('industry', '')
    min_revenue = request.args.get('min_revenue', '')
    search = request.args.get('search', '')
    sort_by = request.args.get('sort_by', 'company_name')
    lead_id = request.args.get('lead_id', '')
    action = request.args.get('action', '')

    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()

    # Handle add new company
    if request.method == 'POST' and action == 'add':
        company_name = request.form.get('company_name', '').strip()
        website = request.form.get('website', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        industry_form = request.form.get('industry', '').strip()
        revenue = request.form.get('revenue', '')
        if company_name and industry_form and revenue:
            try:
                revenue = float(revenue)
                if revenue < 0 or not is_valid_email(contact_email):
                    return render_template('index.html', error="Invalid email or revenue", leads=None, lead=None)
                score = calculate_score(revenue)
                cursor.execute('''
                    INSERT OR IGNORE INTO leads (company_name, website, contact_email, industry, revenue, score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (company_name, website, contact_email, industry_form, revenue, score, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
                conn.commit()
            except ValueError:
                return render_template('index.html', error="Invalid revenue", leads=None, lead=None)
        else:
            return render_template('index.html', error="Missing required fields", leads=None, lead=None)

    # Handle edit lead
    if request.method == 'POST' and action == 'edit' and lead_id:
        company_name = request.form.get('company_name', '').strip()
        website = request.form.get('website', '').strip()
        contact_email = request.form.get('contact_email', '').strip()
        industry_form = request.form.get('industry', '').strip()
        revenue = request.form.get('revenue', '')
        if company_name and industry_form and revenue:
            try:
                revenue = float(revenue)
                if revenue < 0 or not is_valid_email(contact_email):
                    return render_template('index.html', error="Invalid email or revenue", leads=None, lead=None)
                score = calculate_score(revenue)
                cursor.execute('''
                    UPDATE leads SET company_name = ?, website = ?, contact_email = ?, industry = ?, revenue = ?, score = ?
                    WHERE id = ?
                ''', (company_name, website, contact_email, industry_form, revenue, score, lead_id))
                conn.commit()
            except ValueError:
                return render_template('index.html', error="Invalid revenue", leads=None, lead=None)
        else:
            return render_template('index.html', error="Missing required fields", leads=None, lead=None)
        return redirect(url_for('lead_list'))

    # Handle CSV import
    if request.method == 'POST' and action == 'import':
        file = request.files.get('csv_file')
        if file and file.filename.endswith('.csv'):
            seen_names = set([row[1] for row in cursor.execute('SELECT company_name FROM leads').fetchall()])
            try:
                reader = csv.DictReader(file.read().decode('utf-8').splitlines())
                for row in reader:
                    company_name = row['company_name'].strip()
                    if company_name in seen_names or not is_valid_email(row['contact_email']):
                        continue
                    revenue = float(row['revenue'])
                    if revenue < 0:
                        continue
                    score = calculate_score(revenue)
                    cursor.execute('''
                        INSERT OR IGNORE INTO leads (company_name, website, contact_email, industry, revenue, score, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        company_name,
                        row['website'].strip(),
                        row['contact_email'].strip(),
                        row['industry'].strip(),
                        revenue,
                        score,
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    ))
                    seen_names.add(company_name)
                conn.commit()
            except (ValueError, KeyError):
                return render_template('index.html', error="Invalid CSV format", leads=None, lead=None)
        else:
            return render_template('index.html', error="Invalid or missing CSV file", leads=None, lead=None)

    # Handle delete lead
    if action == 'delete' and lead_id:
        cursor.execute('DELETE FROM leads WHERE id = ?', (lead_id,))
        conn.commit()

    # Show single lead details or edit form
    if lead_id:
        cursor.execute('SELECT * FROM leads WHERE id = ?', (lead_id,))
        lead = cursor.fetchone()
        conn.close()
        if not lead:
            return render_template('index.html', error="Lead not found", leads=None, lead=None)
        return render_template('index.html', lead=lead, leads=None, edit_mode=action == 'edit')

    # Filter, search, and sort leads
    query = 'SELECT * FROM leads WHERE 1=1'
    params = []
    if industry:
        query += ' AND industry LIKE ?'
        params.append(f'%{industry}%')
    if min_revenue:
        try:
            query += ' AND revenue >= ?'
            params.append(float(min_revenue))
        except ValueError:
            pass
    if search:
        query += ' AND company_name LIKE ?'
        params.append(f'%{search}%')

    # Validate sort_by
    sort_by = sort_by if sort_by in ['company_name', 'revenue', 'score'] else 'company_name'
    query += f' ORDER BY {sort_by}'

    cursor.execute(f'SELECT COUNT(*) FROM ({query})', params)
    total_leads = cursor.fetchone()[0]
    total_pages = (total_leads + per_page - 1) // per_page

    query += ' LIMIT ? OFFSET ?'
    params.extend([per_page, (page - 1) * per_page])
    cursor.execute(query, params)
    leads = cursor.fetchall()
    conn.close()

    return render_template('index.html', 
                         leads=leads, 
                         lead=None, 
                         industry=industry, 
                         min_revenue=min_revenue,
                         search=search,
                         sort_by=sort_by,
                         page=page, 
                         total_pages=total_pages,
                         edit_mode=False)

@app.route('/export')
def export_leads():
    industry = request.args.get('industry', '')
    min_revenue = request.args.get('min_revenue', '')
    search = request.args.get('search', '')

    conn = sqlite3.connect('leads.db')
    cursor = conn.cursor()
    query = 'SELECT company_name, website, contact_email, industry, revenue, score FROM leads WHERE 1=1'
    params = []
    if industry:
        query += ' AND industry LIKE ?'
        params.append(f'%{industry}%')
    if min_revenue:
        try:
            query += ' AND revenue >= ?'
            params.append(float(min_revenue))
        except ValueError:
            pass
    if search:
        query += ' AND company_name LIKE ?'
        params.append(f'%{search}%')

    cursor.execute(query, params)
    leads = cursor.fetchall()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Company Name', 'Website', 'Contact Email', 'Industry', 'Revenue', 'Score'])
    for lead in leads:
        writer.writerow(lead)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    response = Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=leads_{timestamp}.csv'}
    )
    return response

# Initialize database and populate leads
if __name__ == '__main__':
    init_db()  # Always run to ensure schema is up-to-date
    if os.path.exists('sample_leads.csv'):
        populate_leads()
    app.run(host='0.0.0.0', port=8000, debug=True)