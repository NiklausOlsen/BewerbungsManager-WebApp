"""
BewerbungsManager Web-App
Eine Flask-Anwendung zur Verwaltung von Bewerbungen und Generierung von Anschreiben
"""
import os
import csv
import io
from datetime import date, datetime
from flask import (
    Flask, render_template, request, redirect, url_for, 
    flash, jsonify, Response, send_file
)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
import uuid
from werkzeug.utils import secure_filename
from config import Config
from models import db, Application, UserSettings, Letter, Template, Document, User
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
    """Admin: Benutzer löschen"""
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Sie können sich nicht selbst löschen.', 'error')
        return redirect(url_for('admin_users'))
    email = user.email
    db.session.delete(user)
    db.session.commit()
    flash(f'Benutzer {email} wurde gelöscht.', 'success')
    return redirect(url_for('admin_users'))


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
    stats = {
        'total': Application.query.count(),
        'pending': Application.query.filter(Application.status.in_(['draft', 'sent'])).count(),
        'interviews': Application.query.filter_by(status='interview').count(),
        'offers': Application.query.filter_by(status='offer').count()
    }
    recent_applications = Application.query.order_by(
        Application.last_update.desc()
    ).limit(5).all()
    
    return render_template('index.html', stats=stats, recent_applications=recent_applications)


# ============================================================================
# Applications CRUD
# ============================================================================

@app.route('/applications')
@login_required
def applications_list():
    """Liste aller Bewerbungen mit Filtern"""
    query = Application.query
    
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
    
    # Sortierung: Neueste zuerst
    applications = query.order_by(Application.last_update.desc()).all()
    
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
    application = Application.query.get_or_404(id)
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
    """Bewerbung löschen"""
    application = Application.query.get_or_404(id)
    
    # Auch verknüpfte Letters löschen
    Letter.query.filter_by(application_id=id).delete()
    
    db.session.delete(application)
    db.session.commit()
    
    flash('Bewerbung erfolgreich gelöscht!', 'success')
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
        application = Application.query.get(application_id)
    
    user_settings = UserSettings.query.first()
    
    # Platzhalter für die UI
    placeholders = text_generator.get_placeholder_list()
    
    # Alle Vorlagen laden
    templates = Template.query.order_by(Template.name).all()
    
    # Standard-Template bestimmen
    default_template = TextGenerator.DEFAULT_TEMPLATE
    selected_template = None
    
    if template_id:
        selected_template = Template.query.get(template_id)
        if selected_template:
            default_template = selected_template.content
    elif templates:
        # Suche nach Standard-Vorlage
        default_tpl = Template.query.filter_by(is_default=True).first()
        if default_tpl:
            selected_template = default_tpl
            default_template = default_tpl.content
        else:
            # Erste Vorlage verwenden
            selected_template = templates[0]
            default_template = templates[0].content
    
    return render_template(
        'generator.html',
        application=application,
        user_settings=user_settings,
        placeholders=placeholders,
        default_template=default_template,
        templates=templates,
        selected_template=selected_template,
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
    
    application = Application.query.get(application_id)
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
        'body_text': body_text
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
    application = db.session.get(Application, application_id)
    if not application:
        flash('Bewerbung nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
    if 'document' not in request.files:
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('application_edit', application_id=application_id))
    
    file = request.files['document']
    
    if file.filename == '':
        flash('Keine Datei ausgewählt!', 'error')
        return redirect(url_for('application_edit', application_id=application_id))
    
    if file and allowed_file(file.filename):
        # Sicheren Dateinamen erstellen
        original_filename = secure_filename(file.filename)
        # Eindeutigen Dateinamen generieren
        file_ext = original_filename.rsplit('.', 1)[1].lower()
        stored_filename = f"{uuid.uuid4().hex}.{file_ext}"
        
        # Datei speichern
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], stored_filename)
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
    
    return redirect(url_for('application_edit', application_id=application_id))


@app.route('/documents/<int:document_id>')
@login_required
def download_document(document_id):
    """Dokument herunterladen"""
    document = db.session.get(Document, document_id)
    if not document:
        flash('Dokument nicht gefunden!', 'error')
        return redirect(url_for('applications_list'))
    
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
    
    application_id = document.application_id
    
    # Datei vom Dateisystem löschen
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], document.stored_filename)
    if os.path.exists(file_path):
        os.remove(file_path)
    
    # Aus Datenbank löschen
    db.session.delete(document)
    db.session.commit()
    
    flash('Dokument erfolgreich gelöscht!', 'success')
    return redirect(url_for('application_edit', application_id=application_id))


# ============================================================================
# Settings
# ============================================================================

@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Benutzereinstellungen"""
    user_settings = UserSettings.query.first()
    
    if not user_settings:
        user_settings = UserSettings()
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
    templates = Template.query.order_by(Template.name).all()
    
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
            Template.query.update({Template.is_default: False})
        
        template = Template(
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
    template = Template.query.get_or_404(id)
    form = TemplateForm(obj=template)
    
    if form.validate_on_submit():
        # Wenn als Standard markiert, andere Standard-Markierungen entfernen
        if form.is_default.data:
            Template.query.filter(Template.id != id).update({Template.is_default: False})
        
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
    template = Template.query.get_or_404(id)
    
    db.session.delete(template)
    db.session.commit()
    
    flash('Vorlage erfolgreich gelöscht!', 'success')
    return redirect(url_for('settings'))


@app.route('/api/templates/<int:id>')
@login_required
def api_get_template(id):
    """API-Endpunkt zum Abrufen einer Vorlage"""
    template = Template.query.get_or_404(id)
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
    """Exportiert alle Bewerbungen als CSV"""
    applications = Application.query.order_by(Application.id).all()
    
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
# Run
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000)
