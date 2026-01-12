#!/bin/bash
# Richtet automatische tägliche Backups ein (via Cron)

SCRIPT_DIR="/var/www/bewerbungsmanager/scripts"
BACKUP_SCRIPT="$SCRIPT_DIR/backup.sh"

echo "Richte automatische Backups ein..."

# Backup-Script ausführbar machen
chmod +x "$BACKUP_SCRIPT"

# Cron-Job hinzufügen (täglich um 3:00 Uhr)
CRON_JOB="0 3 * * * $BACKUP_SCRIPT >> /var/log/bewerbungsmanager_backup.log 2>&1"

# Prüfen ob Cron-Job bereits existiert
if crontab -l 2>/dev/null | grep -q "$BACKUP_SCRIPT"; then
    echo "Cron-Job existiert bereits."
else
    # Cron-Job hinzufügen
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "Cron-Job hinzugefügt: Tägliches Backup um 3:00 Uhr"
fi

# Backup-Verzeichnis erstellen
mkdir -p /var/backups/bewerbungsmanager

# Erstes Backup ausführen
echo ""
echo "Führe erstes Backup aus..."
$BACKUP_SCRIPT

echo ""
echo "Setup abgeschlossen!"
echo "Backups werden täglich um 3:00 Uhr erstellt."
echo "Log-Datei: /var/log/bewerbungsmanager_backup.log"
