#!/bin/bash
# Automatisches Backup-Script für BewerbungsManager
# Führt tägliche Backups der Datenbank und Uploads durch

# Konfiguration
APP_DIR="/var/www/bewerbungsmanager"
BACKUP_DIR="/var/backups/bewerbungsmanager"
DATE=$(date +%Y%m%d_%H%M%S)
KEEP_DAYS=30  # Backups älter als 30 Tage löschen

# Farben für Output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "=========================================="
echo "BewerbungsManager Backup - $DATE"
echo "=========================================="

# Backup-Verzeichnis erstellen falls nicht vorhanden
mkdir -p "$BACKUP_DIR"

# 1. Datenbank-Backup
echo -n "Erstelle Datenbank-Backup... "
if [ -f "$APP_DIR/instance/bewerbungen.db" ]; then
    cp "$APP_DIR/instance/bewerbungen.db" "$BACKUP_DIR/db_backup_$DATE.db"
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FEHLER: Datenbank nicht gefunden${NC}"
fi

# 2. Uploads-Backup (falls vorhanden)
echo -n "Erstelle Uploads-Backup... "
if [ -d "$APP_DIR/uploads" ] && [ "$(ls -A $APP_DIR/uploads 2>/dev/null)" ]; then
    tar -czf "$BACKUP_DIR/uploads_backup_$DATE.tar.gz" -C "$APP_DIR" uploads
    echo -e "${GREEN}OK${NC}"
else
    echo "Keine Uploads vorhanden, übersprungen."
fi

# 3. JSON-Export über die App (optional, wenn curl verfügbar)
echo -n "Erstelle JSON-Export... "
if command -v curl &> /dev/null; then
    # Hinweis: Dies erfordert einen API-Endpunkt ohne Auth oder einen Service-Account
    # Für jetzt kopieren wir nur die DB
    echo "Übersprungen (manuell über Admin-Panel möglich)"
else
    echo "curl nicht verfügbar, übersprungen."
fi

# 4. Alte Backups löschen
echo -n "Lösche Backups älter als $KEEP_DAYS Tage... "
find "$BACKUP_DIR" -name "*.db" -mtime +$KEEP_DAYS -delete 2>/dev/null
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$KEEP_DAYS -delete 2>/dev/null
echo -e "${GREEN}OK${NC}"

# 5. Backup-Statistik
echo ""
echo "Backup-Statistik:"
echo "  Datenbank-Backups: $(ls -1 $BACKUP_DIR/*.db 2>/dev/null | wc -l)"
echo "  Upload-Backups: $(ls -1 $BACKUP_DIR/*.tar.gz 2>/dev/null | wc -l)"
echo "  Speicherplatz: $(du -sh $BACKUP_DIR 2>/dev/null | cut -f1)"
echo ""
echo "Backup abgeschlossen: $BACKUP_DIR"
echo "=========================================="
