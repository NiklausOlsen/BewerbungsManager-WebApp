# BewerbungsManager Web-App

Eine moderne Web-Anwendung zur Verwaltung von Bewerbungen und automatischen Generierung von Anschreiben.

![Dashboard](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

### Modul 1: Bewerbungs-Übersicht (CRUD)
- **Tabellenansicht** mit allen Bewerbungen
- **Filter** nach Status, Feedback, Antwort erhalten, Suche
- **Vollständiges CRUD**: Erstellen, Bearbeiten, Löschen
- **Umfangreiche Felder**:
  - Unternehmen, Position, Ansprechpartner
  - Status (Entwurf, Versendet, Vorstellungsgespräch, Angebot, Abgelehnt, Zurückgezogen)
  - Feedback (Unbekannt, Positiv, Negativ)
  - Gehaltsvorstellung (Betrag, Währung, Zeitraum)
  - Standort, Remote-Option
  - Quelle (LinkedIn, StepStone, etc.)
  - Notizen (max. 200 Zeichen)
- **CSV-Export** aller Bewerbungen

### Modul 2: Textgenerator
- **Platzhalter-basierte Templates** mit Jinja2
- **Verfügbare Platzhalter**:
  - `{{company}}` - Unternehmen
  - `{{company_address}}` - Unternehmensadresse
  - `{{job_title}}` - Stellenbezeichnung
  - `{{subject}}` - Betreff (automatisch generiert)
  - `{{date}}` - Datum
  - `{{contact_person}}` - Ansprechpartner
  - `{{your_name}}`, `{{your_address}}`, `{{your_email}}`, `{{your_phone}}` - Ihre Daten
- **Automatische Vorbefüllung** aus Bewerbungsdaten
- **Copy-to-Clipboard** Funktion
- **Anschreiben speichern** pro Bewerbung

### Modul 3: Einstellungen
- **Persönliche Kontaktdaten** speichern
- **Standard-Vorlage** für den Textgenerator

## Installation

### Voraussetzungen
- Python 3.9+
- pip

### Setup

1. **Repository klonen**
```bash
cd BewerbungsManager-WebApp
```

2. **Virtuelle Umgebung erstellen**
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows
```

3. **Dependencies installieren**
```bash
pip install -r requirements.txt
```

4. **Anwendung starten**
```bash
python app.py
```

5. **Browser öffnen**
```
http://127.0.0.1:5000
```

## Projektstruktur

```
BewerbungsManager-WebApp/
├── app.py                 # Hauptanwendung mit Routes
├── config.py              # Konfiguration
├── models.py              # SQLAlchemy Datenmodelle
├── forms.py               # WTForms Formulare
├── requirements.txt       # Python Dependencies
├── services/
│   └── textgen.py         # Textgenerator Service
├── templates/
│   ├── base.html          # Basis-Template
│   ├── index.html         # Dashboard
│   ├── generator.html     # Textgenerator
│   ├── settings.html      # Einstellungen
│   └── applications/
│       ├── list.html      # Bewerbungsliste
│       └── form.html      # Bewerbungsformular
└── instance/
    └── bewerbungen.db     # SQLite Datenbank (wird automatisch erstellt)
```

## API-Endpunkte

### Bewerbungen
- `GET /applications` - Liste aller Bewerbungen
- `GET /applications/new` - Neue Bewerbung erstellen
- `GET /applications/<id>/edit` - Bewerbung bearbeiten
- `POST /applications/<id>/delete` - Bewerbung löschen

### Textgenerator
- `GET /generator` - Textgenerator-Seite
- `POST /api/generate` - Text generieren (JSON API)
- `POST /api/letters` - Anschreiben speichern (JSON API)

### Export
- `GET /export/csv` - CSV-Export aller Bewerbungen

## Technologie-Stack

- **Backend**: Flask 3.0
- **Datenbank**: SQLite mit SQLAlchemy ORM
- **Frontend**: HTML5, CSS3 (Custom Dark Theme)
- **Templating**: Jinja2
- **Forms**: Flask-WTF / WTForms
- **Icons**: Bootstrap Icons

## Erweiterungsmöglichkeiten

- [ ] Timeline / Aktionen pro Bewerbung
- [ ] Versionsverwaltung der Anschreiben
- [ ] Dokumentenablage (PDF/DOCX Upload)
- [ ] Follow-up Erinnerungen
- [ ] Tags & Volltextsuche
- [ ] Statistik-Dashboard
- [ ] DOCX/PDF Export der generierten Texte
- [ ] Import von CSV-Dateien

## Lizenz

MIT License
