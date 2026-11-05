import os
import getpass
# --- Ajout de QgsMessageLog pour une gestion propre des erreurs ---
from qgis.core import QgsProject, Qgis, QgsMessageLog
from qgis.PyQt.QtWidgets import QMessageBox

# ... (Le reste du code initial reste inchangé jusqu'aux fonctions ci-dessous) ...

    def _createLock(self, user):
        if self.lock_file:
            try:
                with open(self.lock_file, 'w', encoding='utf-8') as f:
                    f.write(user)
            except Exception as e:
                # Correction Bandit : Journalisation de l'erreur au lieu d'un pass silencieux
                QgsMessageLog.logMessage(
                    f"Impossible de créer le fichier de verrou : {str(e)}",
                    "VerrouillageProjet",
                    Qgis.MessageLevel.Warning
                )

    def onProjectClose(self):
        """Nettoie les verrous à la fermeture du projet"""
        if self.lock_file and os.path.exists(self.lock_file):
            current_user = getpass.getuser()
            try:
                with open(self.lock_file, 'r', encoding='utf-8') as f:
                    locking_user = f.read().strip()
                # On ne supprime le fichier que s'il nous appartient
                if locking_user == current_user and not self.is_read_only:
                    os.remove(self.lock_file)
            except Exception as e:
                # Correction Bandit : Journalisation de l'erreur
                QgsMessageLog.logMessage(
                    f"Erreur lors de la lecture/suppression du verrou à la fermeture : {str(e)}",
                    "VerrouillageProjet",
                    Qgis.MessageLevel.Warning
                )
        
        self.lock_file = None
        self.is_read_only = False
        self.toggleSaveActions(True)  # Réactive tout pour le projet suivant
