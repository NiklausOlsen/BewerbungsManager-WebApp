"""
Textgenerator Service für Bewerbungsanschreiben
Verwendet Jinja2 für sicheres Template-Rendering
"""
from datetime import date
from jinja2 import Environment, BaseLoader, UndefinedError
from jinja2.sandbox import SandboxedEnvironment


class TextGenerator:
    """Generator für Bewerbungsanschreiben aus Templates"""

    # Standard-Platzhalter
    PLACEHOLDERS = {
        'company': 'Unternehmen',
        'company_address': 'Unternehmensadresse',
        'job_title': 'Stellenbezeichnung',
        'subject': 'Betreff',
        'date': 'Datum',
        'contact_person': 'Ansprechpartner',
        'your_name': 'Ihr Name',
        'your_address': 'Ihre Adresse',
        'your_email': 'Ihre E-Mail',
        'your_phone': 'Ihre Telefonnummer'
    }

    DEFAULT_TEMPLATE = """{{your_name}}
{{your_address}}
{{your_email}}
{{your_phone}}

{{company}}
{{company_address}}

{{date}}

Betreff: {{subject}}

{% if contact_person %}Sehr geehrte/r {{contact_person}},{% else %}Liebes {{company}}-Recruiting-Team,{% endif %}

mit großem Interesse habe ich Ihre Stellenausschreibung als {{job_title}} gelesen und bewerbe mich hiermit auf diese Position.

[Ihr Bewerbungstext hier]

Mit freundlichen Grüßen

{{your_name}}
"""

    def __init__(self):
        # Sandboxed Environment für sichere Template-Verarbeitung
        # autoescape=False da wir Plaintext generieren, nicht HTML
        self.env = SandboxedEnvironment(
            loader=BaseLoader(),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True
        )

    def generate_subject(self, job_title: str = None) -> str:
        """Generiert den Standard-Betreff"""
        if job_title and job_title.strip():
            return f"Bewerbung als {job_title}"
        return "Bewerbung"

    def render(self, template_string: str, context: dict) -> str:
        """
        Rendert ein Template mit dem gegebenen Kontext
        
        Args:
            template_string: Das Template mit Platzhaltern
            context: Dictionary mit Werten für die Platzhalter
            
        Returns:
            Der gerenderte Text
        """
        # Standard-Betreff generieren falls nicht vorhanden
        if 'subject' not in context or not context['subject']:
            context['subject'] = self.generate_subject(context.get('job_title'))
        
        # Standard-Datum falls nicht vorhanden
        if 'date' not in context or not context['date']:
            context['date'] = date.today().strftime('%d.%m.%Y')
        
        # Leere Werte durch leere Strings ersetzen
        for key in self.PLACEHOLDERS.keys():
            if key not in context or context[key] is None:
                context[key] = ''
        
        try:
            template = self.env.from_string(template_string)
            return template.render(**context)
        except UndefinedError as e:
            return f"Fehler: Unbekannter Platzhalter - {str(e)}"
        except Exception as e:
            return f"Fehler beim Rendern: {str(e)}"

    def get_placeholder_list(self) -> list:
        """Gibt eine Liste aller verfügbaren Platzhalter zurück"""
        return [f"{{{{{key}}}}}" for key in self.PLACEHOLDERS.keys()]

    def get_placeholder_descriptions(self) -> dict:
        """Gibt Platzhalter mit Beschreibungen zurück"""
        return self.PLACEHOLDERS.copy()


# Singleton-Instanz
text_generator = TextGenerator()
