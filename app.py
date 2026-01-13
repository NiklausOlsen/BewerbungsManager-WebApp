"""
BewerbungsManager Web-App
Eine Flask-Anwendung zur Verwaltung von Bewerbungen und Generierung von Anschreiben
"""
import os
import csv
import io
import json
from datetime import date, datetime
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, jsonify, Response, send_file
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
import uuid
from werkzeug.utils import secure_filename
from config import Config
from models import db, Application, UserSettings, Letter, Template, Document, User, DeletedRecord
from forms import ApplicationForm, TextGeneratorForm, UserSettingsForm, TemplateForm, LoginForm, RegisterForm
from services.textgen import text_generator, TextGenerator
from services.pdfgen import pdf_generator, generate_filename

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Bitte melden Sie sich an, um diese Seite zu sehen.'
login_manager.login_message_category = 'info'
login_manager.needs_refresh_message = None


@login_manager.user_loader
def load_user(user_id):
    """Lädt den Benutzer für Flask-Login"""
    return db.session.get(User, int(user_id))


# CSRF Token und Hilfsfunktionen für alle Templates verfügbar machen
@app.context_processor
def inject_template_globals():
    return dict(
        csrf_token=generate_csrf,
        now=datetime.now
    )


# Create tables and instance folder
with app.app_context():
    # Ensure instance folder exists
    instance_path = os.path.join(os.path.dirname(__file__), 'instance')
    if not os.path.exists(instance_path):
        os.makedirs(instance_path)
    # Ensure upload folder exists
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    db.create_all()


def allowed_file(filename):
    """Prüft ob die Dateiendung erlaubt ist"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def create_sample_data_for_user(user_id):
    """Erstellt Beispieldaten für einen neuen Benutzer"""
    # Benutzerdaten abrufen
    user = db.session.get(User, user_id)
    
    # Beispiel-Bewerbung
    sample_app = Application(
        user_id=user_id,
        company_name="Beispiel GmbH",
        job_title="Projektmanager (m/w/d)",
        location="Berlin",
        remote_possible=True,
        contact_person="Frau Muster",
        contact_email="bewerbung@beispiel-gmbh.de",
        contact_phone="+49 30 12345678",
        company_address="Musterstraße 123\n10115 Berlin",
        source="LinkedIn",
        job_url="https://www.beispiel-gmbh.de/karriere",
        status="draft",
        feedback="unknown",
        response_received=False,
        notes="Dies ist eine Beispiel-Bewerbung. Sie können diese bearbeiten oder löschen.",
        created_at=datetime.utcnow()
    )
    db.session.add(sample_app)
    
    # Beispiel-Vorlage
    sample_template = Template(
        user_id=user_id,
        name="Beispiel-Anschreiben",
        content="""Sehr geehrte Damen und Herren,

mit großem Interesse habe ich Ihre Stellenausschreibung für die Position als {job_title} gelesen.

{company_name} hat sich als innovatives Unternehmen etabliert, und ich möchte Teil Ihres Teams werden.

Mit freundlichen Grüßen
{my_name}""",
        created_at=datetime.utcnow()
    )
    db.session.add(sample_template)
    
    # Einstellungen mit echten User-Daten vorausfüllen
    sample_settings = UserSettings(
        user_id=user_id,
        your_name=user.name if user else "Max Mustermann",
        your_email=user.email if user else "max.mustermann@example.com",
        your_phone="+49 123 4567890",
        your_address="Musterstraße 1\n12345 Musterstadt",
        created_at=datetime.utcnow()
    )
    db.session.add(sample_settings)
    
    db.session.commit()


# ============================================================================
# Authentication
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login-Seite"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Ihr Konto wurde noch nicht freigeschaltet. Bitte warten Sie auf die Freigabe durch einen Administrator.', 'warning')
                return render_template('auth/login.html', form=form)
            
            login_user(user, remember=form.remember_me.data)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            flash('Erfolgreich angemeldet!', 'success')
            
            # Immer zur Startseite weiterleiten (saubere URL)
            return redirect(url_for('index'))
        else:
            flash('Ungültige E-Mail oder Passwort.', 'error')
    
    return render_template('auth/login.html', form=form)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registrierungs-Seite"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        # Prüfen ob E-Mail bereits existiert
        existing_user = User.query.filter_by(email=form.email.data.lower()).first()
        if existing_user:
            flash('Diese E-Mail-Adresse ist bereits registriert.', 'error')
            return render_template('auth/register.html', form=form)
        
        # Neuen Benutzer erstellen
        user = User(
            email=form.email.data.lower(),
            name=form.name.data
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        # Prüfen ob dies der erste Benutzer ist (wird automatisch Admin)
        if User.query.count() == 0:
            user.is_admin = True
            user.is_active = True
        
        flash('Registrierung erfolgreich! Ihr Konto muss erst von einem Administrator freigeschaltet werden.', 'info')
        return redirect(url_for('login'))
    
    return render_template('auth/register.html', form=form)


# ============================================================================
# Admin - Benutzerverwaltung
# ============================================================================

def admin_required(f):
    """Decorator für Admin-only Routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Sie haben keine Berechtigung für diese Seite.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    """Admin: Alle Benutzer anzeigen"""
    users = User.query.order_by(User.created_at.desc()).all()
    pending_count = User.query.filter_by(is_active=False).count()
    return render_template('admin/users.html', users=users, pending_count=pending_count)


@app.route('/admin/users/<int:user_id>/activate', methods=['POST'])
@login_required
@admin_required
def admin_activate_user(user_id):
    """Admin: Benutzer aktivieren"""
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    
    # Beispieldaten für neuen Benutzer erstellen
    # Prüfen ob Benutzer bereits Daten hat
    has_data = (
        Application.query.filter_by(user_id=user.id).count() > 0 or
        Template.query.filter_by(user_id=user.id).count() > 0 or
        UserSettings.query.filter_by(user_id=user.id).count() > 0
    )
    
    if not has_data:
        create_sample_data_for_user(user.id)
        flash(f'Benutzer {user.email} wurde aktiviert und Beispieldaten wurden erstellt.', 'success')
    else:
        flash(f'Benutzer {user.email} wurde aktiviert.', 'success')
    
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/deactivate', methods=['POST'])
@login_required
@admin_required
def admin_deactivate_user(user_id):
    """Admin: Benutzer deaktivieren"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Sie können sich nicht selbst deaktivieren.', 'error')
        return redirect(url_for('admin_users'))
    user.is_active = False
    db.session.commit()
    flash(f'Benutzer {user.email} wurde deaktiviert.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def admin_toggle_admin(user_id):
    """Admin: Admin-Rechte umschalten"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Sie können Ihre eigenen Admin-Rechte nicht entfernen.', 'error')
        return redirect(url_for('admin_users'))
    user.is_admin = not user.is_admin
    status = 'Admin-Rechte erteilt' if user.is_admin else 'Admin-Rechte entzogen'
    db.session.commit()
    flash(f'{user.email}: {status}.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    """Admin: Benutzer löschen (mit Archivierung)"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Sie können sich nicht selbst löschen.', 'error')
        return redirect(url_for('admin_users'))
    
    # Benutzer-Daten archivieren
    user_data = {
        'id': user.id,
        'email': user.email,
        'name': user.name,
        'is_active': user.is_active,
        'is_admin': user.is_admin,
        'created_at': user.created_at.isoformat() if user.created_at else None,
        'last_login': user.last_login.isoformat() if user.last_login else None
    }
    
    deleted_record = DeletedRecord(
        table_name='users',
        record_id=user.id,
        record_data=json.dumps(user_data),
        deleted_by=current_user.id
    )
    db.session.add(deleted_record)
    
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f'Benutzer {email} wurde gelöscht und archiviert.', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
def admin_reset_password(user_id):
    """Admin: Passwort eines Benutzers zurücksetzen"""
    user = User.query.get_or_404(user_id)
    new_password = request.form.get('new_password', '')
    
    if len(new_password) < 6:
        flash('Passwort muss mindestens 6 Zeichen lang sein.', 'error')
        return redirect(url_for('admin_users'))
    
    user.set_password(new_password)
    db.session.commit()
    flash(f'Passwort für {user.email} wurde zurückgesetzt.', 'success')
    return redirect(url_for('admin_users'))


# ============================================================================
# Admin - Datenbank-Verwaltung
# ============================================================================

@app.route('/admin/database')
@login_required
@admin_required
def admin_database():
    """Admin: Datenbank-Übersicht mit allen Tabellen"""
    # Statistiken
    stats = {
        'users': User.query.count(),
        'applications': Application.query.count(),
        'templates': Template.query.count(),
        'letters': Letter.query.count(),
        'documents': Document.query.count(),
        'deleted': DeletedRecord.query.count()
    }
    
    # Alle Daten laden
    users = User.query.order_by(User.created_at.desc()).all()
    # Bewerbungsanzahl pro Benutzer hinzufügen
    for user in users:
        user.application_count = Application.query.filter_by(user_id=user.id).count()
    
    applications = Application.query.order_by(Application.created_at.desc()).all()
    templates = Template.query.order_by(Template.created_at.desc()).all()
    letters = Letter.query.order_by(Letter.created_at.desc()).all()
    documents = Document.query.order_by(Document.created_at.desc()).all()
    deleted_records = DeletedRecord.query.order_by(DeletedRecord.deleted_at.desc()).all()
    
    return render_template(
        'admin/database.html',
        stats=stats,
        users=users,
        applications=applications,
        templates=templates,
        letters=letters,
        documents=documents,
        deleted_records=deleted_records
    )


@app.route('/admin/export-all')
@login_required
@admin_required
def admin_export_all():
    """Admin: Komplettes Datenbank-Backup als JSON"""
    backup_data = {
        'exported_at': datetime.utcnow().isoformat(),
        'exported_by': current_user.email,
        'users': [],
        'applications': [],
        'templates': [],
        'letters': [],
        'user_settings': [],
        'documents': [],
        'deleted_records': []
    }
    
    # Benutzer exportieren (ohne Passwort-Hashes)
    for user in User.query.all():
        backup_data['users'].append({
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_active': user.is_active,
            'is_admin': user.is_admin,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None
        })
    
    # Bewerbungen exportieren
    for app in Application.query.all():
        backup_data['applications'].append({
            'id': app.id,
            'user_id': app.user_id,
            'company_name': app.company_name,
            'job_title': app.job_title,
            'sent_date': app.sent_date.isoformat() if app.sent_date else None,
            'status': app.status,
            'feedback': app.feedback,
            'response_received': app.response_received,
            'salary_expectation_given': app.salary_expectation_given,
            'salary_amount': float(app.salary_amount) if app.salary_amount else None,
            'salary_currency': app.salary_currency,
            'salary_period': app.salary_period,
            'contact_person': app.contact_person,
            'company_address': app.company_address,
            'website': app.website,
            'job_url': app.job_url,
            'location': app.location,
            'remote_possible': app.remote_possible,
            'source': app.source,
            'notes': app.notes,
            'is_deleted': app.is_deleted,
            'deleted_at': app.deleted_at.isoformat() if app.deleted_at else None,
            'created_at': app.created_at.isoformat() if app.created_at else None,
            'last_update': app.last_update.isoformat() if app.last_update else None
        })
    
    # Vorlagen exportieren
    for tpl in Template.query.all():
        backup_data['templates'].append({
            'id': tpl.id,
            'user_id': tpl.user_id,
            'name': tpl.name,
            'description': tpl.description,
            'content': tpl.content,
            'is_default': tpl.is_default,
            'created_at': tpl.created_at.isoformat() if tpl.created_at else None
        })
    
    # Anschreiben exportieren
    for letter in Letter.query.all():
        backup_data['letters'].append({
            'id': letter.id,
            'application_id': letter.application_id,
            'template_used': letter.template_used,
            'rendered_text': letter.rendered_text,
            'created_at': letter.created_at.isoformat() if letter.created_at else None
        })
    
    # Benutzereinstellungen exportieren
    for settings in UserSettings.query.all():
        backup_data['user_settings'].append({
            'id': settings.id,
            'user_id': settings.user_id,
            'your_name': settings.your_name,
            'your_address': settings.your_address,
            'your_email': settings.your_email,
            'your_phone': settings.your_phone,
            'default_template': settings.default_template
        })
    
    # Dokumente exportieren (nur Metadaten, nicht die Dateien selbst)
    for doc in Document.query.all():
        backup_data['documents'].append({
            'id': doc.id,
            'application_id': doc.application_id,
            'filename': doc.filename,
            'stored_filename': doc.stored_filename,
            'file_type': doc.file_type,
            'file_size': doc.file_size,
            'description': doc.description,
            'created_at': doc.created_at.isoformat() if doc.created_at else None
        })
    
    # Gelöschte Einträge exportieren
    for record in DeletedRecord.query.all():
        backup_data['deleted_records'].append({
            'id': record.id,
            'table_name': record.table_name,
            'record_id': record.record_id,
            'record_data': record.record_data,
            'deleted_by': record.deleted_by,
            'deleted_at': record.deleted_at.isoformat() if record.deleted_at else None
        })
    
    # JSON-Response erstellen
    output = json.dumps(backup_data, ensure_ascii=False, indent=2)
    
    return Response(
        output,
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename=bewerbungsmanager_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        }
    )


@app.route('/admin/import-data', methods=['POST'])
@login_required
@admin_required
def admin_import_data():
    """Admin: Daten aus JSON-Backup importieren"""
    if 'file' not in request.files:
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('admin_database'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('admin_database'))
    
    if not file.filename.endswith('.json'):
        flash('Nur JSON-Dateien sind erlaubt!', 'error')
        return redirect(url_for('admin_database'))
    
    try:
        data = json.load(file)
        imported_counts = {'applications': 0, 'templates': 0, 'letters': 0}
        
        # Bewerbungen importieren
        for app_data in data.get('applications', []):
            # Prüfen ob Bewerbung bereits existiert
            existing = Application.query.filter_by(
                company_name=app_data.get('company_name'),
                job_title=app_data.get('job_title'),
                user_id=app_data.get('user_id') or current_user.id
            ).first()
            
            if not existing:
                app = Application(
                    user_id=app_data.get('user_id') or current_user.id,
                    company_name=app_data.get('company_name'),
                    job_title=app_data.get('job_title'),
                    status=app_data.get('status', 'draft'),
                    feedback=app_data.get('feedback', 'unknown'),
                    response_received=app_data.get('response_received', False),
                    salary_expectation_given=app_data.get('salary_expectation_given', False),
                    salary_amount=app_data.get('salary_amount'),
                    salary_currency=app_data.get('salary_currency', 'EUR'),
                    salary_period=app_data.get('salary_period', 'year'),
                    contact_person=app_data.get('contact_person'),
                    company_address=app_data.get('company_address'),
                    website=app_data.get('website'),
                    job_url=app_data.get('job_url'),
                    location=app_data.get('location'),
                    remote_possible=app_data.get('remote_possible', False),
                    source=app_data.get('source'),
                    notes=app_data.get('notes')
                )
                if app_data.get('sent_date'):
                    app.sent_date = datetime.fromisoformat(app_data['sent_date']).date()
                db.session.add(app)
                imported_counts['applications'] += 1
        
        # Vorlagen importieren
        for tpl_data in data.get('templates', []):
            existing = Template.query.filter_by(
                name=tpl_data.get('name'),
                user_id=tpl_data.get('user_id') or current_user.id
            ).first()
            
            if not existing:
                tpl = Template(
                    user_id=tpl_data.get('user_id') or current_user.id,
                    name=tpl_data.get('name'),
                    description=tpl_data.get('description'),
                    content=tpl_data.get('content'),
                    is_default=tpl_data.get('is_default', False)
                )
                db.session.add(tpl)
                imported_counts['templates'] += 1
        
        db.session.commit()
        
        flash(f'Import erfolgreich! {imported_counts["applications"]} Bewerbungen, {imported_counts["templates"]} Vorlagen importiert.', 'success')
        
    except json.JSONDecodeError:
        flash('Ungültiges JSON-Format!', 'error')
    except Exception as e:
        flash(f'Fehler beim Import: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin_database'))


@app.route('/admin/applications/<int:id>/restore', methods=['POST'])
@login_required
@admin_required
def admin_restore_application(id):
    """Admin: Soft-gelöschte Bewerbung wiederherstellen"""
    app = Application.query.get_or_404(id)
    app.is_deleted = False
    app.deleted_at = None
    db.session.commit()
    flash(f'Bewerbung "{app.company_name}" wurde wiederhergestellt.', 'success')
    return redirect(url_for('admin_database'))


@app.route('/admin/deleted/<int:id>/restore', methods=['POST'])
@login_required
@admin_required
def admin_restore_deleted(id):
    """Admin: Gelöschten Eintrag aus dem Archiv wiederherstellen"""
    record = DeletedRecord.query.get_or_404(id)
    
    try:
        data = json.loads(record.record_data)
        
        if record.table_name == 'applications':
            app = Application(
                user_id=data.get('user_id'),
                company_name=data.get('company_name'),
                job_title=data.get('job_title'),
                status=data.get('status', 'draft'),
                feedback=data.get('feedback', 'unknown'),
                response_received=data.get('response_received', False),
                salary_expectation_given=data.get('salary_expectation_given', False),
                salary_amount=data.get('salary_amount'),
                salary_currency=data.get('salary_currency', 'EUR'),
                salary_period=data.get('salary_period', 'year'),
                contact_person=data.get('contact_person'),
                company_address=data.get('company_address'),
                website=data.get('website'),
                job_url=data.get('job_url'),
                location=data.get('location'),
                remote_possible=data.get('remote_possible', False),
                source=data.get('source'),
                notes=data.get('notes')
            )
            if data.get('sent_date'):
                app.sent_date = datetime.fromisoformat(data['sent_date']).date()
            db.session.add(app)
            
        elif record.table_name == 'users':
            # Benutzer können nicht automatisch wiederhergestellt werden (Passwort fehlt)
            flash('Benutzer können nicht automatisch wiederhergestellt werden. Bitte manuell neu anlegen.', 'warning')
            return redirect(url_for('admin_database'))
        
        # Archiv-Eintrag löschen
        db.session.delete(record)
        db.session.commit()
        
        flash(f'Eintrag aus {record.table_name} wurde wiederhergestellt.', 'success')
        
    except Exception as e:
        flash(f'Fehler bei der Wiederherstellung: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin_database'))


@app.route('/admin/export/<table>')
@login_required
@admin_required
def admin_export_table(table):
    """Admin: Einzelne Tabelle exportieren (CSV oder JSON)"""
    format_type = request.args.get('format', 'csv')
    
    if table == 'users':
        data = []
        for user in User.query.all():
            data.append({
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'is_active': user.is_active,
                'is_admin': user.is_admin,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None
            })
        filename = f'benutzer_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
    elif table == 'applications':
        data = []
        for app in Application.query.all():
            data.append({
                'id': app.id,
                'user_id': app.user_id,
                'company_name': app.company_name,
                'job_title': app.job_title,
                'sent_date': app.sent_date.isoformat() if app.sent_date else None,
                'status': app.status,
                'feedback': app.feedback,
                'response_received': app.response_received,
                'salary_expectation_given': app.salary_expectation_given,
                'salary_amount': float(app.salary_amount) if app.salary_amount else None,
                'salary_currency': app.salary_currency,
                'salary_period': app.salary_period,
                'contact_person': app.contact_person,
                'company_address': app.company_address,
                'website': app.website,
                'job_url': app.job_url,
                'location': app.location,
                'remote_possible': app.remote_possible,
                'source': app.source,
                'notes': app.notes,
                'is_deleted': app.is_deleted,
                'created_at': app.created_at.isoformat() if app.created_at else None
            })
        filename = f'bewerbungen_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
    elif table == 'templates':
        data = []
        for tpl in Template.query.all():
            data.append({
                'id': tpl.id,
                'user_id': tpl.user_id,
                'name': tpl.name,
                'description': tpl.description,
                'content': tpl.content,
                'is_default': tpl.is_default,
                'created_at': tpl.created_at.isoformat() if tpl.created_at else None
            })
        filename = f'vorlagen_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
    elif table == 'letters':
        data = []
        for letter in Letter.query.all():
            data.append({
                'id': letter.id,
                'application_id': letter.application_id,
                'template_used': letter.template_used,
                'rendered_text': letter.rendered_text,
                'created_at': letter.created_at.isoformat() if letter.created_at else None
            })
        filename = f'anschreiben_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        
    else:
        flash('Unbekannte Tabelle!', 'error')
        return redirect(url_for('admin_database'))
    
    if format_type == 'json':
        output = json.dumps(data, ensure_ascii=False, indent=2)
        return Response(
            output,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}.json'}
        )
    else:
        # CSV Export
        if not data:
            flash('Keine Daten zum Exportieren!', 'warning')
            return redirect(url_for('admin_database'))
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys(), delimiter=';')
        writer.writeheader()
        writer.writerows(data)
        output.seek(0)
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}.csv'}
        )


@app.route('/admin/import/<table>', methods=['POST'])
@login_required
@admin_required
def admin_import_table(table):
    """Admin: Einzelne Tabelle importieren (CSV oder JSON)"""
    if 'file' not in request.files:
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('admin_database'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('admin_database'))
    
    try:
        # Dateiformat erkennen
        if file.filename.endswith('.json'):
            data = json.load(file)
        elif file.filename.endswith('.csv'):
            content = file.read().decode('utf-8')
            reader = csv.DictReader(io.StringIO(content), delimiter=';')
            data = list(reader)
        else:
            flash('Nur JSON oder CSV Dateien sind erlaubt!', 'error')
            return redirect(url_for('admin_database'))
        
        imported_count = 0
        
        if table == 'applications':
            for row in data:
                # Prüfen ob bereits existiert
                existing = Application.query.filter_by(
                    company_name=row.get('company_name'),
                    job_title=row.get('job_title')
                ).first()
                
                if not existing:
                    app = Application(
                        user_id=row.get('user_id') or current_user.id,
                        company_name=row.get('company_name'),
                        job_title=row.get('job_title'),
                        status=row.get('status', 'draft'),
                        feedback=row.get('feedback', 'unknown'),
                        response_received=str(row.get('response_received', 'False')).lower() in ('true', '1', 'ja'),
                        salary_expectation_given=str(row.get('salary_expectation_given', 'False')).lower() in ('true', '1', 'ja'),
                        salary_amount=float(row['salary_amount']) if row.get('salary_amount') else None,
                        salary_currency=row.get('salary_currency', 'EUR'),
                        salary_period=row.get('salary_period', 'year'),
                        contact_person=row.get('contact_person'),
                        company_address=row.get('company_address'),
                        website=row.get('website'),
                        job_url=row.get('job_url'),
                        location=row.get('location'),
                        remote_possible=str(row.get('remote_possible', 'False')).lower() in ('true', '1', 'ja'),
                        source=row.get('source'),
                        notes=row.get('notes')
                    )
                    if row.get('sent_date') and row['sent_date'] != 'None':
                        try:
                            app.sent_date = datetime.fromisoformat(row['sent_date']).date()
                        except:
                            pass
                    db.session.add(app)
                    imported_count += 1
                    
        elif table == 'templates':
            for row in data:
                existing = Template.query.filter_by(name=row.get('name')).first()
                
                if not existing:
                    tpl = Template(
                        user_id=row.get('user_id') or current_user.id,
                        name=row.get('name'),
                        description=row.get('description'),
                        content=row.get('content'),
                        is_default=str(row.get('is_default', 'False')).lower() in ('true', '1', 'ja')
                    )
                    db.session.add(tpl)
                    imported_count += 1
        else:
            flash('Import für diese Tabelle nicht unterstützt!', 'error')
            return redirect(url_for('admin_database'))
        
        db.session.commit()
        flash(f'{imported_count} Einträge erfolgreich importiert!', 'success')
        
    except Exception as e:
        flash(f'Fehler beim Import: {str(e)}', 'error')
        db.session.rollback()
    
    return redirect(url_for('admin_database'))


@app.route('/logout')
@login_required
def logout():
    """Benutzer abmelden"""
    logout_user()
    flash('Sie wurden erfolgreich abgemeldet.', 'success')
    return redirect(url_for('login'))


# ============================================================================
# Dashboard / Index
# ============================================================================

@app.route('/')
@login_required
def index():
    """Dashboard mit Statistiken und letzten Bewerbungen"""
    # Nur nicht-gelöschte Bewerbungen des aktuellen Benutzers zählen
    active_apps = Application.query.filter(
        Application.user_id == current_user.id,
        db.or_(Application.is_deleted == False, Application.is_deleted == None)
    )
    stats = {
        'total': active_apps.count(),
        'pending': active_apps.filter(Application.status.in_(['draft', 'sent'])).count(),
        'interviews': active_apps.filter(Application.status == 'interview').count(),
        'offers': active_apps.filter(Application.status == 'offer').count()
    }
    recent_applications = Application.query.filter(
        Application.user_id == current_user.id,
        db.or_(Application.is_deleted == False, Application.is_deleted == None)
    ).order_by(
        Application.sent_date.desc().nullslast(),
        Application.created_at.desc()
    ).limit(5).all()
    
    return render_template('index.html', stats=stats, recent_applications=recent_applications)


# ============================================================================
# Applications CRUD
# ============================================================================

@app.route('/applications')
@login_required
def applications_list():
    """Liste aller Bewerbungen mit Filtern"""
    # Nur nicht-gelöschte Bewerbungen des aktuellen Benutzers anzeigen
    query = Application.query.filter(
        Application.user_id == current_user.id,
        db.or_(Application.is_deleted == False, Application.is_deleted == None)
    )
    
    # Filter: Status
    status = request.args.get('status')
    if status:
        query = query.filter_by(status=status)
    
    # Filter: Feedback
    feedback = request.args.get('feedback')
    if feedback:
        query = query.filter_by(feedback=feedback)
    
    # Filter: Antwort erhalten
    response = request.args.get('response')
    if response == 'yes':
        query = query.filter_by(response_received=True)
    elif response == 'no':
        query = query.filter_by(response_received=False)
    
    # Filter: Suche
    search = request.args.get('search')
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                Application.company_name.ilike(search_term),
                Application.job_title.ilike(search_term),
                Application.location.ilike(search_term)
            )
        )
    
    # Sortierung: Nach Versanddatum (neueste zuerst), dann nach Erstellungsdatum
    applications = query.order_by(
        Application.sent_date.desc().nullslast(),
        Application.created_at.desc()
    ).all()
    
    return render_template(
        'applications/list.html',
        applications=applications,
        status_choices=Application.STATUS_CHOICES,
        feedback_choices=Application.FEEDBACK_CHOICES
    )


@app.route('/applications/new', methods=['GET', 'POST'])
@login_required
def application_new():
    """Neue Bewerbung erstellen"""
    form = ApplicationForm()
    
    if form.validate_on_submit():
        application = Application(
            user_id=current_user.id,
            company_name=form.company_name.data,
            job_title=form.job_title.data,
            sent_date=form.sent_date.data,
            status=form.status.data,
            feedback=form.feedback.data,
            response_received=form.response_received.data,
            salary_expectation_given=form.salary_expectation_given.data,
            salary_amount=form.salary_amount.data if form.salary_expectation_given.data else None,
            salary_currency=form.salary_currency.data,
            salary_period=form.salary_period.data,
            contact_person=form.contact_person.data,
            company_address=form.company_address.data,
            website=form.website.data or None,
            job_url=form.job_url.data or None,
            location=form.location.data,
            remote_possible=form.remote_possible.data,
            source=form.source.data or None,
            notes=form.notes.data
        )
        db.session.add(application)
        db.session.commit()
        
        flash('Bewerbung erfolgreich erstellt!', 'success')
        return redirect(url_for('applications_list'))
    
    return render_template('applications/form.html', form=form, application=None)


@app.route('/applications/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def application_edit(id):
    """Bewerbung bearbeiten"""
    application = Application.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = ApplicationForm(obj=application)
    
    if form.validate_on_submit():
        application.company_name = form.company_name.data
        application.job_title = form.job_title.data
        application.sent_date = form.sent_date.data
        application.status = form.status.data
        application.feedback = form.feedback.data
        application.response_received = form.response_received.data
        application.salary_expectation_given = form.salary_expectation_given.data
        application.salary_amount = form.salary_amount.data if form.salary_expectation_given.data else None
        application.salary_currency = form.salary_currency.data
        application.salary_period = form.salary_period.data
        application.contact_person = form.contact_person.data
        application.company_address = form.company_address.data
        application.website = form.website.data or None
        application.job_url = form.job_url.data or None
        application.location = form.location.data
        application.remote_possible = form.remote_possible.data
        application.source = form.source.data or None
        application.notes = form.notes.data
        
        db.session.commit()
        
        flash('Bewerbung erfolgreich aktualisiert!', 'success')
        return redirect(url_for('applications_list'))
    
    return render_template('applications/form.html', form=form, application=application)


@app.route('/applications/<int:id>/delete', methods=['POST'])
@login_required
def application_delete(id):
    """Bewerbung löschen (Soft-Delete - Daten werden archiviert)"""
    application = Application.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    # Bewerbungs-Daten archivieren
    app_data = {
        'id': application.id,
        'user_id': application.user_id,
        'company_name': application.company_name,
        'job_title': application.job_title,
        'sent_date': application.sent_date.isoformat() if application.sent_date else None,
        'status': application.status,
        'feedback': application.feedback,
        'response_received': application.response_received,
        'salary_expectation_given': application.salary_expectation_given,
        'salary_amount': float(application.salary_amount) if application.salary_amount else None,
        'salary_currency': application.salary_currency,
        'salary_period': application.salary_period,
        'contact_person': application.contact_person,
        'company_address': application.company_address,
        'website': application.website,
        'job_url': application.job_url,
        'location': application.location,
        'remote_possible': application.remote_possible,
        'source': application.source,
        'notes': application.notes,
        'created_at': application.created_at.isoformat() if application.created_at else None
    }
    
    # In Archiv speichern
    deleted_record = DeletedRecord(
        table_name='applications',
        record_id=application.id,
        record_data=json.dumps(app_data),
        deleted_by=current_user.id
    )
    db.session.add(deleted_record)
    
    # Soft-Delete: Markieren statt löschen
    application.is_deleted = True
    application.deleted_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('Bewerbung wurde in den Papierkorb verschoben. Sie kann vom Admin wiederhergestellt werden.', 'success')
    return redirect(url_for('applications_list'))


# ============================================================================
# Text Generator
# ============================================================================

@app.route('/generator')
@login_required
def text_generator_page():
    """Textgenerator Seite"""
    application = None
    application_id = request.args.get('application_id')
    template_id = request.args.get('template_id')
    
    if application_id:
        application = Application.query.filter_by(id=application_id, user_id=current_user.id).first()
    
    # Benutzereinstellungen laden oder erstellen
    user_settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    if not user_settings:
        # Neue Einstellungen mit Daten aus User-Account vorausfüllen
        user_settings = UserSettings(
            user_id=current_user.id,
            your_name=current_user.name or '',
            your_email=current_user.email or ''
        )
        db.session.add(user_settings)
        db.session.commit()
    
    # Platzhalter für die UI
    placeholders = text_generator.get_placeholder_list()
    
    # Alle Vorlagen des Benutzers laden
    templates = Template.query.filter_by(user_id=current_user.id).order_by(Template.name).all()
    
    return render_template(
        'generator.html',
        application=application,
        user_settings=user_settings,
        placeholders=placeholders,
        templates=templates,
        today=date.today().strftime('%Y-%m-%d')
    )


@app.route('/api/generate', methods=['POST'])
@login_required
def api_generate():
    """API-Endpunkt für Textgenerierung"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Keine Daten erhalten'})
    
    template = data.get('template', '')
    if not template:
        return jsonify({'success': False, 'error': 'Keine Vorlage angegeben'})
    
    # Kontext für das Template
    context = {
        'company': data.get('company', ''),
        'company_address': data.get('company_address', ''),
        'job_title': data.get('job_title', ''),
        'subject': data.get('subject', ''),
        'date': data.get('date', ''),
        'contact_person': data.get('contact_person', ''),
        'your_name': data.get('your_name', ''),
        'your_address': data.get('your_address', ''),
        'your_email': data.get('your_email', ''),
        'your_phone': data.get('your_phone', '')
    }
    
    # Datum formatieren wenn vorhanden
    if context['date']:
        try:
            date_obj = datetime.strptime(context['date'], '%Y-%m-%d')
            context['date'] = date_obj.strftime('%d.%m.%Y')
        except ValueError:
            pass
    
    # Text generieren
    rendered_text = text_generator.render(template, context)
    
    return jsonify({'success': True, 'text': rendered_text})


@app.route('/api/letters', methods=['POST'])
@login_required
def api_save_letter():
    """API-Endpunkt zum Speichern eines generierten Anschreibens"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Keine Daten erhalten'})
    
    application_id = data.get('application_id')
    if not application_id:
        return jsonify({'success': False, 'error': 'Keine Bewerbungs-ID angegeben'})
    
    application = Application.query.filter_by(id=application_id, user_id=current_user.id).first()
    if not application:
        return jsonify({'success': False, 'error': 'Bewerbung nicht gefunden'})
    
    letter = Letter(
        application_id=application_id,
        template_used=data.get('template_used', ''),
        rendered_text=data.get('rendered_text', '')
    )
    db.session.add(letter)
    db.session.commit()
    
    return jsonify({'success': True, 'letter_id': letter.id})


@app.route('/api/save-draft', methods=['POST'])
@login_required
def api_save_draft():
    """API-Endpunkt zum Speichern einer neuen Bewerbung als Entwurf"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Keine Daten erhalten'})
    
    company = data.get('company', '').strip()
    job_title = data.get('job_title', '').strip()
    
    if not company:
        return jsonify({'success': False, 'error': 'Unternehmen ist erforderlich'})
    if not job_title:
        return jsonify({'success': False, 'error': 'Stellenbezeichnung ist erforderlich'})
    
    # Neue Bewerbung erstellen
    application = Application(
        company_name=company,
        job_title=job_title,
        company_address=data.get('company_address', ''),
        contact_person=data.get('contact_person', ''),
        status='draft'  # Status: Entwurf
    )
    
    db.session.add(application)
    db.session.commit()
    
    # Optional: Generiertes Anschreiben speichern
    generated_text = data.get('generated_text', '')
    template_used = data.get('template_used', '')
    
    if generated_text:
        letter = Letter(
            application_id=application.id,
            template_used=template_used,
            rendered_text=generated_text
        )
        db.session.add(letter)
        db.session.commit()
    
    return jsonify({
        'success': True, 
        'application_id': application.id,
        'message': f'Bewerbung bei {company} als Entwurf gespeichert'
    })


@app.route('/api/preview-pdf', methods=['POST'])
@login_required
def api_preview_pdf():
    """API-Endpunkt für die PDF-Vorschau (gibt PDF als Blob zurück)"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Keine Daten erhalten'}), 400
    
    body_text = data.get('body_text', '')
    if not body_text:
        return jsonify({'success': False, 'error': 'Kein Text'}), 400
    
    # PDF-Daten vorbereiten
    pdf_data = {
        'your_name': data.get('your_name', ''),
        'your_address': data.get('your_address', ''),
        'your_email': data.get('your_email', ''),
        'your_phone': data.get('your_phone', ''),
        'company': data.get('company', ''),
        'company_address': data.get('company_address', ''),
        'contact_person': data.get('contact_person', ''),
        'date': data.get('date', ''),
        'subject': data.get('subject', ''),
        'job_title': data.get('job_title', ''),
        'body_text': body_text,
        'html_content': data.get('html_content', ''),
        'margins': data.get('margins', {})
    }
    
    # PDF generieren
    pdf_buffer = pdf_generator.generate_pdf(pdf_data)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=False
    )


@app.route('/api/export-pdf', methods=['POST'])
@login_required
def api_export_pdf():
    """API-Endpunkt zum Exportieren des generierten Textes als DIN-Brief PDF"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'error': 'Keine Daten erhalten'})
    
    body_text = data.get('body_text', '')
    if not body_text:
        return jsonify({'success': False, 'error': 'Kein Text zum Exportieren'})
    
    # PDF-Daten vorbereiten
    pdf_data = {
        'your_name': data.get('your_name', ''),
        'your_address': data.get('your_address', ''),
        'your_email': data.get('your_email', ''),
        'your_phone': data.get('your_phone', ''),
        'company': data.get('company', ''),
        'company_address': data.get('company_address', ''),
        'contact_person': data.get('contact_person', ''),
        'date': data.get('date', ''),
        'subject': data.get('subject', ''),
        'job_title': data.get('job_title', ''),
        'body_text': body_text,
        'html_content': data.get('html_content', ''),
        'margins': data.get('margins', {})
    }
    
    # PDF generieren
    pdf_buffer = pdf_generator.generate_pdf(pdf_data)
    
    # Dateiname generieren
    filename = generate_filename(
        data.get('company', ''),
        data.get('job_title', ''),
        data.get('date')
    )
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


# ============================================================================
# Dokumente Upload/Download
# ============================================================================

@app.route('/applications/<int:application_id>/documents', methods=['POST'])
@login_required
def upload_document(application_id):
    """Dokument zu einer Bewerbung hochladen"""
    # Prüfen ob Bewerbung existiert UND dem aktuellen Benutzer gehört
    application = Application.query.filter_by(id=application_id, user_id=current_user.id).first()
    if not application:
        flash('Bewerbung nicht gefunden oder keine Berechtigung!', 'error')
        return redirect(url_for('applications_list'))
    
    if 'document' not in request.files:
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('application_edit', id=application_id))
    
    file = request.files['document']
    
    if file.filename == '':
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('application_edit', id=application_id))
    
    if file and allowed_file(file.filename):
        # Sicheren Dateinamen erstellen
        original_filename = secure_filename(file.filename)
        # Eindeutigen Dateinamen generieren
        file_ext = original_filename.rsplit('.', 1)[1].lower()
        stored_filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        # Benutzer-spezifisches Verzeichnis erstellen
        user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
        if not os.path.exists(user_upload_dir):
            os.makedirs(user_upload_dir)
        
        # Datei im Benutzer-Verzeichnis speichern
        file_path = os.path.join(user_upload_dir, stored_filename)
        file.save(file_path)
        
        # Dateigröße ermitteln
        file_size = os.path.getsize(file_path)
        
        # Dokument in Datenbank speichern
        document = Document(
            application_id=application_id,
            filename=original_filename,
            stored_filename=stored_filename,
            file_type=file.content_type,
            file_size=file_size,
            description=request.form.get('description', '')
        )
        db.session.add(document)
        db.session.commit()
        
        flash(f'Dokument "{original_filename}" erfolgreich hochgeladen!', 'success')
    else:
        flash('Dateityp nicht erlaubt! Erlaubt sind: PDF, DOC, DOCX, PNG, JPG', 'error')
    
    return redirect(url_for('application_edit', id=application_id))


@app.route('/documents/<int:document_id>')
@login_required
def download_document(document_id):
    """Dokument herunterladen"""
    document = db.session.get(Document, document_id)
    if not document:
        flash('Dokument nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
    # Prüfen ob Dokument zur Bewerbung des aktuellen Benutzers gehört
    application = Application.query.filter_by(id=document.application_id, user_id=current_user.id).first()
    if not application:
        flash('Keine Berechtigung für dieses Dokument!', 'error')
        return redirect(url_for('applications_list'))
    
    # Datei im Benutzer-Verzeichnis suchen
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), document.stored_filename)
    
    # Fallback: Alte Dateien im Root-Verzeichnis
    if not os.path.exists(file_path):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.stored_filename)
    
    if not os.path.exists(file_path):
        flash('Datei nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
    return send_file(
        file_path,
        as_attachment=True,
        download_name=document.filename
    )


@app.route('/documents/<int:document_id>/view')
@login_required
def view_document(document_id):
    """Dokument im Browser anzeigen (für PDFs)"""
    document = db.session.get(Document, document_id)
    if not document:
        flash('Dokument nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
    # Prüfen ob Dokument zur Bewerbung des aktuellen Benutzers gehört
    application = Application.query.filter_by(id=document.application_id, user_id=current_user.id).first()
    if not application:
        flash('Keine Berechtigung für dieses Dokument!', 'error')
        return redirect(url_for('applications_list'))
    
    # Datei im Benutzer-Verzeichnis suchen
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), document.stored_filename)
    
    # Fallback: Alte Dateien im Root-Verzeichnis
    if not os.path.exists(file_path):
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.stored_filename)
    
    if not os.path.exists(file_path):
        flash('Datei nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
    return send_file(
        file_path,
        as_attachment=False,
        download_name=document.filename
    )


@app.route('/documents/<int:document_id>/delete', methods=['POST'])
@login_required
def delete_document(document_id):
    """Dokument löschen"""
    document = db.session.get(Document, document_id)
    if not document:
        flash('Dokument nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
    # Prüfen ob Dokument zur Bewerbung des aktuellen Benutzers gehört
    application = Application.query.filter_by(id=document.application_id, user_id=current_user.id).first()
    if not application:
        flash('Keine Berechtigung für dieses Dokument!', 'error')
        return redirect(url_for('applications_list'))
    
    application_id = document.application_id
    
    # Datei vom Dateisystem löschen (Benutzer-Verzeichnis)
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id), document.stored_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    else:
        # Fallback: Alte Dateien im Root-Verzeichnis
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.stored_filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    
    # Aus Datenbank löschen
    db.session.delete(document)
    db.session.commit()
    
    flash('Dokument erfolgreich gelöscht!', 'success')
    return redirect(url_for('application_edit', id=application_id))


# ============================================================================
# Settings
# ============================================================================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Benutzereinstellungen"""
    user_settings = UserSettings.query.filter_by(user_id=current_user.id).first()
    
    if not user_settings:
        # Neue Einstellungen mit Daten aus User-Account vorausfüllen
        user_settings = UserSettings(
            user_id=current_user.id,
            your_name=current_user.name,
            your_email=current_user.email
        )
        db.session.add(user_settings)
        db.session.commit()
    
    form = UserSettingsForm(obj=user_settings)
    
    if form.validate_on_submit():
        user_settings.your_name = form.your_name.data
        user_settings.your_address = form.your_address.data
        user_settings.your_email = form.your_email.data
        user_settings.your_phone = form.your_phone.data
        
        db.session.commit()
        
        flash('Einstellungen erfolgreich gespeichert!', 'success')
        return redirect(url_for('settings'))
    
    # Vorlagen laden
    templates = Template.query.filter_by(user_id=current_user.id).order_by(Template.name).all()
    
    return render_template('settings.html', form=form, templates=templates)


# ============================================================================
# Templates CRUD
# ============================================================================

@app.route('/templates/new', methods=['GET', 'POST'])
@login_required
def template_new():
    """Neue Vorlage erstellen"""
    form = TemplateForm()
    
    if form.validate_on_submit():
        # Wenn als Standard markiert, andere Standard-Markierungen entfernen
        if form.is_default.data:
            Template.query.filter_by(user_id=current_user.id).update({Template.is_default: False})
        
        template = Template(
            user_id=current_user.id,
            name=form.name.data,
            description=form.description.data,
            content=form.content.data,
            is_default=form.is_default.data
        )
        db.session.add(template)
        db.session.commit()
        
        flash('Vorlage erfolgreich erstellt!', 'success')
        return redirect(url_for('settings'))
    
    # Platzhalter für die UI
    placeholders = text_generator.get_placeholder_list()
    
    return render_template('templates/form.html', form=form, template=None, placeholders=placeholders)


@app.route('/templates/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def template_edit(id):
    """Vorlage bearbeiten"""
    template = Template.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    form = TemplateForm(obj=template)
    
    if form.validate_on_submit():
        # Wenn als Standard markiert, andere Standard-Markierungen entfernen
        if form.is_default.data:
            Template.query.filter(Template.user_id == current_user.id, Template.id != id).update({Template.is_default: False})
        
        template.name = form.name.data
        template.description = form.description.data
        template.content = form.content.data
        template.is_default = form.is_default.data
        
        db.session.commit()
        
        flash('Vorlage erfolgreich aktualisiert!', 'success')
        return redirect(url_for('settings'))
    
    # Platzhalter für die UI
    placeholders = text_generator.get_placeholder_list()
    
    return render_template('templates/form.html', form=form, template=template, placeholders=placeholders)


@app.route('/templates/<int:id>/delete', methods=['POST'])
@login_required
def template_delete(id):
    """Vorlage löschen"""
    template = Template.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    
    db.session.delete(template)
    db.session.commit()
    
    flash('Vorlage erfolgreich gelöscht!', 'success')
    return redirect(url_for('settings'))


@app.route('/api/templates/<int:id>')
@login_required
def api_get_template(id):
    """API-Endpunkt zum Abrufen einer Vorlage"""
    template = Template.query.filter_by(id=id, user_id=current_user.id).first_or_404()
    return jsonify({
        'success': True,
        'template': {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'content': template.content,
            'is_default': template.is_default
        }
    })


# ============================================================================
# Export
# ============================================================================

@app.route('/export/csv')
@login_required
def export_csv():
    """Exportiert alle Bewerbungen des Benutzers als CSV"""
    applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.id).all()
    
    # CSV erstellen
    output = io.StringIO()
    writer = csv.writer(output, delimiter=';', quotechar='"')
    
    # Header
    writer.writerow([
        'Nr.', 'Unternehmen', 'Position', 'Status', 'Feedback', 
        'Versanddatum', 'Antwort erhalten', 'Gehaltsvorstellung', 
        'Gehalt', 'Währung', 'Zeitraum', 'Ansprechpartner',
        'Adresse', 'Website', 'Stellen-URL', 'Standort', 
        'Remote möglich', 'Quelle', 'Notizen', 'Erstellt', 'Aktualisiert'
    ])
    
    # Daten
    for app in applications:
        writer.writerow([
            app.id,
            app.company_name,
            app.job_title,
            dict(Application.STATUS_CHOICES).get(app.status, app.status),
            dict(Application.FEEDBACK_CHOICES).get(app.feedback, app.feedback),
            app.sent_date.strftime('%d.%m.%Y') if app.sent_date else '',
            'Ja' if app.response_received else 'Nein',
            'Ja' if app.salary_expectation_given else 'Nein',
            str(app.salary_amount) if app.salary_amount else '',
            app.salary_currency,
            'Jahr' if app.salary_period == 'year' else 'Monat',
            app.contact_person or '',
            app.company_address or '',
            app.website or '',
            app.job_url or '',
            app.location or '',
            'Ja' if app.remote_possible else 'Nein',
            dict(Application.SOURCE_CHOICES).get(app.source, app.source or ''),
            app.notes or '',
            app.created_at.strftime('%d.%m.%Y %H:%M') if app.created_at else '',
            app.last_update.strftime('%d.%m.%Y %H:%M') if app.last_update else ''
        ])
    
    # Response erstellen
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={
            'Content-Disposition': f'attachment; filename=bewerbungen_{date.today().strftime("%Y%m%d")}.csv'
        }
    )


# ============================================================================
# Legal Pages
# ============================================================================

@app.route('/datenschutz')
def privacy():
    """Datenschutzerklärung"""
    return render_template('legal/privacy.html')


@app.route('/impressum')
def imprint():
    """Impressum"""
    return render_template('legal/imprint.html')


@app.route('/robots.txt')
def robots_txt():
    """Robots.txt - verhindert Indexierung durch Suchmaschinen"""
    return send_file('static/robots.txt', mimetype='text/plain')


# ============================================================================
# Run
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5001)
