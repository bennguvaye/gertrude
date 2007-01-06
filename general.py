# -*- coding: cp1252 -*-

import os.path
import datetime
from wxPython.wx import *
from common import *
from planning import GPanel
from Controls import *

class CrechePanel(AutoTab):
    def __init__(self, parent, creche):
        AutoTab.__init__(self, parent)
        self.creche = creche
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer2 = wx.FlexGridSizer(4, 2, 5, 5)
        sizer2.AddMany([wx.StaticText(self, -1, u'Nom de la cr�che :'), AutoTextCtrl(self, self.creche, 'nom')])
        sizer2.AddMany([wx.StaticText(self, -1, 'Adresse :'), AutoTextCtrl(self, self.creche, 'adresse')])
        sizer2.AddMany([wx.StaticText(self, -1, 'Code Postal :'), AutoNumericCtrl(self, self.creche, 'code_postal', precision=0)])
        sizer2.AddMany([wx.StaticText(self, -1, 'Ville :'), AutoTextCtrl(self, self.creche, 'ville')])       
        sizer.Add(sizer2)
        sizer.Fit(self)
        self.SetSizer(sizer)
        
class ResponsabilitesPanel(AutoTab):
    def __init__(self, parent, creche, inscrits):
        AutoTab.__init__(self, parent)
        self.creche = creche
        self.inscrits = inscrits
        parents = self.GetNomsParents()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(PeriodeChoice(self, creche, 'bureaux', Bureau))
        sizer2 = wx.FlexGridSizer(4, 2, 5, 5)
        self.responsables_ctrls = []
        self.responsables_ctrls.append(AutoChoiceCtrl(self, creche, 'bureaux[self.parent.periode].president', items=parents))
        sizer2.AddMany([wx.StaticText(self, -1, u'Pr�sident :'), self.responsables_ctrls[-1]])
        self.responsables_ctrls.append(AutoChoiceCtrl(self, creche, 'bureaux[self.parent.periode].vice_president', items=parents))
        sizer2.AddMany([wx.StaticText(self, -1, u'Vice pr�sident :'), self.responsables_ctrls[-1]])
        self.responsables_ctrls.append(AutoChoiceCtrl(self, creche, 'bureaux[self.parent.periode].tresorier', items=parents))
        sizer2.AddMany([wx.StaticText(self, -1, u'Tr�sorier :'), self.responsables_ctrls[-1]])
        self.responsables_ctrls.append(AutoChoiceCtrl(self, creche, 'bureaux[self.parent.periode].secretaire', items=parents))        
        sizer2.AddMany([wx.StaticText(self, -1, u'Secr�taire :'), self.responsables_ctrls[-1]])
        sizer.Add(sizer2)
        sizer.Fit(self)
        self.SetSizer(sizer)

    def UpdateContents(self):
        parents = self.GetNomsParents()
        for ctrl in self.responsables_ctrls:
            ctrl.SetItems(parents)
        AutoTab.UpdateContents(self)

    def GetNomsParents(self):
        result = []
        parents = []
        for inscrit in self.inscrits:
            for parent in (inscrit.papa, inscrit.maman):
                if parent.prenom and parent.nom:
                    tmp = parent.prenom + ' ' + parent.nom
                    if not tmp in parents:
                        parents.append(tmp)
                        result.append((tmp, parent))
        result.sort(cmp=lambda x,y: cmp(x[0].lower(), y[0].lower()))
        return result

class CafPanel(AutoTab):
    def __init__(self, parent, creche):
        AutoTab.__init__(self, parent)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(PeriodeChoice(self, creche, 'baremes_caf', BaremeCAF))
        sizer2 = wx.FlexGridSizer(4, 2, 5, 5)
        sizer2.AddMany([wx.StaticText(self, -1, 'Plancher :'), AutoNumericCtrl(self, creche, 'baremes_caf[self.parent.periode].plancher', precision=2)])
        sizer2.AddMany([wx.StaticText(self, -1, 'Plafond :'), AutoNumericCtrl(self, creche, 'baremes_caf[self.parent.periode].plafond', precision=2)])
        sizer.Add(sizer2)
        sizer.Fit(self)
        self.SetSizer(sizer)
        
class GeneralNotebook(wx.Notebook):
    def __init__(self, parent, creche, inscrits):
        wx.Notebook.__init__(self, parent, style=wx.LB_DEFAULT)
        self.AddPage(CrechePanel(self, creche), u'Cr�che')
        self.AddPage(ResponsabilitesPanel(self, creche, inscrits), u'Responsabilit�s')
        self.AddPage(CafPanel(self, creche), 'C.A.F.')        
        self.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.OnPageChanged)

    def OnPageChanged(self, event):
        page = self.GetPage(event.GetSelection())
        page.UpdateContents()
        event.Skip()

    def UpdateContents(self):
        page = self.GetCurrentPage()
        page.UpdateContents()
     
class GeneralPanel(GPanel):
    def __init__(self, parent, creche, inscrits):
        GPanel.__init__(self, parent, u'Cr�che')
        self.notebook = GeneralNotebook(self, creche, inscrits)
	self.sizer.Add(self.notebook, 1, wx.EXPAND)
            
    def UpdateContents(self):
        self.notebook.UpdateContents()
