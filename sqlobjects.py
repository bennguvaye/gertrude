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

class Day(object):
    def __init__(self):
        self.activites = {}
        self.values = [0] * 24 * (60 / BASE_GRANULARITY)

    def save(self):            
        old_activities = self.activites.keys()
        new_activities = self.get_activities()
        for activity in new_activities:
            if activity in old_activities:
                old_activities.remove(activity)
            else:
                a, b, v = activity
                self.insert_activity(a, b, v)
        for a, b, v in old_activities:
            self.remove_activity(a, b, v)

    def get_activities(self, reference=None):
        result = []
        for value in creche.activites.keys():
            mask = (1 << value)
            a = v = h = 0
            while h <= 24 * 60 / BASE_GRANULARITY:
                if h == 24 * 60 / BASE_GRANULARITY:
                    nv = 0
                elif self.values[h] < 0:
                    if value == 0:
                        nv = self.values[h]
                    else:
                        nv = 0
                else:
                    nv = self.values[h] & mask
                    if nv:
                        if creche.presences_previsionnelles and self.values[h] & PREVISIONNEL:
                            nv += PREVISIONNEL
                        elif creche.presences_supplementaires and reference and not (reference.values[h] & mask):
                            nv += SUPPLEMENT
                if nv != v:
                    if v < 0:
                        result.append((a, h, v))
                    elif v > 0:
                        result.append((a, h, value+(v&PREVISIONNEL)+(v&SUPPLEMENT)))
                    a = h
                    v = nv
                h += 1
        return result        

    def add_activity(self, start, end, value, idx):
        for i in range(start, end):
            if value >= 0:
                self.values[i] |= (1 << (value % PREVISIONNEL)) + (value & PREVISIONNEL)
            else:
                self.values[i] = value
        self.activites[(start, end, value)] = idx
        
    def remove_all_activities(self, value):
        mask = ~(1 << value)
        for i in range(24 * 60 / BASE_GRANULARITY):
            if self.values[i] > 0:
                self.values[i] &= mask
                if self.values[i] == PREVISIONNEL:
                    self.values[i] = 0
        self.save()
            
    def set_state(self, state):
        start, end = int(creche.ouverture*(60 / BASE_GRANULARITY)), int(creche.fermeture*(60 / BASE_GRANULARITY))
        self.values[start:end] = [state] * (end-start)
        self.save()
        
    def get_state(self):
        state = ABSENT
        for i in range(24 * 60 / BASE_GRANULARITY):
            if self.values[i] < 0:
                return self.values[i]
            else:
                state |= self.values[i]
#        activities_state = state & ~(PRESENT|PREVISIONNEL)
#        if activities_state:
#            state &= ~activities_state
#            state |= PRESENT
        if state == PREVISIONNEL:
            return ABSENT
        else:
            return state
        
    def get_heures(self):
        heures = 0.0
        for i in range(24 * 60 / BASE_GRANULARITY):
            if self.values[i] < 0:
                return 0.0
            elif self.values[i] > 0:
                heures += 5.0 / 60
        return heures
    
    def copy(self, day, previsionnel=True):
        self.values = day.values[:]
        if previsionnel:
            for i in range(24 * 60 / BASE_GRANULARITY):
                if self.values[i]:
                    self.values[i] |= PREVISIONNEL
                    
    def get_extra_activities(self):
        result = set()
        for value in creche.activites.keys():
            mask = (1 << value)
            for h in range(24 * 60 / BASE_GRANULARITY):
                if self.values[h] > 0 and self.values[h] & mask:
                    result.add(value)
                    break
        return result        
        

class ReferenceDay(Day):
    def __init__(self, inscription, day):
        Day.__init__(self)
        self.inscription = inscription
        self.day = day

    def insert_activity(self, start, end, value):
        print 'nouvelle activite de reference (%d, %d, %d)' % (start, end, value), 
        result = sql_connection.execute('INSERT INTO REF_ACTIVITIES (idx, reference, day, value, debut, fin) VALUES (NULL,?,?,?,?,?)', (self.inscription.idx, self.day, value, start, end))
        idx = result.lastrowid
        self.activites[(start, end, value)] = idx
        print idx
        
    def remove_activity(self, start, end, value):
        print 'suppression activite de reference %d' % self.activites[(start, end, value)]
        sql_connection.execute('DELETE FROM REF_ACTIVITIES WHERE idx=?', (self.activites[(start, end, value)],))
        del self.activites[(start, end, value)]
        
    def delete(self):
        print 'suppression jour de reference %d' % self.day
        for start, end, value in self.activites.keys():
            self.remove_activity(start, end, value)
        
       
class Journee(Day):
    def __init__(self, inscrit, date, reference=None):
        Day.__init__(self)
        self.inscrit_idx = inscrit.idx
        self.date = date
        self.previsionnel = 0
        if reference:
            self.copy(reference, creche.presences_previsionnelles)

    def insert_activity(self, start, end, value):
        print 'nouvelle activite (%d, %d, %d)' % (start, end, value), 
        result = sql_connection.execute('INSERT INTO ACTIVITES (idx, inscrit, date, value, debut, fin) VALUES (NULL,?,?,?,?,?)', (self.inscrit_idx, self.date, value, start, end))
        idx = result.lastrowid
        self.activites[(start, end, value)] = idx
        print idx
        
    def remove_activity(self, start, end, value):
        print 'suppression activite %d' % self.activites[(start, end, value)]
        sql_connection.execute('DELETE FROM ACTIVITES WHERE idx=?', (self.activites[(start, end, value)],))
        del self.activites[(start, end, value)]
       
    def confirm(self):
        for i in range(24 * 60 / BASE_GRANULARITY):
            self.values[i] &= ~PREVISIONNEL
        self.save()
        
class Bureau(object):
    def __init__(self, creation=True):
        self.idx = None
        self.debut = None
        self.fin = None
        self.president = None
        self.vice_president = None
        self.tresorier = None
        self.secretaire = None

        if creation:
            self.create()

    def create(self):
        print 'nouveau bureau'
        result = sql_connection.execute('INSERT INTO BUREAUX (idx, debut, fin, president, vice_president, tresorier, secretaire) VALUES (NULL,?,?,?,?,?,?)', (self.debut, self.fin, None, None, None, None))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression bureau'
        sql_connection.execute('DELETE FROM BUREAUX WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'president', 'vice_president', 'tresorier', 'secretaire'] and self.idx:
            if name in ['president', 'vice_president', 'tresorier', 'secretaire'] and value is not None:
                value = value.idx
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
    def __init__(self, creation=True):
        self.idx = None
        self.debut = ""
        self.fin = ""
        self.label = ""
        self.options = 0
        self.creche = None

        if creation:
            self.create()

    def create(self):
        print 'nouveau conge'
        result = sql_connection.execute('INSERT INTO CONGES (idx, debut, fin) VALUES (NULL,?,?)', (self.debut, self.fin))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression conge'
        sql_connection.execute('DELETE FROM CONGES WHERE idx=?', (self.idx,))
        if self.creche:
            self.creche.calcule_jours_fermeture()

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'label', 'options'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE CONGES SET %s=? WHERE idx=?' % name, (value, self.idx))
            if self.creche:
                self.creche.calcule_jours_fermeture()

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

class Employe(object):
    def __init__(self, creation=True):
        self.idx = None
        self.date_embauche = None
        self.prenom = ""
        self.nom = ""
        self.telephone_domicile = ""
        self.telephone_domicile_notes = ""
        self.telephone_portable = ""
        self.telephone_portable_notes = ""
        self.email = ""

        if creation:
            self.create()

    def create(self):
        print 'nouvel employe'
        result = sql_connection.execute('INSERT INTO EMPLOYES (idx, date_embauche, prenom, nom, telephone_domicile, telephone_domicile_notes, telephone_portable, telephone_portable_notes, email) VALUES(NULL,?,?,?,?,?,?,?,?)', (self.date_embauche, self.prenom, self.nom, self.telephone_domicile, self.telephone_domicile_notes, self.telephone_portable, self.telephone_portable_notes, self.email))
        self.idx = result.lastrowid

    def delete(self):
        print 'suppression employe'
        sql_connection.execute('DELETE FROM EMPLOYES WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['date_embauche', 'prenom', 'nom', 'telephone_domicile', 'telephone_domicile_notes', 'telephone_portable', 'telephone_portable_notes', 'email'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE EMPLOYES SET %s=? WHERE idx=?' % name, (value, self.idx))

class Creche(object): 
    def __init__(self):
        self.idx = None
        self.nom = ''
        self.adresse = ''
        self.code_postal = ''
        self.ville = ''
        self.telephone = ''
        self.users = []
        self.couleurs = {}
        self.activites = {}
        self.employes = []
        self.feries = {}
        self.conges = []
        self.bureaux = []
        self.baremes_caf = []
        self.inscrits = []
        self.ouverture = 7.75
        self.fermeture = 18.5
        self.affichage_min = 7.75
        self.affichage_max = 19.0
        self.granularite = 15
        self.mois_payes = 12
        self.minimum_maladie = 15
        self.mode_facturation = FACTURATION_FORFAIT_10H
        self.tarification_activites = ACTIVITES_NON_FACTUREES
        self.traitement_maladie = DEDUCTION_MALADIE_AVEC_CARENCE
        self.presences_previsionnelles = False
        self.presences_supplementaires = True
        self.modes_inscription = MODE_HALTE_GARDERIE + MODE_4_5 + MODE_3_5
        self.email = ''
        self.type = TYPE_PARENTAL
        self.capacite = 0
        self.forfait_horaire = 0.0
        self.majoration_localite = 0.0
        self.facturation_jours_feries = JOURS_FERIES_NON_DEDUITS
        self.calcul_taux_effort = TAUX_EFFORT_AUTO
        self.calcule_jours_fermeture()

    def calcule_jours_fermeture(self):
        self.jours_fermeture = {}        
        for year in range(first_date.year, last_date.year + 1):
            for label, func, enable in jours_fermeture:
                if label in self.feries:
                    tmp = func(year)
                    if isinstance(tmp, list):
                        for j in tmp:
                            self.jours_fermeture[j] = self.feries[label]
                    else:
                        self.jours_fermeture[tmp] = self.feries[label]
        self.jours_feries = self.jours_fermeture.keys()

        def add_periode(debut, fin, conge):
            date = debut
            while date <= fin:
                self.jours_fermeture[date] = conge
                date += datetime.timedelta(1)

        for conge in self.conges:
            if conge.options != MOIS_SANS_FACTURE:
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

    def add_conge(self, conge):
        conge.creche = self
        if '/' in conge.debut or conge.debut not in [tmp[0] for tmp in jours_fermeture]:
            self.conges.append(conge)
        else:
            self.feries[conge.debut] = conge
        self.calcule_jours_fermeture()

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['nom', 'adresse', 'code_postal', 'ville', 'telephone', 'ouverture', 'fermeture', 'affichage_min', 'affichage_max', 'granularite', 'mois_payes', 'presences_previsionnelles', 'presences_supplementaires', 'modes_inscription', 'minimum_maladie', 'email', 'type', 'capacite', 'mode_facturation', 'forfait_horaire', 'tarification_activites', 'traitement_maladie', 'forfait_horaire', 'majoration_localite', 'facturation_jours_feries', 'calcul_taux_effort'] and self.idx:
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
    def __init__(self, inscrit, creation=True):
        self.inscrit = inscrit
        self.idx = None
        self.absent = False
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
        result = sql_connection.execute('INSERT INTO PARENTS (idx, inscrit, absent, prenom, nom, telephone_domicile, telephone_domicile_notes, telephone_portable, telephone_portable_notes, telephone_travail, telephone_travail_notes, email) VALUES(NULL,?,?,?,?,?,?,?,?,?,?,?)', (self.inscrit.idx, self.absent, self.prenom, self.nom, self.telephone_domicile, self.telephone_domicile_notes, self.telephone_portable, self.telephone_portable_notes, self.telephone_travail, self.telephone_travail_notes, self.email))
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
        if name in ['absent', 'prenom', 'nom', 'telephone_domicile', 'telephone_domicile_notes', 'telephone_portable', 'telephone_portable_notes', 'telephone_travail', 'telephone_travail_notes', 'email'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE PARENTS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Referent(object):
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

    def delete(self):
        print 'suppression referent'
        sql_connection.execute('DELETE FROM REFERENTS WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['prenom', 'nom', 'telephone'] and self.idx:
            print 'update', name
            sql_connection.execute('UPDATE REFERENTS SET %s=? WHERE idx=?' % name, (value, self.idx))

class Inscription(object):
    def __init__(self, inscrit, duree_reference=7, creation=True):
        self.inscrit = inscrit
        self.idx = None
        self.debut = None
        self.fin = None
        self.mode = MODE_5_5
        self.duree_reference = duree_reference
        self.semaines_conges = 0
        self.taux_effort = .0
        self.reference = []
        for i in range(duree_reference):
            self.reference.append(ReferenceDay(self, i))
        self.fin_periode_essai = None

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
    
    def create(self):
        print 'nouvelle inscription'
        result = sql_connection.execute('INSERT INTO INSCRIPTIONS (idx, inscrit, debut, fin, mode, fin_periode_essai, duree_reference, semaines_conges, taux_effort) VALUES(NULL,?,?,?,?,?,?,?,?)', (self.inscrit.idx, self.debut, self.fin, self.mode, self.fin_periode_essai, self.duree_reference, self.semaines_conges, self.taux_effort))
        self.idx = result.lastrowid
        
    def delete(self):
        print 'suppression inscription'
        sql_connection.execute('DELETE FROM INSCRIPTIONS WHERE idx=?', (self.idx,))

    def __setattr__(self, name, value):
        self.__dict__[name] = value
        if name in ['debut', 'fin', 'mode', 'fin_periode_essai', 'duree_reference', 'semaines_conges', 'taux_effort'] and self.idx:
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
        self.majoration = False
        self.marche = None
        self.photo = None
        self.freres_soeurs = []
        self.papa = None
        self.maman = None
        self.referents = []
        self.inscriptions = []
        self.journees = { }

        if creation:
            self.create()
            self.papa = Parent(self)
            self.maman = Parent(self)
            self.inscriptions.append(Inscription(self))

#       self.handicape = 0
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
        result = sql_connection.execute('INSERT INTO INSCRITS (idx, prenom, nom, naissance, adresse, code_postal, ville, majoration, marche, photo) VALUES(NULL,?,?,?,?,?,?,?,?,?)', (self.prenom, self.nom, self.naissance, self.adresse, self.code_postal, self.ville, self.majoration, self.marche, self.photo))
        self.idx = result.lastrowid
        for obj in [self.papa, self.maman] + self.freres_soeurs + self.referents + self.inscriptions: # TODO + self.presences.values():
            if obj: obj.create()
        
    def delete(self):
        print 'suppression inscrit'
        sql_connection.execute('DELETE FROM INSCRITS WHERE idx=?', (self.idx,))
        for obj in [self.papa, self.maman] + self.freres_soeurs + self.referents + self.inscriptions + self.journees.values():
            obj.delete()

    def __setattr__(self, name, value):
        if name in self.__dict__:
            old_value = self.__dict__[name]
        else:
            old_value = '-'
        self.__dict__[name] = value
        if name == 'photo' and value:
            value = binascii.b2a_base64(value)
        if name in ['prenom', 'nom', 'sexe', 'naissance', 'adresse', 'code_postal', 'ville', 'majoration', 'marche', 'photo'] and self.idx:
            print 'update', name, (old_value, value)
            sql_connection.execute('UPDATE INSCRITS SET %s=? WHERE idx=?' % name, (value, self.idx))

    def getInscription(self, date):
        return Select(self.inscriptions, date)

    def getInscriptions(self, date_debut, date_fin):
        result = []
        for i, inscription in enumerate(self.inscriptions):
          if inscription.debut:
            try:
              date_debut_periode = inscription.debut
              if inscription.fin:
                date_fin_periode = inscription.fin
              else:
                date_fin_periode = datetime.date.max
              if ((date_debut >= date_debut_periode and date_debut <= date_fin_periode) or 
                  (date_fin >= date_debut_periode and date_fin <= date_fin_periode) or
                  (date_debut < date_debut_periode and date_fin > date_fin_periode)):
                  result.append(inscription)
            except:
              pass
        return result

    def getReferenceDay(self, date):
        inscription = self.getInscription(date)
        if inscription:
            return inscription.getReferenceDay(date)
        else:
            return None
        
    def getReferenceDayCopy(self, date):
        reference = self.getReferenceDay(date)
        if reference:
            return Journee(self, date, reference)
        else:
            return None

    def getState(self, date):
        if date in creche.jours_fermeture:
            return ABSENT, 0
        inscription = self.getInscription(date)
        if inscription is None:
            return ABSENT, 0
        
        reference = self.getReferenceDay(date)
        ref_state = reference.get_state()
        if date in self.journees:
            journee = self.journees[date]
            state = journee.get_state()
            if state == MALADE:
                return MALADE, 0
            elif state in (ABSENT, VACANCES):
                if inscription.mode == MODE_5_5 or ref_state:
                    return VACANCES, 0
                else:
                    return ABSENT, 0
            else: # PRESENT
                supplement = 0.0
                for i in range(24 * 60 / BASE_GRANULARITY):
                    if journee.values[i] and not reference.values[i]:
                        supplement += 5.0 / 60
                if inscription.mode == MODE_5_5 or ref_state:
                    return PRESENT, supplement
                else:
                    return PRESENT|SUPPLEMENT, supplement
        else:
            if ref_state:
                if creche.presences_previsionnelles and date > today:
                    return PRESENT|PREVISIONNEL, 0
                else:
                    return PRESENT, 0
            else:
                return ABSENT, 0
            
    def getActivites(self, date):
        if date in creche.jours_fermeture:
            return []
        inscription = self.getInscription(date)
        if inscription is None:
            return []
        
        reference = self.getReferenceDay(date)
        result = reference.get_extra_activities()
        if date in self.journees:
            journee = self.journees[date]
            result.update(journee.get_extra_activities())
        result.discard(0)
        return result

    def __cmp__(self, other):
        if other is self: return 0
        if other is None: return 1
        return cmp("%s %s" % (self.prenom, self.nom), "%s %s" % (other.prenom, other.nom))
