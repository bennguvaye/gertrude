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
from ooffice import *


class ReleveSalariesModifications(object):
    title = "Relevés salariés"
    template = "Releve salaries.ods"

    def __init__(self, salaries, periode):
        self.salaries = salaries
        self.periode = periode
        self.email = None
        self.site = None
        self.multi = False
        if len(salaries) > 1:
            self.default_output = "Releve salaries %s %d.ods" % (months[periode.month-1], periode.year)
        else:
            who = salaries[0]
            self.default_output = "Releve salaries %s - %s %d.ods" % (GetPrenomNom(who), months[periode.month - 1], periode.year)
    
    def GetFields(self, salarie):
        fields = [('nom-creche', database.creche.nom),
                  ('adresse-creche', database.creche.adresse),
                  ('code-postal-creche', str(database.creche.code_postal)),
                  ('departement-creche', GetDepartement(database.creche.code_postal)),
                  ('ville-creche', database.creche.ville),
                  ('telephone-creche', database.creche.telephone),
                  ('email-creche', database.creche.email),
                  ('prenom', salarie.prenom),
                  ('nom', salarie.nom),
                  ('mois', months[self.periode.month-1]),
                  ('annee', self.periode.year)
                  ]
        day = self.periode
        weekday = day.weekday()
        if weekday >= 5:
            day += datetime.timedelta(7 - weekday)
        elif weekday >= 1 or weekday <= 4:
            day -= datetime.timedelta(weekday)
        semaines = 0
        while day.year < self.periode.year or (day.year == self.periode.year and day.month <= self.periode.month):
            semaines += 1
            for i in range(7):
                if day.month == self.periode.month:
                    contrat = salarie.get_contrat(day)
                    if contrat is not None:
                        heures = salarie.days.get(day, salarie.GetJourneeReference(day)).get_duration()
                    else:
                        heures = 0
                else:
                    heures = ""
                fields.append(("%s-%d" % (days[i].lower(), semaines), heures))                    
                day += datetime.timedelta(1)
        _, contrat, realise, _, _ = salarie.GetDecompteHeuresEtConges(GetMonthStart(self.periode), GetMonthEnd(self.periode))
        fields.append(('delta', realise - contrat))
        return semaines, fields

    def execute(self, filename, dom):
        if filename != 'content.xml':
            return None
        
        spreadsheet = dom.getElementsByTagName('office:spreadsheet').item(0)
        table = spreadsheet.getElementsByTagName("table:table").item(0)       
        lignes = table.getElementsByTagName("table:table-row")
        
        LINES = 16
        template = lignes[1:LINES + 1]
        last_line = lignes[LINES + 1]
        for line in template:
            table.removeChild(line)

        inc = 0
        for salarie in self.salaries:
            if salarie.get_contrat(datetime.date.today()):
                semaines, fields = self.GetFields(salarie)
                lignes = []
                for l, line in enumerate(template):
                    if l == LINES-1 or l < LINES-1-(5-semaines)*2:
                        clone = line.cloneNode(1)
                        lignes.append(clone)
                        if l == LINES - 1:
                            ReplaceFormulas(clone, "SUM([.G8:.G16])", "SUM([.G%d:.G%d])" % (8+inc, 8+inc+2*(semaines-1)))
                        else:
                            IncrementFormulas(clone, row=+inc)
                        table.insertBefore(clone, last_line)
                ReplaceFields(lignes, fields)
                inc += LINES - (5-semaines) * 2
