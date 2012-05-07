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

import datetime, binascii
from constants import *
from parameters import *
from functions import *

class SQLObject(object):
    def delete(self):
        print 'suppression %s' % self.__class__.__name__
        sql_connection.execute('DELETE FROM %s WHERE idx=?' % self.table, (self.idx,))
        
class Day(object):
    table = None
    
    def __init__(self):
        self.activites = {}
        self.activites_sans_horaires = {}
        self.last_heures = None
        self.readonly = False
           
    def SetActivity(self, start, end, value):
        self.last_heures = None
        activity_value = value & ~PREVISIONNEL
        if value == activity_value:
            self.Confirm()
        activity = creche.activites[activity_value]
        for a, b, v in self.activites.keys():
            if v < 0:
                self.remove_activity(a, b, v)
            elif value == v:
                if start <= b+1 and end >= a-1:
                    start, end = min(a, start), max(b, end)
                    self.remove_activity(a, b, v)
            elif activity.mode == MODE_LIBERE_PLACE and start < b and end > a:
                self.remove_activity(a, b, v)
                if a < start:
                    self.insert_activity(a, start, v)
                if b > end:
                    self.insert_activity(end, b, v)
            elif creche.activites[v & ~(PREVISIONNEL+CLOTURE)].mode == MODE_LIBERE_PLACE and start < b and end > a:
                self.remove_activity(a, b, v)
                if a < start:
                    self.insert_activity(a, start, v)
                if b > end:
                    self.insert_activity(end, b, v)
        self.insert_activity(start, end, value)
        if activity_value != 0 and activity.mode == MODE_NORMAL:
            self.SetActivity(start, end, value&PREVISIONNEL)
            
    def ClearActivity(self, start, end, value):
        self.last_heures = None
        activity_value = value & ~PREVISIONNEL
        if value == activity_value:
            self.Confirm()
        activity = creche.activites[activity_value]
        for a, b, v in self.activites.keys():
            if value == v:
                if start <= b+1 and end >= a-1:
                    self.remove_activity(a, b, v)
                    if start > a:
                        self.insert_activity(a, start, v)
                    if end < b:
                        self.insert_activity(end, b, v)
            elif activity_value == 0 and (not v&CLOTURE) and creche.activites[v & ~PREVISIONNEL].mode == MODE_NORMAL and start < b and end > a:
                self.remove_activity(a, b, v)
                if a < start:
                    self.insert_activity(a, start, v)
                if b > end:
                    self.insert_activity(end, b, v)

    def insert_activity(self, start, end, value):
        self.add_activity(start, end, value, None)

    def add_activity(self, start, end, value, idx):
        if start is None and end is None:
            self.activites_sans_horaires[value] = idx
        else:
            self.activites[(start, end, value)] = idx
    
    def remove_activities(self, activity):
        for start, end, value in self.activites.keys():
            if activity == value:
                self.remove_activity(start, end, value)
        for key in self.activites_sans_horaires.keys():
            if activity == key:
                self.remove_activity(None, None, key)
            
    def remove_all_activities(self):
        for start, end, value in self.activites.keys():
            if value < 0 or not value & CLOTURE:
                self.remove_activity(start, end, value)
        for key in self.activites_sans_horaires.keys():
            if key < 0 or not key & CLOTURE:
                self.remove_activity(None, None, key)
                
    def Backup(self):
        backup = []
        for start, end, value in self.activites:
            if value < 0 or not value & CLOTURE:
                backup.append((start, end, value))
        for key in self.activites_sans_horaires:
            if key < 0 or not key & CLOTURE:
                backup.append((None, None, key))
        return backup
    
    def Restore(self, backup):
        self.remove_all_activities()
        for start, end, value in backup:
            self.add_activity(start, end, value, None)
        self.Save()
    
    def Confirm(self):
        self.last_heures = None
        for start, end, value in self.activites.keys():
            if value & PREVISIONNEL and not value & CLOTURE:
                self.remove_activity(start, end, value)
                value -= PREVISIONNEL
                self.insert_activity(start, end, value)
        for value in self.activites_sans_horaires.keys():
            if value & PREVISIONNEL and not value & CLOTURE:
                self.remove_activity(None, None, value)
                value -= PREVISIONNEL
                self.insert_activity(None, None, value)
        self.Save()
    
    def Save(self):
        self.last_heures = None
        for start, end, value in self.activites.keys():
            if self.activites[(start, end, value)] == None:
                self.insert_activity(start, end, value)
        for value in self.activites_sans_horaires.keys():
            if self.activites_sans_horaires[value] == None:
                self.insert_activity(None, None, value)
               
    def CloturePrevisionnel(self):
        for start, end, value in self.activites.keys() + self.activites_sans_horaires.keys():
            if value >= 0:
                self.insert_activity(start, end, value|PREVISIONNEL|CLOTURE)
                
    def HasPrevisionnelCloture(self):
        for start, end, value in self.activites.keys() + self.activites_sans_horaires.keys():
            if value >= PREVISIONNEL+CLOTURE:
                return True
        return False
    
    def RestorePrevisionnelCloture(self, previsionnel=True):
        self.last_heures = None
        self.remove_all_activities()
        for start, end, value in self.activites.keys() + self.activites_sans_horaires.keys():
            if previsionnel:               
                self.insert_activity(start, end, value-CLOTURE)
            else:
                self.insert_activity(start, end, value-PREVISIONNEL-CLOTURE)
    
    def set_state(self, state):
        self.last_heures = None
        self.remove_all_activities()
        if creche.debut_pause and creche.fin_pause:
            start, end = int(creche.ouverture*(60 / BASE_GRANULARITY)), int(creche.debut_pause*(60 / BASE_GRANULARITY))
            self.insert_activity(start, end, state)
            start, end = int(creche.fin_pause*(60 / BASE_GRANULARITY)), int(creche.fermeture*(60 / BASE_GRANULARITY))
            self.insert_activity(start, end, state)
        else:
            start, end = int(creche.ouverture*(60 / BASE_GRANULARITY)), int(creche.fermeture*(60 / BASE_GRANULARITY))
            self.insert_activity(start, end, state)
        
    def get_state(self):
        state = ABSENT
        for start, end, value in self.activites:
            if value < 0:
                return value
            elif value == 0:
                state = PRESENT
            elif value == PREVISIONNEL:
                return PRESENT|PREVISIONNEL
        return state
        
    def GetNombreHeures(self):
#        if self.last_heures is not None:
#            return self.last_heures
        self.last_heures = 0.0
        for start, end, value in self.activites:
            if value < 0:
                self.last_heures = 0.0
                return self.last_heures
            elif value == 0:
                self.last_heures += 5.0 * GetDureeArrondie(start, end)
        if creche.mode_facturation == FACTURATION_FORFAIT_10H:
            self.last_heures = 10.0 * (self.last_heures > 0)
        else:
            self.last_heures /= 60
        return self.last_heures
    
    def Copy(self, day, previsionnel=True):
        self.last_heures = None
        self.remove_all_activities()
        for start, end, value in day.activites:
            if previsionnel:
                self.activites[(start, end, value|PREVISIONNEL)] = None
            else:
                self.activites[(start, end, value)] = None            
        for key in day.activites_sans_horaires:
            self.activites_sans_horaires[key] = None
                    
    def GetExtraActivites(self):
        result = set()
        for key in self.activites.keys():
            value = key[2]
            if value > 0:
                result.add(value & ~PREVISIONNEL)
        for value in self.activites_sans_horaires.keys():
            result.add(value)
        return result
    
    def GetPlageHoraire(self):
        debut, fin = None, None
        for start, end, value in self.activites.keys():
            if not debut or start < debut:
                debut = start
            if not fin or end > fin:
                fin = end
        return debut, fin
    
    def delete(self):
        print 'suppression jour'
        for start, end, value in self.activites.keys():
            self.remove_activity(start, end, value)
        for value in self.activites_sans_horaires.keys():
            self.remove_activity(None, None, value)
            
    def remove_activity(self, start, end, value):
        if start is None and end is None:
            if self.activites_sans_horaires[value] is not None:
                print 'suppression %s %d' % (self.nom, self.activites_sans_horaires[value])
                sql_connection.execute('DELETE FROM %s WHERE idx=?' % self.table, (self.activites_sans_horaires[value],))
            del self.activites_sans_horaires[value]
        else:
            if self.activites[(start, end, value)] is not None:
                print 'suppression %s %d' % (self.nom, self.activites[(start, end, value)])
                sql_connection.execute('DELETE FROM %s WHERE idx=?' % self.table, (self.activites[(start, end, value)],))
            del self.activites[(start, end, value)]  

class ReferenceDay(Day):
    table = "REF_ACTIVITIES"
    nom = u"activité de référence"
    
    def __init__(self, inscription, day):
        Day.__init__(self)
        self.inscription = inscription
        self.day = day

    def insert_activity(self, start, end, value):
        print 'nouvelle activite de reference (%r, %r %d)' % (start, end, value), 
        result = sql_connection.execute('INSERT INTO REF_ACTIVITIES (idx, reference, day, value, debut, fin) VALUES (NULL,?,?,?,?,?)', (self.inscription.idx, self.day, value, start, end))
        idx = result.lastrowid
        if start is None and end is None:
            self.activites_sans_horaires[value] = idx
        else:
            self.activites[(start, end, value)] = idx   
        print idx    
       
class Journee(Day):
    table = "ACTIVITES"
    nom = u"activité"
    
    def __init__(self, inscrit, date, reference=None):
        Day.__init__(self)
        self.inscrit_idx = inscrit.idx
        self.date = date
        self.previsionnel = 0
        if reference:
            self.Copy(reference, creche.presences_previsionnelles)

    def insert_activity(self, start, end, value): 
        if sql_connection:
            print 'nouvelle activite (%r, %r, %d)' % (start, end, value),
            result = sql_connection.execute('INSERT INTO ACTIVITES (idx, inscrit, date, value, debut, fin) VALUES (NULL,?,?,?,?,?)', (self.inscrit_idx, self.date, value, start, end))
            idx = result.lastrowid
            print idx
        else:
            idx = None
        if start is None and end is None:
            self.activites_sans_horaires[value] = idx
        else:
            self.activites[(start, end, value)] = idx           
        return idx
        
class Bureau(SQLObject):
    table = "BUREAUX"
    
    def __init__(self, creation=True):
        self.idx = None
        self.debut = None
        self.fin = None
        self.president = ""
        self.vice_president = ""
        self.tresorier = ""
        self.secretaire = ""
        self.directeur = ""

        if creation:
            self.create()

    def create(self):
        print 'nouveau bureau'
        result = sql_connection.execute('INSERT INTO BUREAUX (idx, debut, fin, president, vice_president, tresorier, secretaire, directeur) VALUES (NULL,?,?,?,?,?,?,?)', (self.debut, self.fin, self.president, self.vice_president, self.tresorier, self.secretaire, self.directeur))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression bureau'
        sql_connection.execute('DELETE FROM BUREAUX WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'president', 'vice_president', 'tresorier', 'secretaire', 'directeur'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE BUREAUX SET %s=? WHERE idx=?' % name, (value, self.idx))

class BaremeCAF(object):
    def __init__(self, creation=True):
        self.idx = None
        self.debut = None
        self.fin = None
        self.plancher = 0
        self.plafond = 4000

        if creation:
            self.create()

    def create(self):
        print 'nouveau bareme caf'
        result = sql_connection.execute('INSERT INTO BAREMESCAF (idx, debut, fin, plancher, plafond) VALUES (NULL,?,?,?,?)', (self.debut, self.fin, self.plancher, self.plafond))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression bareme caf'
        sql_connection.execute('DELETE FROM BAREMESCAF WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'plancher', 'plafond'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE BAREMESCAF SET %s=? WHERE idx=?' % name, (value, self.idx))

class Charges(object):
    def __init__(self, date=None, creation=True):
        self.idx = None
        self.date = date
        self.charges = 0.0

        if creation:
            self.create()

    def create(self):
        print 'nouvelles charges'
        result = sql_connection.execute('INSERT INTO CHARGES (idx, date, charges) VALUES (NULL,?,?)', (self.date, self.charges))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression charges'
        sql_connection.execute('DELETE FROM CHARGES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['date', 'charges'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE CHARGES SET %s=? WHERE idx=?' % name, (value, self.idx))

class User(object):
    def __init__(self, creation=True):
        self.idx = None
        self.login = "anonymous"
        self.password = "anonymous"
        self.profile = PROFIL_ALL

        if creation:
            self.create()

    def create(self):
        print 'nouveau user'
        result = sql_connection.execute('INSERT INTO USERS (idx, login, password, profile) VALUES (NULL,?,?,?)', (self.login, self.password, self.profile))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression user'
        sql_connection.execute('DELETE FROM USERS WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['login', 'password', 'profile'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE USERS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Conge(object):
    __table__ = "CONGES"
    
    def __init__(self, parent, creation=True):
        self.idx = None
        self.debut = ""
        self.fin = ""
        self.label = ""
        self.options = 0
        self.parent = parent
        if creation:
            self.create()

    def create(self):
        print 'nouveau conge'
        result = sql_connection.execute('INSERT INTO %s (idx, debut, fin, label, options) VALUES (NULL,?,?,?,?)' % self.__table__, (self.debut, self.fin, self.label, self.options))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression conge'
        sql_connection.execute('DELETE FROM %s WHERE idx=?' % self.__table__, (self.idx,))
        self.parent.calcule_jours_conges()

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'label', 'options'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE %s SET %s=? WHERE idx=?' % (self.__table__, name), (value, self.idx))
            self.parent.calcule_jours_conges()
                
class CongeInscrit(Conge):
    __table__ = "CONGES_INSCRITS"
    
    def create(self):
        print 'nouveau conge'
        result = sql_connection.execute('INSERT INTO %s (idx, inscrit, debut, fin, label) VALUES (NULL,?,?,?,?)' % self.__table__, (self.parent.idx, self.debut, self.fin, self.label))
        self.idx = result.lastrowid

class Activite(object):
    last_value = 0
    def __init__(self, creation=True, value=None):
        self.idx = None
        self.label = ""
        self.value = value
        self.mode = 0
        self.couleur = None
        self.couleur_supplement = None
        self.couleur_previsionnel = None
        self.tarif = 0
        if creation:
            self.create()

    def create(self):
        print 'nouvelle activite', 
        if self.value is None:
            values = creche.activites.keys()
            value = Activite.last_value + 1
            while value in values:
                value += 1
            Activite.last_value = self.value = value
        print self.value
        result = sql_connection.execute('INSERT INTO ACTIVITIES (idx, label, value, mode, couleur, couleur_supplement, couleur_previsionnel, tarif) VALUES(NULL,?,?,?,?,?,?,?)', (self.label, self.value, self.mode, str(self.couleur), str(self.couleur_supplement), str(self.couleur_previsionnel), self.tarif))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression activite'
        sql_connection.execute('DELETE FROM ACTIVITIES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        if name in ("couleur", "couleur_supplement", "couleur_previsionnel") and isinstance(value, basestring):
            self.__dict__[name] = eval(value)
        else:
            self.__dict__[name] = value
        if name in ['label', 'value', 'mode', 'couleur', "couleur_supplement", "couleur_previsionnel", "tarif"] and self.idx:
            print 'update', name, value
            if name in ("couleur", "couleur_supplement", "couleur_previsionnel") and not isinstance(value, basestring):
                value = str(value)
            sql_connection.execute('UPDATE ACTIVITIES SET %s=? WHERE idx=?' % name, (value, self.idx))

class Contrat(object):
    def __init__(self, employe, creation=True):
        self.idx = None
        self.employe = employe
        self.debut = None
        self.fin = None
        self.site = None
        self.fonction = ''
        if creation:
            self.create()

    def create(self):
        print 'nouveau contrat'
        result = sql_connection.execute('INSERT INTO CONTRATS (idx, employe, debut, fin, site, fonction) VALUES (NULL,?,?,?,?,?)', (self.employe.idx, self.debut, self.fin, self.site, self.fonction))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression contrat'
        sql_connection.execute('DELETE FROM CONTRATS WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'site', 'fonction'] and self.idx:
            if name == 'site':
                value = value.idx
            print 'update', name
            sql_connection.execute('UPDATE CONTRATS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Employe(object):
    def __init__(self, creation=True):
        self.idx = None
        self.prenom = ""
        self.nom = ""
        self.telephone_domicile = ""
        self.telephone_domicile_notes = ""
        self.telephone_portable = ""
        self.telephone_portable_notes = ""
        self.email = ""
        self.diplomes = ''
        self.contrats = []
        if creation:
            self.create()

    def create(self):
        print 'nouvel employe'
        result = sql_connection.execute('INSERT INTO EMPLOYES (idx, prenom, nom, telephone_domicile, telephone_domicile_notes, telephone_portable, telephone_portable_notes, email, diplomes) VALUES(NULL,?,?,?,?,?,?,?,?)', (self.prenom, self.nom, self.telephone_domicile, self.telephone_domicile_notes, self.telephone_portable, self.telephone_portable_notes, self.email, self.diplomes))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression employe'
        sql_connection.execute('DELETE FROM EMPLOYES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['prenom', 'nom', 'telephone_domicile', 'telephone_domicile_notes', 'telephone_portable', 'telephone_portable_notes', 'email', 'diplomes'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE EMPLOYES SET %s=? WHERE idx=?' % name, (value, self.idx))

class Professeur(SQLObject):
    table = "PROFESSEURS"
    
    def __init__(self, creation=True):
        self.idx = None
        self.prenom = ""
        self.nom = ""
        self.entree = None
        self.sortie = None
        
        if creation:
            self.create()

    def create(self):
        print 'nouveau professeur'
        result = sql_connection.execute('INSERT INTO PROFESSEURS (idx, prenom, nom, entree, sortie) VALUES(NULL,?,?,?,?)', (self.prenom, self.nom, self.entree, self.sortie))
        self.idx = result.lastrowid

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['prenom', 'nom', 'entree', 'sortie'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE PROFESSEURS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Site(object):
    def __init__(self, creation=True):
        self.idx = None
        self.nom = ''
        self.adresse = ''
        self.code_postal = ''
        self.ville = ''
        self.telephone = ''
        self.capacite = 0
        if creation:
            self.create()

    def create(self):
        print 'nouveau site'
        result = sql_connection.execute('INSERT INTO SITES (idx, nom, adresse, code_postal, ville, telephone, capacite) VALUES(NULL,?,?,?,?,?,?)', (self.nom, self.adresse, self.code_postal, self.ville, self.telephone, self.capacite))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression site'
        sql_connection.execute('DELETE FROM SITES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['nom', 'adresse', 'code_postal', 'ville', 'telephone', 'capacite'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE SITES SET %s=? WHERE idx=?' % name, (value, self.idx))

class Creche(object): 
    def __init__(self):
        self.idx = None
        self.nom = ''
        self.adresse = ''
        self.code_postal = ''
        self.ville = ''
        self.telephone = ''
        self.sites = []
        self.users = []
        self.tarifs_speciaux = []
        self.groupes = []
        self.couleurs = {}
        self.activites = {}
        self.employes = []
        self.professeurs = []
        self.feries = {}
        self.conges = []
        self.bureaux = []
        self.baremes_caf = []
        self.charges = {}
        self.inscrits = []
        self.ouverture = 7.75
        self.fermeture = 18.5
        self.debut_pause = 0.0
        self.fin_pause = 0.0
        self.affichage_min = 7.75
        self.affichage_max = 19.0
        self.granularite = 15
        self.mois_payes = 12
        self.minimum_maladie = 15
        self.mode_facturation = FACTURATION_FORFAIT_10H
        self.temps_facturation = FACTURATION_FIN_MOIS
        self.conges_inscription = 0
        self.tarification_activites = ACTIVITES_NON_FACTUREES
        self.traitement_maladie = DEDUCTION_MALADIE_AVEC_CARENCE_JOURS_CALENDAIRES
        self.preinscriptions = False
        self.presences_previsionnelles = False
        self.presences_supplementaires = True
        self.modes_inscription = MODE_HALTE_GARDERIE + MODE_4_5 + MODE_3_5
        self.email = ''
        self.smtp_server = ''
        self.caf_email = ''
        self.type = TYPE_PARENTAL
        self.capacite = 0
        self.facturation_periode_adaptation = PERIODE_ADAPTATION_FACTUREE_NORMALEMENT
        self.facturation_jours_feries = JOURS_FERIES_NON_DEDUITS
        self.formule_taux_horaire = None
        self.conversion_formule_taux_horaire = None
        self.formule_taux_effort = None
        self.conversion_formule_taux_effort = None
        self.gestion_alertes = False
        self.cloture_factures = False
        self.arrondi_heures = SANS_ARRONDI
        self.gestion_maladie_hospitalisation = False
        self.tri_planning = TRI_PRENOM
        self.alertes = {}
        self.calcule_jours_conges()

    def calcule_jours_conges(self):
        self.jours_fermeture = {}
        self.jours_fete = set()
        self.jours_weekend = []
        self.mois_sans_facture = set()
        for year in range(first_date.year, last_date.year + 1):
            for label, func, enable in jours_fermeture:
                if label in self.feries:
                    tmp = func(year)
                    if isinstance(tmp, list):
                        for j in tmp:
                            self.jours_fermeture[j] = self.feries[label]
                            if label == "Week-end":
                                self.jours_weekend.append(j)
                    else:
                        self.jours_fermeture[tmp] = self.feries[label]

        self.jours_feries = self.jours_fermeture.keys()
        self.jours_fete = set(self.jours_feries) - set(self.jours_weekend)
        self.jours_conges = set()
        def add_periode(debut, fin, conge):
            date = debut
            while date <= fin:
                self.jours_fermeture[date] = conge
                if date not in self.jours_feries:
                    self.jours_conges.add(date)
                date += datetime.timedelta(1)

        for conge in self.conges:
            if conge.options == MOIS_SANS_FACTURE:
                if conge.debut in months:
                    mois = months.index(conge.debut) + 1
                    self.mois_sans_facture.add(mois)
                else:
                    try:
                        mois = int(conge.debut)
                        self.mois_sans_facture.add(mois)
                    except:
                        pass
            else:
                try:
                    count = conge.debut.count('/')
                    if count == 2:
                        debut = str2date(conge.debut)
                        if conge.fin.strip() == "":
                            fin = debut
                        else:
                            fin = str2date(conge.fin)
                        add_periode(debut, fin, conge)
                    elif count == 1:
                        for year in range(first_date.year, last_date.year + 1):
                            debut = str2date(conge.debut, year)
                            if conge.fin.strip() == "":
                                fin = debut
                            else:
                                fin = str2date(conge.fin, year)
                            add_periode(debut, fin, conge)
                except:
                    pass
        
        self.jours_fete = list(self.jours_fete)
        self.jours_feries = list(self.jours_feries)
        self.jours_conges = list(self.jours_conges)

    def add_conge(self, conge, calcule=True):
        conge.creche = self
        if '/' in conge.debut or conge.debut not in [tmp[0] for tmp in jours_fermeture]:
            self.conges.append(conge)
        else:
            self.feries[conge.debut] = conge
        if calcule:
            self.calcule_jours_conges()

    def update_formule_taux_horaire(self, changed=True):
        if changed:
            print 'update formule_taux_horaire', self.formule_taux_horaire
            sql_connection.execute('UPDATE CRECHE SET formule_taux_horaire=?', (str(self.formule_taux_horaire),))
        self.conversion_formule_taux_horaire = self.GetFormuleConversion(self.formule_taux_horaire)
    
    def eval_taux_horaire(self, mode, revenus, enfants, jours, heures):
        return self.EvalFormule(self.conversion_formule_taux_horaire, mode, revenus, enfants, jours, heures)
    
    def formule_taux_horaire_needs_revenus(self):
        if self.mode_facturation in (FACTURATION_FORFAIT_10H, FACTURATION_PSU, FACTURATION_PSU_TAUX_PERSONNALISES):
            return True
        elif self.mode_facturation == FACTURATION_FORFAIT_MENSUEL:
            return False
        if self.formule_taux_horaire is None:
            return False
        for cas in self.formule_taux_horaire:
            if "revenus" in cas[0]:
                return True
        else:
            return False
        
    def test_formule_taux_horaire(self, index):
        return self.TestFormule(self.conversion_formule_taux_horaire, index)
    
    def GetFormuleConversion(self, formule):
        if formule:
            result = []
            for cas in formule:
                condition = cas[0].strip()
                if condition == "":
                    condition = "True"
                else:
                    condition = condition.lower().replace(" et ", " and ").replace(" ou ", " or ").replace("!=", "<>").replace("=", "==").replace("<>", "!=")
                result.append([condition, cas[1], cas[0]])
            return result
        else:
            return None
        
    def EvalFormule(self, formule, mode, revenus, enfants, jours, heures):
        hg = MODE_HALTE_GARDERIE
        creche = MODE_CRECHE
        forfait = MODE_FORFAIT_HORAIRE
        try:
            for cas in formule:
                if eval(cas[0]):
                    return cas[1]
            else:
                return None
        except:
            return None
        
    def TestFormule(self, formule, index):
        hg = MODE_HALTE_GARDERIE
        creche = MODE_CRECHE
        forfait = MODE_FORFAIT_HORAIRE
        mode = hg
        revenus = 20000
        jours = 5
        heures = 60
        enfants = 1
        try:
            test = eval(formule[index][0])
            return True
        except:
            return False
            
    def update_formule_taux_effort(self, changed=True):
        if changed:
            print 'update formule_taux_effort', self.formule_taux_effort
            sql_connection.execute('UPDATE CRECHE SET formule_taux_effort=?', (str(self.formule_taux_effort),))
        self.conversion_formule_taux_effort = self.GetFormuleConversion(self.formule_taux_effort)
    
    def eval_taux_effort(self, mode, revenus, enfants, jours, heures):
        return self.EvalFormule(self.conversion_formule_taux_effort, mode, revenus, enfants, jours, heures)
        
    def test_formule_taux_effort(self, index):
        return self.TestFormule(self.conversion_formule_taux_effort, index)
        
    def HasActivitesAvecHoraires(self):
        count = len(self.activites)
        for activity in self.activites.values():
            if activity.mode == MODE_SANS_HORAIRES:
                count -= 1 
        return count > 1
    
    def GetActivitesSansHoraires(self):
        result = []
        for activite in self.activites.values():
            if activite.mode == MODE_SANS_HORAIRES:
                result.append(activite) 
        return result
    
    def GetAmplitudeHoraire(self):
        return self.fermeture - self.ouverture
        
    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['nom', 'adresse', 'code_postal', 'ville', 'telephone', 'ouverture', 'fermeture', 'debut_pause', 'fin_pause', 'affichage_min', 'affichage_max', 'granularite', 'mois_payes', 'preinscriptions', 'presences_previsionnelles', 'presences_supplementaires', 'modes_inscription', 'minimum_maladie', 'email', 'type', 'capacite', 'mode_facturation', 'temps_facturation', 'conges_inscription', 'tarification_activites', 'traitement_maladie', 'facturation_jours_feries', 'facturation_periode_adaptation', 'gestion_alertes', 'cloture_factures', 'arrondi_heures', 'gestion_maladie_hospitalisation', 'tri_planning', 'smtp_server', 'caf_email'] and self.idx:
            print 'update', name, value
            sql_connection.execute('UPDATE CRECHE SET %s=?' % name, (value,))

class Revenu(object):
    def __init__(self, parent, creation=True):
        self.parent = parent
        self.idx = None
        self.debut = None
        self.fin = None
        self.revenu = ''
        self.chomage = False
        self.regime = 0

        if creation:
            self.create()

    def create(self):
        print 'nouveau revenu'
        result = sql_connection.execute('INSERT INTO REVENUS (idx, parent, debut, fin, revenu, chomage, regime) VALUES(NULL,?,?,?,?,?,?)', (self.parent.idx, self.debut, self.fin, self.revenu, self.chomage, self.regime))
        self.idx = result.lastrowid
        
    def delete(self):
        print 'suppression revenu'
        sql_connection.execute('DELETE FROM REVENUS WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'revenu', 'chomage', 'regime'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE REVENUS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Parent(object):
    def __init__(self, inscrit, relation=None, creation=True):
        self.inscrit = inscrit
        self.idx = None
        self.relation = relation
        self.prenom = ""
        self.nom = ""
        self.telephone_domicile = ""
        self.telephone_domicile_notes = ""
        self.telephone_portable = ""
        self.telephone_portable_notes = ""
        self.telephone_travail = ""
        self.telephone_travail_notes = ""
        self.email = ""
        self.revenus = []
        # self.justificatif_revenu = 0
        # self.justificatif_chomage = 0

        if creation:
            self.create()
            self.revenus.append(Revenu(self))

    def create(self):
        print 'nouveau parent'
        result = sql_connection.execute('INSERT INTO PARENTS (idx, inscrit, relation, prenom, nom, telephone_domicile, telephone_domicile_notes, telephone_portable, telephone_portable_notes, telephone_travail, telephone_travail_notes, email) VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)', (self.inscrit.idx, self.relation, self.prenom, self.nom, self.telephone_domicile, self.telephone_domicile_notes, self.telephone_portable, self.telephone_portable_notes, self.telephone_travail, self.telephone_travail_notes, self.email))
        self.idx = result.lastrowid
        for revenu in self.revenus:
            revenu.create()

    def delete(self):
        print 'suppression parent'
        sql_connection.execute('DELETE FROM PARENTS WHERE idx=?', (self.idx,))
        for revenu in self.revenus:
            revenu.delete()
        for bureau in creche.bureaux:
            for attr in ('president', 'vice_president', 'tresorier', 'secretaire'):
                if getattr(bureau, attr) is self:
                    setattr(bureau, attr, None)

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['relation', 'prenom', 'nom', 'telephone_domicile', 'telephone_domicile_notes', 'telephone_portable', 'telephone_portable_notes', 'telephone_travail', 'telephone_travail_notes', 'email'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE PARENTS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Referent(SQLObject):
    table = "REFERENTS"
    
    def __init__(self, inscrit, creation=True):
        self.inscrit = inscrit
        self.idx = None
        self.prenom = ""
        self.nom = ""
        self.telephone = ""
        
        if creation:
            self.create()

    def create(self):
        print 'nouveau referent'
        result = sql_connection.execute('INSERT INTO REFERENTS (idx, inscrit, prenom, nom, telephone) VALUES(NULL,?,?,?,?)', (self.inscrit.idx, self.prenom, self.nom, self.telephone))
        self.idx = result.lastrowid

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['prenom', 'nom', 'telephone'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE REFERENTS SET %s=? WHERE idx=?' % name, (value, self.idx))

class TarifSpecial(SQLObject):
    table = "TARIFSSPECIAUX"
    def __init__(self, creation=True):
        self.idx = None
        self.label = ""
        self.reduction = False
        self.pourcentage = False
        self.valeur = 0.0
        if creation:
            self.create()
        
    def create(self):
        print 'nouveau tarif special'
        result = sql_connection.execute('INSERT INTO TARIFSSPECIAUX (idx, label, reduction, pourcentage, valeur) VALUES(NULL,?,?,?,?)', (self.label, self.reduction, self.pourcentage, self.valeur))
        self.idx = result.lastrowid
        
    def delete(self):
        SQLObject.delete(self)

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['label', 'reduction', 'pourcentage', 'valeur'] and self.idx:
            print 'update', name, value
            sql_connection.execute('UPDATE TARIFSSPECIAUX SET %s=? WHERE idx=?' % name, (value, self.idx))
    
class Groupe(SQLObject):
    table = "GROUPES"
    def __init__(self, ordre=None, creation=True):
        self.idx = None
        self.nom = ""
        self.ordre = ordre
        if creation:
            self.create()
        
    def create(self):
        print 'nouveau groupe'
        result = sql_connection.execute('INSERT INTO GROUPES (idx, nom, ordre) VALUES(NULL,?,?)', (self.nom, self.ordre))
        self.idx = result.lastrowid
        
    def delete(self):
        SQLObject.delete(self)

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['nom', 'ordre'] and self.idx:
            print 'update', name, value
            sql_connection.execute('UPDATE GROUPES SET %s=? WHERE idx=?' % name, (value, self.idx))
    
class Inscription(SQLObject):
    table = "INSCRIPTIONS"
    def __init__(self, inscrit, duree_reference=7, creation=True):
        self.idx = None
        self.inscrit = inscrit
        self.groupe = None
        self.preinscription = False
        self.site = None
        self.sites_preinscription = []
        self.debut = None
        self.fin = None
        self.mode = MODE_5_5
        self.duree_reference = duree_reference
        self.forfait_heures_presence = 0
        self.semaines_conges = 0
        self.reference = []
        for i in range(duree_reference):
            self.reference.append(ReferenceDay(self, i))
        self.fin_periode_adaptation = None
        self.professeur = None
        self.forfait_mensuel = 0.0
        self.frais_inscription = 0.0
        self.heures_supplementaires = {}

        if creation:
            self.create()
            if creche.modes_inscription == MODE_5_5:
                for i in range(duree_reference):
                    if i % 7 < 5:
                        self.reference[i].set_state(PRESENT)
    
    def setReferenceDuration(self, duration):
        if duration > self.duree_reference:
            for i in range(self.duree_reference, duration):
                self.reference.append(ReferenceDay(self, i))
        else:
            for i in range(duration, self.duree_reference):
                self.reference[i].delete()
            self.reference = self.reference[0:duration]
        self.duree_reference = duration
    
    def getReferenceDay(self, date):
        if self.duree_reference > 7:
            return self.reference[((date - self.debut).days + self.debut.weekday()) % self.duree_reference]
        else:
            return self.reference[date.weekday()]
        
    def getReferenceDayCopy(self, date):
        reference = self.getReferenceDay(date)
        result = Journee(self.inscrit, date, reference)
        result.reference = reference
        return result
        
    def IsInPeriodeAdaptation(self, date):
        if self.debut is None or self.fin_periode_adaptation is None:
            return False
        return date >= self.debut and date <= self.fin_periode_adaptation
    
    def GetJoursHeuresReference(self):
        jours = 0
        heures = 0.0
        for i in range(self.duree_reference):
            if JourSemaineAffichable(i) and self.reference[i].get_state() & PRESENT:
                jours += 1
                heures += self.reference[i].GetNombreHeures()
        return jours, heures
    
    def create(self):
        print 'nouvelle inscription'
        result = sql_connection.execute('INSERT INTO INSCRIPTIONS (idx, inscrit, debut, fin, mode, forfait_mensuel, frais_inscription, fin_periode_adaptation, duree_reference, forfait_heures_presence, semaines_conges) VALUES(NULL,?,?,?,?,?,?,?,?,?,?)', (self.inscrit.idx, self.debut, self.fin, self.mode, self.forfait_mensuel, self.frais_inscription, self.fin_periode_adaptation, self.duree_reference, self.forfait_heures_presence, self.semaines_conges))
        self.idx = result.lastrowid
        
    def delete(self):
        SQLObject.delete(self)
        for object in self.reference:
            object.delete()

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ('site', 'professeur', 'groupe') and self.idx:
            value = value.idx
        elif name == "sites_preinscription":
            value = " ".join([str(value.idx) for value in value])
        if name in ['debut', 'fin', 'mode', 'forfait_mensuel', 'frais_inscription', 'fin_periode_adaptation', 'duree_reference', 'forfait_heures_presence', 'semaines_conges', 'preinscription', 'site', 'sites_preinscription', 'professeur', 'groupe'] and self.idx:
            print 'update', name, value
            sql_connection.execute('UPDATE INSCRIPTIONS SET %s=? WHERE idx=?' % name, (value, self.idx))   

class Frere_Soeur(object):
    def __init__(self, inscrit, creation=True):
        self.idx = None
        self.inscrit = inscrit
        self.prenom = ''
        self.naissance = None
        # self.handicape = 0
        self.entree = None
        self.sortie = None

        if creation:
            self.create()

    def create(self):
        print 'nouveau frere / soeur'
        result = sql_connection.execute('INSERT INTO FRATRIES (idx, inscrit, prenom, naissance, entree, sortie) VALUES(NULL,?,?,?,?,?)', (self.inscrit.idx, self.prenom, self.naissance, self.entree, self.sortie))
        self.idx = result.lastrowid
        
    def delete(self):
        print 'suppression frere / soeur'
        sql_connection.execute('DELETE FROM FRATRIES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['prenom', 'naissance', 'entree', 'sortie'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE FRATRIES SET %s=? WHERE idx=?' % name, (value, self.idx))

class Correction(SQLObject):
    table = "CORRECTIONS"
    
    def __init__(self, inscrit, date, valeur=0, libelle="", idx=None):
        self.idx = idx
        self.inscrit = inscrit
        self.date = date
        self.valeur = valeur
        self.libelle = libelle

    def create(self):
        print 'nouvelle correction'
        result = sql_connection.execute('INSERT INTO CORRECTIONS (idx, inscrit, date, valeur, libelle) VALUES (NULL,?,?,?,?)', (self.inscrit.idx, self.date, self.valeur, self.libelle))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression correction'
        sql_connection.execute('DELETE FROM CORRECTIONS WHERE idx=?', (self.idx,))
        self.idx = None

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['valeur', 'libelle']:
            if self.idx and (self.valeur or self.libelle):
                print 'update', name
                sql_connection.execute('UPDATE CORRECTIONS SET %s=? WHERE idx=?' % name, (value, self.idx))
            elif value and not self.idx:
                self.create()
            elif self.idx and not self.valeur and not self.libelle:
                self.delete()

class Inscrit(object):
    def __init__(self, creation=True):
        self.idx = None
        self.prenom = ""
        self.nom = ""
        self.sexe = None
        self.naissance = None
        self.adresse = ""
        self.code_postal = ""
        self.ville = ""
        self.numero_securite_sociale = ""
        self.numero_allocataire_caf = ""
        self.handicap = False
        self.tarifs = 0
        self.marche = None
        self.photo = None
        self.notes = ""
        self.notes_parents = ""
        self.freres_soeurs = []
        self.parents = { "papa": None, "maman": None }
        self.referents = []
        self.inscriptions = []
        self.conges = []
        self.journees = {}
        self.jours_conges = {}
        self.factures_cloturees = {}
        self.corrections = {}

        if creation:
            self.create()
            self.parents["papa"] = Parent(self, "papa")
            self.parents["maman"] = Parent(self, "maman")
            self.inscriptions.append(Inscription(self))

#        self.reglement_cotisation = 0
#        self.reglement_caution = 0
#        self.reglement_premier_mois = 0
#        self.cheque_depot_garantie = 0
#        self.fiche_medicale = 0
#        self.signature_ri = 0
#        self.signature_permanences = 0
#        self.signature_projet_pedagogique = 0
#        self.signature_projet_etablissement = 0
#        self.signature_contrat_accueil = 0
#        self.autorisation_hospitalisation = 0
#        self.autorisation_transport = 0
#        self.autorisation_image = 0
#        self.autorisation_recherche = 0


    def create(self):
        print 'nouvel inscrit'
        result = sql_connection.execute('INSERT INTO INSCRITS (idx, prenom, nom, naissance, adresse, code_postal, ville, numero_securite_sociale, numero_allocataire_caf, handicap, tarifs, marche, photo, notes, notes_parents) VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (self.prenom, self.nom, self.naissance, self.adresse, self.code_postal, self.ville, self.numero_securite_sociale, self.numero_allocataire_caf, self.handicap, self.tarifs, self.marche, self.photo, self.notes, self.notes_parents))
        self.idx = result.lastrowid
        for obj in self.parents.values() + self.freres_soeurs + self.referents + self.inscriptions: # TODO + self.presences.values():
            if obj: obj.create()
        
    def delete(self):
        print 'suppression inscrit'
        sql_connection.execute('DELETE FROM INSCRITS WHERE idx=?', (self.idx,))
        for obj in self.parents.values() + self.freres_soeurs + self.referents + self.inscriptions + self.journees.values():
            obj.delete()

    def __setattr__(self, name, value):
        if name in self.__dict__:
            old_value = self.__dict__[name]
        else:
            old_value = '-'
        self.__dict__[name] = value
        if name == 'photo' and value:
            value = binascii.b2a_base64(value)
        if name in ['prenom', 'nom', 'sexe', 'naissance', 'adresse', 'code_postal', 'ville', 'numero_securite_sociale', 'numero_allocataire_caf', 'handicap', 'tarifs', 'marche', 'photo', 'notes', 'notes_parents'] and self.idx:
            print 'update', name, (old_value, value)
            sql_connection.execute('UPDATE INSCRITS SET %s=? WHERE idx=?' % name, (value, self.idx))

    def add_conge(self, conge, calcule=True):
        self.conges.append(conge)
        if calcule:
            self.calcule_jours_conges()
            
    def calcule_jours_conges(self, parent=None):
        if parent is None:
            parent = creche
        self.jours_conges = {}

        def add_periode(debut, fin, conge):
            date = debut
            while date <= fin:
                if date not in parent.jours_fermeture:
                    self.jours_conges[date] = conge
                date += datetime.timedelta(1)

        for conge in self.conges:
            try:
                count = conge.debut.count('/')
                if count == 2:
                    debut = str2date(conge.debut)
                    if conge.fin.strip() == "":
                        fin = debut
                    else:
                        fin = str2date(conge.fin)
                    add_periode(debut, fin, conge)
                elif count == 1:
                    for year in range(first_date.year, last_date.year + 1):
                        debut = str2date(conge.debut, year)
                        if conge.fin.strip() == "":
                            fin = debut
                        else:
                            fin = str2date(conge.fin, year)
                        add_periode(debut, fin, conge)
            except:
                pass
        
    def GetInscription(self, date, preinscription=False):
        for inscription in self.inscriptions:
            if (preinscription or not creche.preinscriptions or not inscription.preinscription) and inscription.debut and date >= inscription.debut and (not inscription.fin or date <= inscription.fin):
                return inscription
        return None

    def GetInscriptions(self, date_debut, date_fin):
        result = []
        if not date_debut:
            date_debut = datetime.date.min
        if not date_fin:
            date_fin = datetime.date.max
        for inscription in self.inscriptions:
            if (not creche.preinscriptions or not inscription.preinscription) and inscription.debut:
                try:
                    date_debut_periode = inscription.debut
                    if inscription.fin:
                        date_fin_periode = inscription.fin
                    else:
                        date_fin_periode = datetime.date.max
                    if (date_fin_periode < date_debut_periode):
                        print "Periode incorrecte pour %s %s:" % (self.prenom, self.nom), date_debut_periode, date_fin_periode
                        continue
                    if ((date_debut >= date_debut_periode and date_debut <= date_fin_periode) or 
                        (date_fin >= date_debut_periode and date_fin <= date_fin_periode) or
                        (date_debut < date_debut_periode and date_fin > date_fin_periode)):
                        result.append(inscription)
                except:
                    pass
        return result
    
    def hasFacture(self, date):
        if date.month in creche.mois_sans_facture:
            return False
        month_start = getMonthStart(date)
        if self.GetInscriptions(month_start, getMonthEnd(date)):
            return True
        if creche.temps_facturation != FACTURATION_FIN_MOIS:
            previous_month_end = month_start - datetime.timedelta(1)
            if self.GetInscriptions(getMonthStart(previous_month_end), previous_month_end):
                return True
        return False

    def getReferenceDay(self, date):
        inscription = self.GetInscription(date)
        if inscription:
            return inscription.getReferenceDay(date)
        else:
            return None
        
    def getReferenceDayCopy(self, date):
        inscription = self.GetInscription(date)
        if inscription:
            return inscription.getReferenceDayCopy(date)
        else:
            return None

    def getState(self, date):
        """Retourne les infos sur une journée

        \param date la journée
        \return (état, heures contractualisées, heures realisées, heures supplémentaires)
        """
        if date in creche.jours_fermeture or date in self.jours_conges:
            return ABSENT, 0, 0, 0
        inscription = self.GetInscription(date)
        if inscription is None:
            return ABSENT, 0, 0, 0
        
        reference = self.getReferenceDay(date)
        heures_reference = reference.GetNombreHeures()
        ref_state = reference.get_state()
        if date in self.journees:
            journee = self.journees[date]
            state = journee.get_state()
            if state == MALADE or state == HOPITAL:
                return state, heures_reference, 0, 0
            elif state in (ABSENT, VACANCES):
                if inscription.mode == MODE_5_5 or ref_state:
                    return VACANCES, heures_reference, 0, 0
                else:
                    return ABSENT, heures_reference, 0, 0
            else: # PRESENT
                heures_supplementaires = 0.0
                tranche = 5.0 / 60
                heures_realisees = 0.0
                
                for start, end, value in journee.activites:
                    if value == 0:
                        duration = GetDureeArrondie(start, end)
                        heures_realisees += tranche * duration
                        for s, e, v in reference.activites:
                            if v == 0:
                                a = max(s, start)
                                b = min(e, end)
                                if a < b:
                                    duration -= GetDureeArrondie(a, b)
                        heures_supplementaires += tranche * duration 
                return PRESENT, heures_reference, heures_realisees, heures_supplementaires
        else:
            if ref_state:
                if creche.presences_previsionnelles:
                    return PRESENT|PREVISIONNEL, heures_reference, heures_reference, 0
                else:
                    return PRESENT, heures_reference, heures_reference, 0
            else:
                return ABSENT, 0, 0, 0
            
    def GetExtraActivites(self, date):
        if date in creche.jours_fermeture:
            return []
        inscription = self.GetInscription(date)
        if inscription is None:
            return []
        
        if date in self.journees:
            return self.journees[date].GetExtraActivites()
        else:
            return inscription.getReferenceDay(date).GetExtraActivites()

    def __cmp__(self, other):
        if other is self: return 0
        if other is None: return 1
        return cmp("%s %s" % (self.prenom, self.nom), "%s %s" % (other.prenom, other.nom))

class Alerte(object):
    def __init__(self, date, texte, acquittement=False, creation=True):
        self.idx = None
        self.date = date
        self.texte = texte
        self.acquittement = acquittement
        if creation:
            self.create()

    def create(self):
        print 'nouvelle alerte'
        result = sql_connection.execute('INSERT INTO ALERTES (idx, date, texte, acquittement) VALUES(NULL,?,?,?)', (self.date, self.texte, self.acquittement))
        self.idx = result.lastrowid
        
    def delete(self):
        print 'suppression alerte'
        sql_connection.execute('DELETE FROM ALERTES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['acquittement'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE ALERTES SET %s=? WHERE idx=?' % name, (value, self.idx))