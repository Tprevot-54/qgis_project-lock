# verrouillage_projet - Extension pour QGIS
# begin in november 2026
# Copyright (C) 2026 by Theo PREVOT
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# -*- coding: utf-8 -*-
import os
import getpass
from qgis.core import QgsProject, Qgis, QgsMessageLog
from qgis.PyQt.QtWidgets import QMessageBox


class VerrouillagePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.lock_file = None
        self.is_read_only = False  # Suit l'état de verrouillage du projet actuel

    def initGui(self):
        # Connexion aux signaux clés du cycle de vie d'un projet QGIS
        QgsProject.instance().readProject.connect(self.onProjectOpen)
        QgsProject.instance().writeProject.connect(self.onProjectSavePrevent)
        QgsProject.instance().projectSaved.connect(self.onProjectSaveSuccess)
        QgsProject.instance().cleared.connect(self.onProjectClose)
        # Correction faille 1 : Écoute quand le statut de modification change
        QgsProject.instance().isDirtyChanged.connect(self.onDirtyChanged)

    def tr(self, message):
        """Permet la traduction des chaînes de caractères via le système natif de QGIS"""
        from qgis.PyQt.QtCore import QCoreApplication
        return QCoreApplication.translate('VerrouillagePlugin', message)

    def unload(self):
        # Déconnexion propre des signaux
        try:
            QgsProject.instance().readProject.disconnect(self.onProjectOpen)
        except (TypeError, RuntimeError):  # nosec
            pass

        try:
            QgsProject.instance().writeProject.disconnect(self.onProjectSavePrevent)
        except (TypeError, RuntimeError):  # nosec
            pass

        try:
            QgsProject.instance().projectSaved.disconnect(self.onProjectSaveSuccess)
        except (TypeError, RuntimeError):  # nosec
            pass

        try:
            QgsProject.instance().cleared.disconnect(self.onProjectClose)
        except (TypeError, RuntimeError):  # nosec
            pass

        try:
            QgsProject.instance().isDirtyChanged.disconnect(self.onDirtyChanged)
        except (TypeError, RuntimeError):  # nosec
            pass
            
        self.toggleSaveActions(True)  # Réactive par sécurité en cas de déchargement de l'extension

    def _getLockFilePath(self):
        project_path = QgsProject.instance().absoluteFilePath()
        if not project_path:
            return None
        return project_path + ".lock"

    def _getLockIdentifier(self, user):
        """Génère un identifiant unique combinant l'utilisateur et le PID local de l'instance"""
        return f"{user}_{os.getpid()}"

    def toggleSaveActions(self, enable):
        """Active ou désactive visuellement les boutons d'enregistrement de QGIS"""
        actions = [
            self.iface.actionSaveProject(),
            self.iface.actionSaveProjectAs()
        ]
        for action in actions:
            if action:
                action.setEnabled(enable)

    def onDirtyChanged(self, is_dirty):
        """Correction faille 1 : Force le projet à rester propre en lecture seule pour éviter le pop-up de fermeture"""
        if self.is_read_only and is_dirty:
            QgsProject.instance().blockSignals(True)
            QgsProject.instance().setDirty(False)
            QgsProject.instance().blockSignals(False)

    def onProjectOpen(self):
        self.lock_file = self._getLockFilePath()
        if not self.lock_file:
            return

        current_user = getpass.getuser()
        current_identifier = self._getLockIdentifier(current_user)
        self.is_read_only = False  # Initialisation par défaut

        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, 'r', encoding='utf-8') as f:
                    lock_content = f.read().strip()
            except Exception:
                lock_content = self.tr("un autre collègue")

            # Extraction du nom d'utilisateur pour l'affichage (sépare l'user du PID s'il existe)
            locking_user = lock_content.split('_')[0] if '_' in lock_content else lock_content

            # Gestion de la restauration après crash OU multi-instance locale
            # Si le contenu est strictement identique (User + PID), c'est une restauration après crash
            if lock_content == current_identifier:
                self._createLock(current_user)
                self.iface.messageBar().pushMessage(
                    self.tr("Session restaurée"), 
                    self.tr("Votre ancienne session suite au crash a été récupérée automatiquement."), 
                    level=Qgis.MessageLevel.Info, 
                    duration=5
                )
                self.toggleSaveActions(True)
                return
            
            # Si le nom d'utilisateur concorde mais pas le PID, c'est une double ouverture locale.
            # On n'écrase pas le verrou, on bascule en lecture seule.

            # --- ACTIVATION DE LA LECTURE SEULE STRICTE ---
            self.is_read_only = True
            self.toggleSaveActions(False)  # Grise les boutons dans l'interface
            QgsProject.instance().setDirty(False)

            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle(self.tr("Fichier verrouillé - Lecture seule active"))
            msg.setText(f"{self.tr('Attention, ce projet QGIS est déjà ouvert par :')} {locking_user}")
            msg.setInformativeText(
                self.tr("Le projet a basculé en LECTURE SEULE stricte.\n\n"
                        "⚠️ Les fonctions d'enregistrement ont été désactivées pour protéger les données.")
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            
            self.iface.messageBar().pushMessage(
                self.tr("Lecture seule"), 
                f"{self.tr('Projet verrouillé par')} {locking_user}. {self.tr('Enregistrement impossible.')}", 
                level=Qgis.MessageLevel.Warning, 
                duration=10
            )
        else:
            # Création normale du verrou si le fichier n'existe pas
            self._createLock(current_user)
            self.toggleSaveActions(True)

    def onProjectSavePrevent(self):
        """Intercepte l'écriture sur le disque. Lève une exception pour forcer le blocage de QGIS."""
        if self.is_read_only:
            self.iface.messageBar().pushMessage(
                self.tr("Action bloquée"), 
                self.tr("Le projet est en lecture seule. Enregistrement annulé."), 
                level=Qgis.MessageLevel.Critical, 
                duration=5
            )
            raise Exception("Projet verrouillé : Écriture interdite par l'extension.")

    def onProjectSaveSuccess(self):
        """Met à jour le fichier de verrou si l'utilisateur fait un 'Enregistrer sous' légitime"""
        if self.is_read_only:
            return
            
        new_lock = self._getLockFilePath()
        if new_lock and new_lock != self.lock_file:
            if self.lock_file and os.path.exists(self.lock_file):
                try:
                    os.remove(self.lock_file)
                except Exception as e:
                    QgsMessageLog.logMessage(
                        f"Impossible de supprimer l'ancien verrou lors du Enregistrer sous : {str(e)}",
                        "VerrouillageProjet",
                        Qgis.MessageLevel.Warning
                    )
            self.lock_file = new_lock
            self._createLock(getpass.getuser())

    def _createLock(self, user):
        if self.lock_file:
            try:
                with open(self.lock_file, 'w', encoding='utf-8') as f:
                    # Correction faille 2 : On écrit l'identifiant combiné (User + PID)
                    f.write(self._getLockIdentifier(user))
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Impossible de créer le fichier de verrou : {str(e)}",
                    "VerrouillageProjet",
                    Qgis.MessageLevel.Warning
                )

    def onProjectClose(self):
        """Nettoie les verrous à la fermeture du projet"""
        if self.lock_file and os.path.exists(self.lock_file):
            current_user = getpass.getuser()
            current_identifier = self._getLockIdentifier(current_user)
            try:
                with open(self.lock_file, 'r', encoding='utf-8') as f:
                    lock_content = f.read().strip()
                # Correction faille 2 : On ne supprime le fichier que si l'identifiant (User + PID) est strictement le nôtre
                if lock_content == current_identifier and not self.is_read_only:
                    os.remove(self.lock_file)
            except Exception as e:
                QgsMessageLog.logMessage(
                    f"Erreur lors de la lecture/suppression du verrou à la fermeture : {str(e)}",
                    "VerrouillageProjet",
                    Qgis.MessageLevel.Warning
                )
        
        self.lock_file = None
        self.is_read_only = False
        self.toggleSaveActions(True)  # Restaure l'interface pour le prochain projet ouvert
