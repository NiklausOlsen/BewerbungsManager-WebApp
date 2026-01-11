from flask_wtf import FlaskForm
from wtforms import (
    StringField, TextAreaField, DateField, BooleanField, 
    DecimalField, SelectField, URLField, SubmitField
)
from wtforms.validators import DataRequired, Length, Optional, URL, ValidationError


class ApplicationForm(FlaskForm):
    """Formular für Bewerbungen"""
    
    # Pflichtfelder
    company_name = StringField('Unternehmen', validators=[
        DataRequired(message='Unternehmensname ist erforderlich'),
        Length(max=200)
    ])
    job_title = StringField('Stellenbezeichnung', validators=[
        DataRequired(message='Stellenbezeichnung ist erforderlich'),
        Length(max=200)
    ])
    
    # Datum
    sent_date = DateField('Versanddatum', validators=[Optional()], format='%Y-%m-%d')
    
    # Status & Feedback
    status = SelectField('Status', choices=[
        ('draft', 'Entwurf'),
        ('sent', 'Versendet'),
        ('interview', 'Vorstellungsgespräch'),
        ('offer', 'Angebot'),
        ('rejected', 'Abgelehnt'),
        ('withdrawn', 'Zurückgezogen')
    ], default='draft')
    
    feedback = SelectField('Feedback', choices=[
        ('unknown', 'Unbekannt'),
        ('positive', 'Positiv'),
        ('negative', 'Negativ')
    ], default='unknown')
    
    response_received = BooleanField('Antwort erhalten')
    
    # Gehalt
    salary_expectation_given = BooleanField('Gehaltsvorstellung abgegeben')
    salary_amount = DecimalField('Gehaltsbetrag', validators=[Optional()], places=2)
    salary_currency = SelectField('Währung', choices=[
        ('EUR', 'EUR'),
        ('CHF', 'CHF'),
        ('USD', 'USD'),
        ('GBP', 'GBP')
    ], default='EUR')
    salary_period = SelectField('Zeitraum', choices=[
        ('year', 'Pro Jahr'),
        ('month', 'Pro Monat')
    ], default='year')
    
    # Kontakt & Unternehmen
    contact_person = StringField('Ansprechpartner', validators=[Optional(), Length(max=200)])
    company_address = TextAreaField('Unternehmensadresse', validators=[Optional()])
    website = URLField('Website', validators=[Optional(), URL(message='Bitte gültige URL eingeben')])
    job_url = URLField('Stellen-URL', validators=[Optional(), URL(message='Bitte gültige URL eingeben')])
    
    # Standort
    location = StringField('Standort', validators=[Optional(), Length(max=200)])
    remote_possible = BooleanField('Remote möglich')
    
    # Quelle
    source = SelectField('Quelle', choices=[
        ('', '-- Bitte wählen --'),
        ('linkedin', 'LinkedIn'),
        ('stepstone', 'StepStone'),
        ('indeed', 'Indeed'),
        ('xing', 'XING'),
        ('website', 'Unternehmenswebsite'),
        ('empfehlung', 'Empfehlung'),
        ('messe', 'Jobmesse'),
        ('andere', 'Andere')
    ], default='')
    
    # Notizen
    notes = TextAreaField('Notizen', validators=[
        Optional(),
        Length(max=200, message='Notizen dürfen maximal 200 Zeichen haben')
    ])
    
    submit = SubmitField('Speichern')

    def validate_salary_amount(self, field):
        """Validiert, dass Gehalt nur angegeben wird wenn salary_expectation_given True ist"""
        if field.data and not self.salary_expectation_given.data:
            raise ValidationError('Gehaltsbetrag kann nur angegeben werden, wenn "Gehaltsvorstellung abgegeben" aktiviert ist')


class TextGeneratorForm(FlaskForm):
    """Formular für den Textgenerator"""
    
    company = StringField('Unternehmen', validators=[Optional(), Length(max=200)])
    company_address = TextAreaField('Adresse', validators=[Optional()])
    job_title = StringField('Stellenbezeichnung', validators=[Optional(), Length(max=200)])
    contact_person = StringField('Ansprechpartner', validators=[Optional(), Length(max=200)])
    date = DateField('Datum', validators=[Optional()], format='%Y-%m-%d')
    subject = StringField('Betreff (optional)', validators=[Optional(), Length(max=300)])
    
    # Eigene Daten
    your_name = StringField('Ihr Name', validators=[Optional(), Length(max=200)])
    your_address = TextAreaField('Ihre Adresse', validators=[Optional()])
    your_email = StringField('Ihre E-Mail', validators=[Optional(), Length(max=200)])
    your_phone = StringField('Ihre Telefonnummer', validators=[Optional(), Length(max=50)])
    
    # Template
    template = TextAreaField('Textvorlage', validators=[
        DataRequired(message='Textvorlage ist erforderlich')
    ])
    
    submit = SubmitField('Generieren')


class UserSettingsForm(FlaskForm):
    """Formular für Benutzereinstellungen"""
    
    your_name = StringField('Ihr Name', validators=[Optional(), Length(max=200)])
    your_address = TextAreaField('Ihre Adresse', validators=[Optional()])
    your_email = StringField('Ihre E-Mail', validators=[Optional(), Length(max=200)])
    your_phone = StringField('Ihre Telefonnummer', validators=[Optional(), Length(max=50)])
    
    submit = SubmitField('Speichern')


class TemplateForm(FlaskForm):
    """Formular für Bewerbungsvorlagen"""
    
    name = StringField('Vorlagenname', validators=[
        DataRequired(message='Name ist erforderlich'),
        Length(max=200)
    ])
    description = StringField('Beschreibung', validators=[Optional(), Length(max=500)])
    content = TextAreaField('Vorlagentext', validators=[
        DataRequired(message='Vorlagentext ist erforderlich')
    ])
    is_default = BooleanField('Als Standard-Vorlage verwenden')
    
    submit = SubmitField('Speichern')
