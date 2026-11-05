# -*- coding: utf-8 -*-

def classFactory(iface):
    # Charger la classe principale depuis le fichier principal de l'extension
    from .verrouillage_plugin import VerrouillagePlugin
    return VerrouillagePlugin(iface)
