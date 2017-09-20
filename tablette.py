# -*- coding: utf-8 -*-

#    This file is part of Gertrude.
#
#    Gertrude is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 3 of the License, or
#    (at your option) any later version.
#
#    Gertrude is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Gertrude; if not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
from __future__ import print_function

# TODO pb in GetActivitiesSummary from __future__ import division

import datetime
import urllib
from constants import *
from functions import *
from globals import *


def write_apache_logs_to_journal(filename):
    # Recuperation des logs Apache
    lines = file(filename).readlines()
    result = []
    for line in lines:
        print(line)
        splitted = line.split()
        url = splitted[6]
        action = None
        combinaison = None
        ts = None
        params = url.split("?")[1].split("&")
        for param in params:
            key, val = param.split("=")
            if key == "action":
                action = val
            elif key == "combinaison":
                combinaison = val
            elif key == "ts":
                ts = int(val)

        who = None
        for inscrit in creche.inscrits:
            letter = inscrit.nom[0] if len(inscrit.nom) > 0 else ""
            name = urllib.quote_plus(inscrit.prenom.encode("utf-8")) + "+" + urllib.quote_plus(letter.encode("utf-8"))
            # print "comparaison", name, combinaison
            if name == combinaison:
                who = inscrit

        if who is None:
            for inscrit in creche.salaries:
                letter = inscrit.nom[0] if len(inscrit.nom) > 0 else ""
                name = urllib.quote_plus(inscrit.prenom.encode("utf-8")) + "+" + urllib.quote_plus(letter.encode("utf-8"))
                # print "comparaison", name, combinaison
                if name == combinaison:
                    action += "_salarie"
                    who = inscrit

        if who is None:
            if combinaison.strip():
                print("-----ERREUR-----", action, combinaison, ts)
        else:
            date = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d@%H:%M')
            if (action, who.idx, date) in result:
                print("-----ENTREE EN DOUBLE-----", url)
            else:
                result.append((action, who.idx, date))

    result.sort(key=lambda tup: tup[-1])  # sorts in place
    f = file("journal.txt", "w")
    for action, idx, date in result:
        print(action, idx, date)
        f.write("%s %d %s\n" % (action, idx, date))
    f.close()


def sync_tablette_lines(lines, tz=None):
    last_imported_day = datetime.date.today()
    date = datetime.datetime.now(tz=tz)
    hour = float(date.hour) + float(date.minute) / 60
    if hour < creche.fermeture:
        last_imported_day -= datetime.timedelta(1)

    def AddPeriodes(who, date, periodes):
        if date in who.journees:
            journee = who.journees[date]
            journee.RemoveActivities(0)
            journee.RemoveActivities(0 | PREVISIONNEL)
        else:
            journee = who.AddJournee(date)
        for periode in periodes:
            AddPeriode(who, journee, periode)

    def AddPeriode(who, journee, periode):
        value = 0
        if periode.absent:
            value = VACANCES
        elif periode.malade:
            value = MALADE
        elif not periode.arrivee:
            errors.append(u"%s : Pas d'arrivée enregistrée le %s" % (GetPrenomNom(who), periode.date))
            periode.arrivee = int(creche.ouverture * (60 / BASE_GRANULARITY))
        elif not periode.depart:
            errors.append(u"%s : Pas de départ enregistré le %s" % (GetPrenomNom(who), periode.date))
            periode.depart = int(creche.fermeture * (60 / BASE_GRANULARITY))

        if value < 0:
            journee.SetState(value)
        else:
            journee.SetActivity(periode.arrivee, periode.depart, value)
        history.Append(None)

    array_enfants = {}
    array_salaries = {}

    for line in lines:
        if len(line) < 20:
            break

        try:
            salarie, label, idx, date, heure = SplitLineTablette(line)
            if date > last_imported_day:
                break
            if salarie:
                array = array_salaries
            else:
                array = array_enfants
            if idx not in array:
                array[idx] = {}
            if date not in array[idx]:
                array[idx][date] = []
            if label == "arrivee":
                arrivee = (heure + TABLETTE_MARGE_ARRIVEE) / creche.granularite * (creche.granularite / BASE_GRANULARITY)
                if len(array[idx][date]) == 0 or (array[idx][date][-1].arrivee and array[idx][date][-1].depart):
                    array[idx][date].append(PeriodePresence(date, arrivee))
                elif array[idx][date][-1].depart:
                    array[idx][date][-1].arrivee = array[idx][date][-1].depart
                    array[idx][date][-1].depart = None
            elif label == "depart":
                depart = (heure + creche.granularite - TABLETTE_MARGE_ARRIVEE) / creche.granularite * (creche.granularite / BASE_GRANULARITY)
                if len(array[idx][date]) > 0:
                    last = array[idx][date][-1]
                    last.depart = depart
                else:
                    array[idx][date].append(PeriodePresence(date, None, depart))
            elif label == "absent":
                array[idx][date].append(PeriodePresence(date, absent=True))
            elif label == "malade":
                array[idx][date].append(PeriodePresence(date, malade=True))
            else:
                print("Ligne %s inconnue" % label)
            creche.last_tablette_synchro = line
        except Exception as e:
            print(e)

    # print array_salaries

    errors = []
    for key in array_enfants:
        inscrit = creche.GetInscrit(key)
        if inscrit:
            for date in array_enfants[key]:
                if not creche.cloture_facturation or not inscrit.IsFactureCloturee(date):
                    AddPeriodes(inscrit, date, array_enfants[key][date])
        else:
            errors.append(u"Inscrit %d: Inconnu!" % key)
    for key in array_salaries:
        salarie = creche.GetSalarie(key)
        if salarie:
            for date in array_salaries[key]:
                # print key, GetPrenomNom(salarie), periode
                AddPeriodes(salarie, date, array_salaries[key][date])
        else:
            errors.append(u"Salarié %d: Inconnu!" % key)

    return errors


def sync_tablette():
    print("Synchro tablette ...")

    journal = config.connection.LoadJournal()
    if not journal:
        return

    lines = journal.split("\n")

    index = -1
    if len(creche.last_tablette_synchro) > 20:
        try:
            index = lines.index(creche.last_tablette_synchro)
        except:
            pass

    if config.saas_port:
        import pytz
        tz = pytz.timezone('Europe/Paris')
    else:
        tz = None
    sync_tablette_lines(lines[index + 1:], tz)


if __name__ == "__main__":
    import __builtin__
    import config
    import sqlinterface

    __builtin__.sql_connection = sqlinterface.SQLConnection(sys.argv[1])
    __builtin__.creche = sql_connection.Load(None)

    # write_apache_logs_to_journal("D:/logs")

    lines = file(sys.argv[2]).readlines()
    sync_tablette_lines(lines)
    sql_connection.close()
