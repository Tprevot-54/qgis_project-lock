# verrouillage_projet - Extension pour QGIS
# begin in november 2026
# Copyright (C) 2026 by Theo PREVOT
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


# -*- coding: utf-8 -*-

def classFactory(iface):
    # Charger la classe principale depuis le fichier principal de l'extension
    from .verrouillage_plugin import VerrouillagePlugin
    return VerrouillagePlugin(iface)
