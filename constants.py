# -*- coding: utf-8 -*-

##    This file is part of Gertrude.
##
##    Gertrude is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 3 of the License, or
##    (at your option) any later version.
##
##    Gertrude is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License
##    along with Gertrude; if not, see <http://www.gnu.org/licenses/>.

days = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi"]
months = ["Janvier", u'Février', "Mars", "Avril", "Mai", "Juin", "Juillet", u'Août', "Septembre", "Octobre", "Novembre", u'Décembre']
months_abbrev = ["Janv", u'Fév', "Mars", "Avril", "Mai", "Juin", "Juil", u'Août', "Sept", "Oct", "Nov", u'Déc']
trimestres = ["1er", u'2ème', u'3ème', u'4ème']

# Profils des utilisateurs
PROFIL_INSCRIPTIONS = 1
PROFIL_TRESORIER = 2
PROFIL_BUREAU = 4
PROFIL_SAISIE_PRESENCES = 8
PROFIL_ADMIN = 16
PROFIL_ALL = PROFIL_ADMIN + PROFIL_INSCRIPTIONS + PROFIL_TRESORIER + PROFIL_BUREAU + PROFIL_SAISIE_PRESENCES

# Modes des activités
MODE_LIBERE_PLACE = 1

# Granularité du planning dans la base
BASE_GRANULARITY = 4 # au quart d'heure

# Modes d'accueil
MODE_CRECHE = 0
MODE_HALTE_GARDERIE = 1
MODE_4_5 = 2
MODE_3_5 = 4

# Modes de déduction pour maladie
DEDUCTION_TOTALE = 1
DEDUCTION_AVEC_CARENCE = 2

# Valeurs de présence
ABSENT = 0
PRESENT = 1
VACANCES = -1
MALADE = -2
NONINSCRIT = -3
PREVISIONNEL = 1<<30
SUPPLEMENT = 512

#IDs de boutons
ID_SYNCHRO = 10001
ID_UNDO = 10002

