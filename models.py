from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """Benutzer-Model für Authentifizierung"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=False)  # Neue Benutzer müssen erst freigeschaltet werden
    is_admin = db.Column(db.Boolean, default=False)   # Admin-Rolle
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def set_password(self, password):
        """Passwort hashen und speichern"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Passwort überprüfen"""
        return check_password_hash(self.password_hash, password)
    
    @property
    def status_text(self):
        """Status als Text"""
        if not self.is_active:
            return 'Wartend'
        return 'Aktiv'

    def __repr__(self):
        return f'<User {self.email}>'


class Application(db.Model):
    """Bewerbungs-Datenmodell"""
    __tablename__ = 'applications'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # Pflichtfelder
    company_name = db.Column(db.String(200), nullable=False)
    job_title = db.Column(db.String(200), nullable=False)
    
    # Datum
    sent_date = db.Column(db.Date, nullable=True)
    
    # Status & Feedback
    status = db.Column(db.String(20), default='draft')  # draft, sent, interview, offer, rejected, withdrawn
    feedback = db.Column(db.String(20), default='unknown')  # unknown, positive, negative
    response_received = db.Column(db.Boolean, default=False)
    
    # Gehalt
    salary_expectation_given = db.Column(db.Boolean, default=False)
    salary_amount = db.Column(db.Numeric(10, 2), nullable=True)
    salary_currency = db.Column(db.String(10), default='EUR')
    salary_period = db.Column(db.String(10), default='year')  # year, month
    
    # Kontakt & Unternehmen
    contact_person = db.Column(db.String(200), nullable=True)
    company_address = db.Column(db.Text, nullable=True)
    website = db.Column(db.String(500), nullable=True)
    job_url = db.Column(db.String(500), nullable=True)
    
    # Standort
    location = db.Column(db.String(200), nullable=True)
    remote_possible = db.Column(db.Boolean, default=False)
    
    # Quelle
    source = db.Column(db.String(50), nullable=True)  # LinkedIn, StepStone, Empfehlung, Website, etc.
    
    # Notizen
    notes = db.Column(db.String(200), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_update = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Status-Optionen
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('sent', 'Versendet'),
        ('interview', 'Vorstellungsgespräch'),
        ('offer', 'Angebot'),
        ('rejected', 'Abgelehnt'),
        ('withdrawn', 'Zurückgezogen')
    ]

    FEEDBACK_CHOICES = [
        ('unknown', 'Unbekannt'),
        ('positive', 'Positiv'),
        ('negative', 'Negativ')
    ]

    SOURCE_CHOICES = [
        ('linkedin', 'LinkedIn'),
        ('stepstone', 'StepStone'),
        ('indeed', 'Indeed'),
        ('xing', 'XING'),
        ('website', 'Unternehmenswebsite'),
        ('empfehlung', 'Empfehlung'),
        ('messe', 'Jobmesse'),
        ('andere', 'Andere')
    ]

    def to_dict(self):
        """Konvertiert das Model zu einem Dictionary"""
        return {
            'id': self.id,
            'company_name': self.company_name,
            'job_title': self.job_title,
            'sent_date': self.sent_date.isoformat() if self.sent_date else None,
            'status': self.status,
            'feedback': self.feedback,
            'response_received': self.response_received,
            'salary_expectation_given': self.salary_expectation_given,
            'salary_amount': float(self.salary_amount) if self.salary_amount else None,
            'salary_currency': self.salary_currency,
            'salary_period': self.salary_period,
            'contact_person': self.contact_person,
            'company_address': self.company_address,
            'website': self.website,
            'job_url': self.job_url,
            'location': self.location,
            'remote_possible': self.remote_possible,
            'source': self.source,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_update': self.last_update.isoformat() if self.last_update else None
        }

    def __repr__(self):
        return f'<Application {self.id}: {self.company_name} - {self.job_title}>'


class UserSettings(db.Model):
    """Benutzereinstellungen für Briefkopf etc."""
    __tablename__ = 'user_settings'

    id = db.Column(db.Integer, primary_key=True)
    your_name = db.Column(db.String(200), nullable=True)
    your_address = db.Column(db.Text, nullable=True)
    your_email = db.Column(db.String(200), nullable=True)
    your_phone = db.Column(db.String(50), nullable=True)
    default_template = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_update = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Letter(db.Model):
    """Gespeicherte Anschreiben-Versionen"""
    __tablename__ = 'letters'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    template_used = db.Column(db.Text, nullable=True)
    rendered_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    application = db.relationship('Application', backref=db.backref('letters', lazy=True))


class Template(db.Model):
    """Gespeicherte Bewerbungsvorlagen"""
    __tablename__ = 'templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    content = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_update = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Template {self.id}: {self.name}>'


class Document(db.Model):
    """Hochgeladene Dokumente zu Bewerbungen (z.B. Stellenausschreibungen)"""
    __tablename__ = 'documents'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)  # Originaler Dateiname
    stored_filename = db.Column(db.String(255), nullable=False)  # Gespeicherter Dateiname (UUID)
    file_type = db.Column(db.String(50), nullable=True)  # z.B. 'application/pdf'
    file_size = db.Column(db.Integer, nullable=True)  # Größe in Bytes
    description = db.Column(db.String(255), nullable=True)  # Optionale Beschreibung
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    application = db.relationship('Application', backref=db.backref('documents', lazy=True, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<Document {self.id}: {self.filename}>'
