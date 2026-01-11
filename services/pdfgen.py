"""
PDF Generator für DIN 5008 konforme Geschäftsbriefe
"""
import io
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.pdfgen import canvas
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.lib.enums import TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class DINBriefGenerator:
    """
    Generiert DIN 5008 konforme Geschäftsbriefe als PDF
    
    DIN 5008 Maße (Form B):
    - Linker Rand: 25 mm
    - Rechter Rand: 20 mm (mindestens)
    - Anschriftfeld: beginnt bei 50,8 mm von oben, 45 mm hoch
    - Bezugszeichenzeile: 97,4 mm von oben
    - Betreff: 103,4 mm von oben
    - Textbeginn: ca. 2 Zeilen unter Betreff
    """
    
    # DIN 5008 Form B Maße
    LEFT_MARGIN = 25 * mm
    RIGHT_MARGIN = 20 * mm
    TOP_MARGIN = 27 * mm
    
    # Absenderzeile (klein, über dem Anschriftfeld)
    SENDER_LINE_Y = 297 * mm - 45 * mm  # ca. 252 mm von unten
    
    # Anschriftfeld
    ADDRESS_FIELD_TOP = 297 * mm - 50.8 * mm  # von unten gemessen
    ADDRESS_FIELD_HEIGHT = 45 * mm
    
    # Datum/Ort (rechtsbündig)
    DATE_Y = 297 * mm - 50.8 * mm
    
    # Betreff
    SUBJECT_Y = 297 * mm - 103.4 * mm
    
    # Textbeginn
    TEXT_START_Y = 297 * mm - 115 * mm
    
    # Seitenbreite für Text
    PAGE_WIDTH = 210 * mm
    TEXT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN
    
    # Schrifteinstellungen
    FONT_SIZE = 11
    FONT_SIZE_SMALL = 7
    FONT_SIZE_SENDER = 10
    LINE_HEIGHT = 14  # Zeilenabstand
    PARAGRAPH_SPACING = 11  # Absatzabstand
    BULLET_INDENT = 8 * mm  # Einrückung für Aufzählungspunkte
    BULLET_SPACING = 8  # Zusätzlicher Abstand zwischen Aufzählungspunkten
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._register_fonts()
        
    def _register_fonts(self):
        """Registriert Avenir Next oder Fallback-Schriften"""
        self.font_name = 'Helvetica'
        self.font_name_bold = 'Helvetica-Bold'
        
        # Avenir Next TTC auf macOS
        # Subfont-Indizes:
        # 0 = Bold, 1 = Bold Italic, 2 = Demi Bold, 3 = Demi Bold Italic
        # 4 = Italic, 5 = Medium, 6 = Medium Italic, 7 = Regular
        # 8 = Heavy, 9 = Heavy Italic, 10 = Ultra Light, 11 = Ultra Light Italic
        
        avenir_path = '/System/Library/Fonts/Avenir Next.ttc'
        
        try:
            if os.path.exists(avenir_path):
                # Avenir Next Regular (Index 7)
                pdfmetrics.registerFont(TTFont('AvenirNext', avenir_path, subfontIndex=7))
                # Avenir Next Bold (Index 0)
                pdfmetrics.registerFont(TTFont('AvenirNext-Bold', avenir_path, subfontIndex=0))
                
                self.font_name = 'AvenirNext'
                self.font_name_bold = 'AvenirNext-Bold'
                print("Avenir Next erfolgreich geladen")
                return
                        
        except Exception as e:
            print(f"Avenir Next nicht verfügbar, verwende Helvetica: {e}")
        
        # Fallback zu Helvetica
        self.font_name = 'Helvetica'
        self.font_name_bold = 'Helvetica-Bold'
    
    def generate_pdf(self, data):
        """
        Generiert ein PDF aus den übergebenen Daten
        
        data = {
            'your_name': str,
            'your_address': str,
            'your_email': str,
            'your_phone': str,
            'company': str,
            'company_address': str,
            'contact_person': str,
            'date': str,
            'subject': str,
            'body_text': str  # Der generierte Brieftext
        }
        """
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        
        # Absender-Block (oben rechts)
        self._draw_sender_block(c, data)
        
        # Absenderzeile (klein, über dem Anschriftfeld)
        self._draw_sender_line(c, data)
        
        # Empfänger-Anschrift
        self._draw_recipient_address(c, data)
        
        # Datum (rechtsbündig)
        self._draw_date(c, data)
        
        # Betreff
        self._draw_subject(c, data)
        
        # Brieftext
        self._draw_body_text(c, data)
        
        c.save()
        buffer.seek(0)
        return buffer
    
    def _draw_sender_block(self, c, data):
        """Zeichnet den Absender-Block oben rechts"""
        y = 297 * mm - self.TOP_MARGIN
        x = self.PAGE_WIDTH - self.RIGHT_MARGIN
        
        c.setFont(self.font_name, self.FONT_SIZE_SENDER)
        
        # Name
        if data.get('your_name'):
            c.drawRightString(x, y, data['your_name'])
            y -= 12
        
        # Adresse (mehrzeilig)
        if data.get('your_address'):
            for line in data['your_address'].split('\n'):
                c.drawRightString(x, y, line.strip())
                y -= 12
        
        # Leerzeile
        y -= 6
        
        # Kontaktdaten
        if data.get('your_phone'):
            c.drawRightString(x, y, f"Tel.: {data['your_phone']}")
            y -= 12
        
        if data.get('your_email'):
            c.drawRightString(x, y, data['your_email'])
    
    def _draw_sender_line(self, c, data):
        """Zeichnet die kleine Absenderzeile über dem Anschriftfeld"""
        sender_parts = []
        if data.get('your_name'):
            sender_parts.append(data['your_name'])
        if data.get('your_address'):
            # Nur erste Zeile der Adresse + PLZ/Ort
            addr_lines = data['your_address'].split('\n')
            sender_parts.extend([line.strip() for line in addr_lines if line.strip()])
        
        if sender_parts:
            sender_line = ' · '.join(sender_parts)
            c.setFont(self.font_name, self.FONT_SIZE_SMALL)
            c.drawString(self.LEFT_MARGIN, self.SENDER_LINE_Y, sender_line)
            
            # Unterstreichung
            c.setLineWidth(0.3)
            c.line(self.LEFT_MARGIN, self.SENDER_LINE_Y - 2, 
                   self.LEFT_MARGIN + 85 * mm, self.SENDER_LINE_Y - 2)
    
    def _draw_recipient_address(self, c, data):
        """Zeichnet die Empfängeradresse im Anschriftfeld"""
        y = self.ADDRESS_FIELD_TOP - 15  # Etwas Abstand von oben
        x = self.LEFT_MARGIN
        
        c.setFont(self.font_name, self.FONT_SIZE)
        
        # Firma
        if data.get('company'):
            c.drawString(x, y, data['company'])
            y -= self.LINE_HEIGHT
        
        # Ansprechpartner (falls vorhanden)
        if data.get('contact_person'):
            c.drawString(x, y, data['contact_person'])
            y -= self.LINE_HEIGHT
        
        # Adresse (mehrzeilig)
        if data.get('company_address'):
            for line in data['company_address'].split('\n'):
                if line.strip():
                    c.drawString(x, y, line.strip())
                    y -= self.LINE_HEIGHT
    
    def _draw_date(self, c, data):
        """Zeichnet Ort und Datum rechtsbündig"""
        date_str = data.get('date', datetime.now().strftime('%d.%m.%Y'))
        
        # Formatiere Datum falls nötig
        if date_str and '-' in date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                date_str = date_obj.strftime('%d.%m.%Y')
            except ValueError:
                pass
        
        # Ort aus Adresse extrahieren (letzte Zeile)
        location = "Flensburg"  # Default
        if data.get('your_address'):
            addr_lines = [l.strip() for l in data['your_address'].split('\n') if l.strip()]
            if addr_lines:
                last_line = addr_lines[-1]
                # PLZ und Ort trennen
                parts = last_line.split(' ', 1)
                if len(parts) > 1:
                    location = parts[1]
        
        date_location = f"{location}, den {date_str}"
        
        c.setFont(self.font_name, self.FONT_SIZE)
        c.drawRightString(self.PAGE_WIDTH - self.RIGHT_MARGIN, self.DATE_Y, date_location)
    
    def _draw_subject(self, c, data):
        """Zeichnet den Betreff"""
        subject = data.get('subject', '')
        if not subject and data.get('job_title'):
            subject = f"Bewerbung als {data['job_title']}"
        
        if subject:
            c.setFont(self.font_name_bold, self.FONT_SIZE)
            c.drawString(self.LEFT_MARGIN, self.SUBJECT_Y, subject)
    
    def _draw_body_text(self, c, data):
        """Zeichnet den Brieftext mit verbesserter Formatierung"""
        body_text = data.get('body_text', '')
        if not body_text:
            return
        
        # Entferne die Kopfzeilen aus dem generierten Text
        lines = body_text.split('\n')
        
        # Finde den Beginn des eigentlichen Brieftextes (nach der Anrede)
        text_start_idx = 0
        for i, line in enumerate(lines):
            line_lower = line.lower().strip()
            if line_lower.startswith('sehr geehrte') or line_lower.startswith('liebes') or line_lower.startswith('liebe '):
                text_start_idx = i
                break
        
        # Nur den Text ab der Anrede verwenden
        relevant_lines = lines[text_start_idx:]
        
        y = self.TEXT_START_Y
        x = self.LEFT_MARGIN
        
        c.setFont(self.font_name, self.FONT_SIZE)
        
        # Verarbeite den Text zeilenweise
        in_bullet_list = False
        previous_was_bullet = False
        
        i = 0
        while i < len(relevant_lines):
            line = relevant_lines[i].strip()
            
            # Leere Zeile = Absatzende
            if not line:
                if in_bullet_list:
                    # Ende der Aufzählung - extra Abstand
                    y -= self.PARAGRAPH_SPACING
                    in_bullet_list = False
                else:
                    y -= self.PARAGRAPH_SPACING
                previous_was_bullet = False
                i += 1
                continue
            
            # Prüfe ob es ein Aufzählungspunkt ist
            is_bullet = line.startswith('•') or line.startswith('-') or line.startswith('–') or line.startswith('*')
            
            if is_bullet:
                # Aufzählungspunkt gefunden
                if not in_bullet_list and not previous_was_bullet:
                    # Beginn einer neuen Liste - kleiner Abstand davor
                    y -= 6
                
                in_bullet_list = True
                
                # Entferne das Aufzählungszeichen und führende Leerzeichen
                bullet_text = line.lstrip('•-–* ').strip()
                
                # Zeichne den Aufzählungspunkt
                c.setFont(self.font_name, self.FONT_SIZE)
                bullet_x = x + 5 * mm
                c.drawString(bullet_x, y, '•')
                
                # Zeichne den Text mit Einrückung
                text_x = x + self.BULLET_INDENT
                text_width = self.TEXT_WIDTH - self.BULLET_INDENT
                
                # Finde den fett formatierten Teil (falls vorhanden)
                if '(' in bullet_text:
                    # Text vor der Klammer ist fett, Text in Klammern normal
                    parts = bullet_text.split('(', 1)
                    bold_part = parts[0].strip()
                    rest_part = '(' + parts[1] if len(parts) > 1 else ''
                    
                    # Zeichne fetten Teil (Titel des Bullet Points)
                    c.setFont(self.font_name_bold, self.FONT_SIZE)
                    c.drawString(text_x, y, bold_part)
                    y -= self.LINE_HEIGHT
                    
                    # Zeichne Beschreibung in Klammern auf neuer Zeile (eingerückt)
                    if rest_part:
                        c.setFont(self.font_name, self.FONT_SIZE)
                        wrapped_lines = self._wrap_text(rest_part, text_width, c)
                        for wline in wrapped_lines:
                            c.drawString(text_x, y, wline)
                            y -= self.LINE_HEIGHT
                    
                    # Abstand nach dem Bullet Point
                    y -= self.BULLET_SPACING
                else:
                    # Kein fetter Teil, normaler Text
                    wrapped_lines = self._wrap_text(bullet_text, text_width, c)
                    for j, wline in enumerate(wrapped_lines):
                        c.setFont(self.font_name, self.FONT_SIZE)
                        c.drawString(text_x, y, wline)
                        y -= self.LINE_HEIGHT
                    y -= self.BULLET_SPACING
                
                previous_was_bullet = True
                
            else:
                # Normaler Absatz
                in_bullet_list = False
                previous_was_bullet = False
                
                c.setFont(self.font_name, self.FONT_SIZE)
                wrapped_lines = self._wrap_text(line, self.TEXT_WIDTH, c)
                
                for wline in wrapped_lines:
                    c.drawString(x, y, wline)
                    y -= self.LINE_HEIGHT
            
            # Seitenumbruch wenn nötig
            if y < 30 * mm:
                c.showPage()
                c.setFont(self.font_name, self.FONT_SIZE)
                y = 297 * mm - 25 * mm
            
            i += 1
        
        return y
    
    def _wrap_text(self, text, max_width, c):
        """Bricht Text um wenn er zu lang ist"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if c.stringWidth(test_line, self.font_name, self.FONT_SIZE) <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines if lines else ['']
    
    def _count_lines(self, text, max_width, c):
        """Zählt wie viele Zeilen der Text benötigt"""
        return len(self._wrap_text(text, max_width, c))


def generate_filename(company, job_title, date=None):
    """Generiert einen sinnvollen Dateinamen für den Brief"""
    if date is None:
        date = datetime.now()
    elif isinstance(date, str):
        try:
            if '-' in date:
                date = datetime.strptime(date, '%Y-%m-%d')
            else:
                date = datetime.strptime(date, '%d.%m.%Y')
        except ValueError:
            date = datetime.now()
    
    # Bereinige Firmennamen und Jobtitel für Dateinamen
    def clean_name(name):
        if not name:
            return ""
        # Entferne Sonderzeichen
        name = name.replace('/', '-').replace('\\', '-')
        name = name.replace(':', '').replace('*', '').replace('?', '')
        name = name.replace('"', '').replace('<', '').replace('>', '')
        name = name.replace('|', '').replace('&', 'und')
        # Ersetze Leerzeichen durch Unterstriche
        name = '_'.join(name.split())
        return name
    
    date_str = date.strftime('%Y-%m-%d')
    company_clean = clean_name(company) or 'Unternehmen'
    job_clean = clean_name(job_title) or 'Bewerbung'
    
    return f"Bewerbung_{date_str}_{company_clean}_{job_clean}.pdf"


# Singleton-Instanz
pdf_generator = DINBriefGenerator()
