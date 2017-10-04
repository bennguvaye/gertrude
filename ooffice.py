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

import datetime
import time
import locale
import numbers
import sys
import os
import shutil
import types
import zipfile
import xml.dom.minidom
import re
import urllib
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import wx
import wx.lib.filebrowsebutton
import traceback
from functions import *
import subprocess

NumberTypes = (types.IntType, types.LongType, types.FloatType, types.ComplexType)


def GetNodeFromAttribute(nodes, attribute, value):
    pass


def GetText(value):
    if isinstance(value, basestring):
        return value
    elif isinstance(value, datetime.date):
        return '%.2d/%.2d/%.4d' % (value.day, value.month, value.year)
    else:
        return str(value)


def GetColumnName(index):
    if index < 26:
        return chr(65+index)
    else:
        return chr(64+(index / 26)) + chr(65+(index % 26))


def GetColumnIndex(name):
    if len(name) == 1:
        return ord(name) - 65
    elif len(name) == 2:
        return (ord(name[0]) - 64) * 26 + (ord(name[1]) - 65)    


def evalFields(fields):
    for i, field in enumerate(fields[:]):
        if len(field) == 2 or field[2] & (FIELD_EUROS | FIELD_HEURES):
            param, value = field[0:2]
            if isinstance(value, list):
                text = [GetText(v) for v in value]
                fields.append((param.upper(), value, [t.upper() for t in text]))
            else:
                text = GetText(value) 
                fields.append((param.upper(), value, text.upper()))
            fields[i] = (param, value, text)
        else:    
            fields.append((param.upper(), value, text.upper()))
    return fields


def GetValue(node):
    result = ""
    text_nodes = node.getElementsByTagName("text:p") + node.getElementsByTagName("text:a")
    for text_node in text_nodes:
        for child in text_node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                result += child.wholeText
    return result


def SetValue(node, value):
    if node.nodeName == "table:table-cell":
        node.setAttribute("office:value", str(value))
    text_nodes = node.getElementsByTagName("text:p") + node.getElementsByTagName("text:a")
    for text_node in text_nodes:
        for child in text_node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                child.replaceWholeText(str(value))
                break


def GetRepeat(node):
    if node.hasAttribute("table:number-columns-repeated"):
        return int(node.getAttribute("table:number-columns-repeated"))
    elif node.hasAttribute("table:number-rows-repeated"):
        return int(node.getAttribute("table:number-rows-repeated"))
    else:
        return 1


def GetRow(table, index):
    rows = table.getElementsByTagName("table:table-row")
    i = 0
    for row in rows:
        repeat = GetRepeat(row)
        i += repeat
        if i >= index:
            return row
    return None


def GetCellsCount(row):
    count = 0
    for child in row.childNodes:
        if child.nodeName in ("table:table-cell", "table:covered-table-cell"):
            count += GetRepeat(child)
    return count


def GetCell(row, index):
    i = 0
    for child in row.childNodes:
        if child.nodeName in ("table:table-cell", "table:covered-table-cell"):
            if i >= index:
                return child
            i += GetRepeat(child)
    return None


def GetValues(row):
    result = []
    cells = row.getElementsByTagName("table:table-cell")
    for cell in cells:
        # print cell.toprettyxml()
        # print GetRepeat(cell), GetValue(cell)
        result.extend([GetValue(cell)] * GetRepeat(cell))
    return result


def RemoveColumn(rows, index):
    for row in rows:
        cells = row.getElementsByTagName("table:table-cell")
        count = 0
        for cell in cells:
            repeat = GetRepeat(cell)
            count += repeat
            if count > index:
                if repeat == 1:
                    row.removeChild(cell)
                else:
                    cell.setAttribute("table:number-columns-repeated", str(repeat - 1))
                break    


def ReplaceTextFields(dom, _fields):
    fields = _fields[:]
    for i, field in enumerate(fields):
        if len(field) == 3 and field[1] is not None:
            if field[2] & FIELD_EUROS:
                v = field[1]
                if not isinstance(v, numbers.Real):
                    v = 0
                if field[2] & FIELD_SIGN:
                    fields[i] = (field[0], locale.format("%+.2f", v))
                else:
                    fields[i] = (field[0], locale.format("%.2f", v))
            elif field[2] & FIELD_HEURES:
                fields[i] = (field[0], GetHeureString(field[1]))

    evalFields(fields)
    # print dom.toprettyxml()
    # print fields

    nodes = dom.getElementsByTagName("text:a")
    for node in nodes:
        href = node.getAttribute("xlink:href")
        for field, value, text in fields:
            tag = '%%3C%s%%3E' % field
            if tag in href:
                if not isinstance(text, basestring):
                    text = str(text)
                node.setAttribute("xlink:href", text)
                break

    if dom.__class__ == xml.dom.minidom.Element and dom.nodeName in ["text:p", "text:h", "text:span"]:
        nodes = [dom] + dom.getElementsByTagName("text:span")
    else:
        nodes = dom.getElementsByTagName("text:p") + dom.getElementsByTagName("text:h") + dom.getElementsByTagName("text:span")

    for node in nodes:
        for child in node.childNodes:
            if child.nodeType == child.TEXT_NODE:
                try:
                    nodeText = child.wholeText
                    replace = False
                    for field, value, text in fields:
                        if isinstance(text, basestring) and callable(value):
                            start_tag, end_tag = '<%s(' % field, ')>'
                            if start_tag in nodeText and end_tag in nodeText:
                                if isinstance(text, list):
                                    print(child.toprettyxml())
                                else:
                                    tag = nodeText[nodeText.find(start_tag):nodeText.find(end_tag) + 2]
                                    parameters = tag[len(field) + 2:-2]
                                    try:
                                        replace = True
                                        nodeText = nodeText.replace(tag, eval("value(%s)" % parameters))
                                    except Exception as e:
                                        print('erreur :', tag, parameters, e)
                        else:
                            tag = '<%s>' % field
                            if tag in nodeText:
                                if isinstance(text, list):
                                    for t in text:
                                        duplicate = node.cloneNode(1)
                                        node.parentNode.insertBefore(duplicate, node)
                                        for c in duplicate.childNodes:
                                            if c.nodeType == child.TEXT_NODE:
                                                nt = c.wholeText.replace(tag, t)
                                                c.replaceWholeText(nt)
                                    node.parentNode.removeChild(node)
                                else:
                                    replace = True
                                    if not isinstance(text, basestring):
                                        text = str(text)
                                    nodeText = nodeText.replace(tag, text)
                        
                    if replace:
                        child.replaceWholeText(nodeText)
                except Exception as e:
                    print(e)


def ReplaceFields(cellules, _fields):
    fields = _fields[:]        
    evalFields(fields)
    
    # Si l'argument est une ligne ...
    if cellules is None:
        return
    elif cellules.__class__ in (xml.dom.minidom.Element, xml.dom.minidom.Document):
        if cellules.nodeName == "table:table-cell":
            cellules = [cellules]
        else:
            cellules = cellules.getElementsByTagName("table:table-cell")
    elif len(cellules) > 0 and cellules[0].nodeName != "table:table-cell":
        nodes = cellules
        cellules = []
        for node in nodes:
            cellules.extend(node.getElementsByTagName("table:table-cell"))

    result = False
    
    # Remplacement ...
    for cellule in cellules:
        formula = cellule.getAttribute("table:formula")
        if formula:
            for param, value, text in fields:
                tag = '<%s>' % param
                if tag in formula:
                    formula = formula.replace(tag, text)
            cellule.setAttribute("table:formula", formula)
        nodes = cellule.getElementsByTagName("text:p") + cellule.getElementsByTagName("text:h")
        for node in nodes:
            for child in node.childNodes:
                if child.nodeType == node.TEXT_NODE:
                    nodeText = child.wholeText
                    if '<' in nodeText and '>' in nodeText:
                        for field, value, text in fields:
                            if isinstance(text, basestring) and callable(value):
                                start_tag, end_tag = '<%s(' % field, ')>'
                                if start_tag in nodeText and end_tag in nodeText:
                                    if isinstance(text, list):
                                        print(child.toprettyxml())
                                    else:
                                        tag = nodeText[nodeText.find(start_tag):nodeText.find(end_tag) + 2]
                                        parameters = tag[len(field) + 2:-2]
                                        try:
                                            cellule.setAttribute("office:value-type", 'float')
                                            val = eval("value(%s)" % parameters)
                                            cellule.setAttribute("office:value", val)
                                            nodeText = nodeText.replace(tag, val)
                                        except Exception as e:
                                            print('erreur :', tag, parameters, e)
                            else:
                                tag = '<%s>' % field
                                if tag in nodeText:
                                    result = True
                                    if value is None:
                                        nodeText = nodeText.replace(tag, '')
                                    elif isinstance(value, int) or isinstance(value, float):
                                        if len(nodes) == 1 and nodeText == tag:
                                            cellule.setAttribute("office:value-type", 'float')
                                            cellule.setAttribute("office:value", str(value))
                                        nodeText = nodeText.replace(tag, text)
                                    elif isinstance(value, datetime.date):
                                        if len(nodes) == 1 and nodeText == tag:
                                            cellule.setAttribute("office:value-type", 'date')
                                            cellule.setAttribute("office:date-value", '%04d-%02d-%02d' % (value.year, value.month, value.day))
                                        nodeText = nodeText.replace(tag, text)
                                    else:
                                        nodeText = nodeText.replace(tag, text)

                                if '<' not in nodeText or '>' not in nodeText:
                                    break

                        # print child.wholeText, '=>', text
                        child.replaceWholeText(nodeText)
                        
    return result


def ReplaceFormulas(cellules, old, new):
    if cellules.__class__ == xml.dom.minidom.Element:
        cellules = cellules.getElementsByTagName("table:table-cell")
    for cellule in cellules:
        if cellule.hasAttribute("table:formula"):
            formula = cellule.getAttribute("table:formula")
            formula = formula.replace(old, new)
            cellule.setAttribute("table:formula", formula)

FLAG_SUM_MAX = 1


def IncrementFormulas(cellules, row=0, column=0, flags=0):
    if flags & FLAG_SUM_MAX:
        prefix = ":"
    else:
        prefix = ""
    formula_gure = re.compile("%s\.([A-Z]+)([0-9]+)" % prefix)
    if cellules.__class__ == xml.dom.minidom.Element:
        cellules = cellules.getElementsByTagName("table:table-cell")
    for cellule in cellules:
        if cellule.hasAttribute("table:formula"):
            formula = cellule.getAttribute("table:formula")
            mo = True
            while mo is not None:
                mo = formula_gure.search(formula)
                if mo:
                    formula = formula.replace(mo.group(0), "%s.___%s%d" % (prefix, GetColumnName(GetColumnIndex(mo.group(1))+column), int(mo.group(2))+row))
            formula = formula.replace('.___', '.')
            cellule.setAttribute("table:formula", formula)


def SetCellFormula(cell, formula):
    cell.setAttribute("table:formula", formula)


def SetCellFormulaReference(cell, table, other):    
    SetCellFormula(cell, "of:=['%s'.%s]" % (table.getAttribute("table:name"), other))


def HideLine(line):
    line.setAttribute("table:visibility", "collapse")


def getNamedShapes(dom):
    shapes = {}
    for tag in ("draw:line", "draw:frame", "draw:custom-shape"):
        nodes = dom.getElementsByTagName(tag)
        for node in nodes:
            name = node.getAttribute("draw:name")
            if name:
                shapes[name] = node
    return shapes


def GetDom(filename, part="content.xml"):
    zip = zipfile.ZipFile(filename, 'r')
    data = zip.read(part)
    dom = xml.dom.minidom.parseString(data)
    zip.close()
    return dom


def GetTables(filename):
    dom = GetDom(filename)
    spreadsheet = dom.getElementsByTagName('office:spreadsheet').item(0)
    return spreadsheet.getElementsByTagName("table:table")


def GetDimension(node, what):
    attribute = node.getAttribute(what)
    if attribute.endswith("cm"):
        return float(attribute[:-2])
    elif attribute.endswith("in"):
        return float(attribute[:-2])*2.54
    else:
        return 0


def SetDimension(node, what, value):
    node.setAttribute(what, "%.3scm" % value)


def ModifyLogo(dom, logo):
    bitmap = wx.Bitmap("templates/logo.png", wx.BITMAP_TYPE_PNG)
    for frame in dom.getElementsByTagName('draw:frame'):
        name = frame.getAttribute('draw:name')
        if name == "Logo":
            width = GetDimension(frame, "svg:width")
            height = GetDimension(frame, "svg:height")
            if width > 0 and height > 0:
                height = width * bitmap.Height / bitmap.Width
                SetDimension(frame, "svg:height", height)
                images = frame.getElementsByTagName('draw:image')
                if len(images) == 1:
                    images[0].setAttribute("xlink:href", logo)
                    return True
    return False


def AddLogo(dom, logo):
    manifests = dom.getElementsByTagName('manifest:manifest')
    for manifest in manifests:
        files = manifest.getElementsByTagName('manifest:file-entry')
        for file in files:
            if file.getAttribute("manifest:media-type") == "image/png":
                clone = file.cloneNode(1)
                clone.setAttribute("manifest:full-path", logo)
                manifest.insertBefore(clone, file)
                return

files_order = ["meta.xml", "content.xml"]


def GenerateOODocument(modifications, filename=None, gauge=None):
    if gauge:
        gauge.SetValue(0)
    if not filename:
        filename = normalize_filename(modifications.default_output)
    template = GetTemplateFile(modifications.template, modifications.site)
    errors = {}
    zip = zipfile.ZipFile(template, 'r')
    files = []
    if gauge:
        modifications.gauge = gauge
        gauge.SetValue(5)
    
    LOGO = "Pictures/logo.png"
    logo_inserted = False
    namelist = zip.namelist()
    
    index = 0
    for f in files_order:
        if f in namelist:
            namelist.remove(f)
            namelist.insert(index, f)
            index += 1
        
    for f in namelist:
        data = zip.read(f)
        if f.endswith(".xml") and len(data) > 0:
            dom = xml.dom.minidom.parseString(data)
            if IsTemplateFile("logo.png"):
                if f == 'content.xml':
                    logo_inserted = ModifyLogo(dom, LOGO)
                elif logo_inserted and f == 'META-INF/manifest.xml':
                    AddLogo(dom, LOGO)
                    files.append((LOGO, file("templates/logo.png", "rb").read()))
            new_errors = modifications.execute(f, dom)
            if new_errors:
                errors.update(new_errors)
            data = dom.toxml('UTF-8')
        files.append((f, data))  
            
    zip.close()
    zip = zipfile.ZipFile(filename, 'w')
    if gauge:
        gauge.SetValue(95)
    for f, data in files:
        zip.writestr(f, data)
    zip.close()
    if gauge:
        gauge.SetValue(100)
    return errors


def GenerateTextDocument(modifications, filename=None, gauge=None):
    if gauge:
        gauge.SetValue(0)
    if not filename:
        filename = normalize_filename(modifications.default_output)
    if modifications.template:
        template = GetTemplateFile(modifications.template)
        text = file(template, 'r').read()
    else:
        text = None
    if gauge:
        modifications.gauge = gauge
        gauge.SetValue(5)
        
    text, errors = modifications.execute(text)
    file(filename, 'w').write(text)
    if gauge:
        gauge.SetValue(100)
        
    return errors


def getOOoContext():
    import win32com.client
    objServiceManager = win32com.client.Dispatch("com.sun.star.ServiceManager")
    objServiceManager._FlagAsMethod("CreateInstance")
    objServiceManager._FlagAsMethod("Bridge_GetStruct")
    core_reflection = objServiceManager.CreateInstance("com.sun.star.reflection.CoreReflection")
    return objServiceManager.createInstance("com.sun.star.frame.Desktop"), objServiceManager, core_reflection


def MakePropertyValue(manager, Name, Value):
    struct = manager.Bridge_GetStruct("com.sun.star.beans.PropertyValue")
    struct.Name = Name
    struct.Value = Value
    return struct


def MakePropertyValues(manager, values):
    return [MakePropertyValue(manager, value[0], value[1]) for value in values]


def StartLibreOffice(filename):
    if sys.platform == 'win32':
        filename = ''.join(["file:", urllib.pathname2url(unicode(os.path.abspath(filename)).encode("latin-1"))])
        # print filename
        try:
            StarDesktop, objServiceManager, core_reflection = getOOoContext()
            document = StarDesktop.LoadComponentFromURL(filename, "_blank", 0,
                         MakePropertyValues(objServiceManager,
                           [["ReadOnly", False],
                           ["Hidden", False]]))
        except Exception as e:
            dlg = wx.MessageDialog(None, "Impossible d'ouvrir le document\n%r" % e, 'Erreur', wx.OK|wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
    else:
        paths = []
        if sys.platform == "darwin":
            paths.append("/Applications/LibreOffice.app/Contents/MacOS/soffice")
            paths.append("/Applications/OpenOffice.app/Contents/MacOS/soffice")
        else:
            paths.append("/usr/bin/libreoffice")
            paths.append("ooffice")
        for path in paths:
            try:
                print(path, filename)
                subprocess.Popen([path, filename])
                return
            except Exception as e:
                print(e)
                pass
        dlg = wx.MessageDialog(None, "Impossible de lancer OpenOffice / LibreOffice", 'Erreur', wx.OK|wx.ICON_WARNING)
        dlg.ShowModal()
        dlg.Destroy()


def save_current_document(filename):
    if sys.platform == 'win32':
        filename = ''.join(["file:", urllib.pathname2url(unicode(os.path.abspath(filename)).encode("latin-1"))])
        # print filename
        StarDesktop, objServiceManager, corereflection = getOOoContext()
        document = StarDesktop.CurrentComponent
        document.storeToUrl(filename, MakePropertyValues(objServiceManager, []))        
    return 1


def convert_to_pdf(filename, pdf_filename):
    # print filename, pdf_filename
    if filename.endswith("ods"):
        filter_name = "calc_pdf_Export"
    else:
        filter_name = "writer_pdf_Export"
    if sys.platform == 'win32':
        filename = ''.join(["file:", urllib.pathname2url(unicode(os.path.abspath(filename)).encode("utf8"))])
        pdf_filename = ''.join(["file:", urllib.pathname2url(unicode(os.path.abspath(pdf_filename)).encode("utf8"))])
        StarDesktop, objServiceManager, core_reflection = getOOoContext()
        document = StarDesktop.LoadComponentFromURL(
            filename,
            "_blank",
            0,
            MakePropertyValues(
                objServiceManager,
                [["ReadOnly", True],
                 ["Hidden", True]]))
        document.storeToUrl(
            pdf_filename,
            MakePropertyValues(
                objServiceManager,
                [["CompressMode", 1],
                 ["FilterName", filter_name]]))
        document.close(False)
    else:
        shutil.copy(filename, pdf_filename)

DDE_ACROBAT_STRINGS = ["AcroviewR15", "AcroviewA15", "AcroviewR12", "AcroviewA12", "AcroviewR11", "AcroviewA11", "AcroviewR10", "AcroviewA10", "acroview"]
dde_server = None


def StartAcrobatReader(filename):
    global dde_server
    import win32api
    import win32ui
    import dde
    
    filename = unicode(os.path.abspath(filename))
    path, name = os.path.split(filename)
    reader = win32api.FindExecutable(name, path)
    os.spawnl(os.P_NOWAIT, reader[1], " ")
    
    for t in range(10):
        time.sleep(1)
        for acrobat in DDE_ACROBAT_STRINGS:
            try:
                if not dde_server:
                    dde_server = dde.CreateServer()
                    dde_server.Create('Gertrude')
                c = dde.CreateConversation(dde_server)
                c.ConnectTo(acrobat, 'control')
                c.Exec('[DocOpen("%s")]' % (filename,))
                return
            except Exception as e:
                pass
        print("Impossible de lancer acrobat reader ; prochain essai dans 1s ...", e)

    dlg = wx.MessageDialog(None, "Impossible d'ouvrir le document", 'Erreur', wx.OK | wx.ICON_WARNING)
    dlg.ShowModal()
    dlg.Destroy()


def IsOODocument(filename):
    return filename and not (filename.endswith(".html") or filename.endswith(".txt") or filename.endswith(".xml"))


def GenerateDocument(modifications, filename, gauge=None):
    if IsOODocument(filename):
        return GenerateOODocument(modifications, filename, gauge)
    else:
        return GenerateTextDocument(modifications, filename, gauge)


def SendDocument(filename, generator, to=None, introduction_filename=None, saas=False):
    if to is None:
        to = generator.email_to
    if introduction_filename is None:
        introduction_filename = GetTemplateFile(generator.introduction_filename)
    COMMASPACE = ', '
    creche_emails = get_emails(creche.email)

    if not creche_emails:
        return False, "Vous devez renseigner l'adresse email de la structure"

    # Create the container (outer) email message.
    msg = MIMEMultipart()
    msg['Subject'] = generator.email_subject
    if saas:
        msg_from = "saas@gertrude-logiciel.org"
        msg["Reply-to"] = creche_emails[0]
        msg["Return-path"] = creche_emails[0]
    else:
        msg_from = creche_emails[0]
    msg['From'] = msg_from
    msg['To'] = COMMASPACE.join(to)
    msg['CC'] = COMMASPACE.join(creche_emails)

    try:
        with open(introduction_filename) as f:
            text = f.read()
            text = text.decode("utf-8")
            for field, _, value in evalFields(generator.GetIntroductionFields()):
                if isinstance(value, basestring):
                    text = text.replace("<%s>" % field, value)
            introduction = MIMEMultipart('alternative')
            html = "<html><head><meta charset='UTF-8'></head><body><p>" + text.replace("\n", "<br>") + "</p></body></html>"
            introduction.attach(MIMEText(text, 'plain', _charset='UTF-8'))
            introduction.attach(MIMEText(html, 'html', _charset='UTF-8'))
            msg.attach(introduction)
    except Exception as e:
        print("Exception", e)

    if filename:
        with open(filename, 'rb') as f:
            doc = MIMEBase('application', 'octet-stream')
            doc.set_payload(f.read())
            encoders.encode_base64(doc)
            doc.add_header('Content-Disposition', 'attachment', filename=os.path.split(filename)[1])
            msg.attach(doc)

    for attachment in generator.GetAttachments():
        with open(attachment, 'rb') as f:
            doc = MIMEBase('application', 'octet-stream')
            doc.set_payload(f.read())
            encoders.encode_base64(doc)
            doc.add_header('Content-Disposition', 'attachment', filename=os.path.split(attachment)[1])
            msg.attach(doc)

    if saas:
        smtp_server = "localhost"
    else:
        smtp_server = creche.smtp_server
    port = 25
    login = None
    try:
        if "/" in creche.smtp_server:
            smtp_server, login, password = smtp_server.split("/")
        if ":" in smtp_server:
            smtp_server, port = smtp_server.split(":")
            port = int(port)
    except:
        pass

    if config.debug:
        print("From: %s, To:" % msg_from, to + creche_emails)
        print(msg.as_string()[:1200], '...')
    else:
        s = smtplib.SMTP(smtp_server, port)
        if "gmail" in smtp_server:
            s.starttls()
        if login:
            s.login(login, password)
        s.sendmail(msg_from, to + creche_emails, msg.as_string())
        s.quit()


class DocumentDialog(wx.Dialog):
    def __init__(self, parent, modifications):
        self.modifications = modifications
        self.document_generated = False

        # Instead of calling wx.Dialog.__init__ we precreate the dialog
        # so we can set an extra style that must be set before
        # creation, and then we create the GUI object using the Create
        # method.
        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, -1, "Génération de document")

        # This next step is the most important, it turns this Python
        # object into the real wrapper of the dialog (instead of pre)
        # as far as the wxPython extension is concerned.
        self.PostCreate(pre)

        self.sizer = wx.BoxSizer(wx.VERTICAL)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(wx.StaticText(self, -1, "Format :"), 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        if not IsOODocument(modifications.template):
            self.format = wx.Choice(self, -1, choices=["Texte"])
        elif sys.platform == 'win32':
            self.format = wx.Choice(self, -1, choices=["LibreOffice", "PDF"])
        else:
            self.format = wx.Choice(self, -1, choices=["LibreOffice"])
        self.format.SetSelection(0)
        self.Bind(wx.EVT_CHOICE, self.onFormat, self.format)
        sizer.Add(self.format, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 5)
        default_output = normalize_filename(modifications.default_output)

        self.extension = os.path.splitext(default_output)[-1]
        wildcard = "OpenDocument (*%s)|*%s|PDF files (*.pdf)|*.pdf" % (self.extension, self.extension)
        self.fbb = wx.lib.filebrowsebutton.FileBrowseButton(self, -1,
                                                            size=(600, -1),
                                                            labelText="Nom de fichier :",
                                                            startDirectory=config.documents_directory,
                                                            initialValue=os.path.join(config.documents_directory, default_output),
                                                            fileMask=wildcard,
                                                            fileMode=wx.SAVE)
        sizer.Add(self.fbb, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.LEFT, 5)
        self.sizer.Add(sizer, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        self.gauge = wx.Gauge(self, -1, size=(-1,10))
        self.gauge.SetRange(100)
        self.sizer.Add(self.gauge, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.LEFT|wx.TOP, 5)
        
        line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
        self.sizer.Add(line, 0, wx.GROW | wx.ALIGN_CENTER_VERTICAL | wx.TOP | wx.BOTTOM, 5)
        
        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.sauver_ouvrir = wx.Button(self, -1, "Sauver et ouvrir")
        self.sauver_ouvrir.SetDefault()
        self.Bind(wx.EVT_BUTTON, self.OnSauverOuvrir, self.sauver_ouvrir)
        sizer.Add(self.sauver_ouvrir, 0, wx.LEFT | wx.RIGHT, 5)

        self.sauver = wx.Button(self, -1, "Sauver")
        self.Bind(wx.EVT_BUTTON, self.OnSauver, self.sauver)
        sizer.Add(self.sauver, 0, wx.RIGHT, 5)

        if modifications.multi:
            button = wx.Button(self, -1, "Sauver individuellement")
            self.Bind(wx.EVT_BUTTON, self.OnSauverUnitaire, button)
            sizer.Add(button, 0, wx.RIGHT, 5)

        if modifications.email:
            self.sauver_envoyer = wx.Button(self, -1, "Sauver et envoyer par email")
            self.Bind(wx.EVT_BUTTON, self.OnSauverEnvoyer, self.sauver_envoyer)
            sizer.Add(self.sauver_envoyer, 0, wx.RIGHT, 5)
            if modifications.multi is False and not modifications.email_to:
                self.sauver_envoyer.Disable()
                
            if creche.caf_email:
                self.sauver_envoyer = wx.Button(self, -1, "Sauver et envoyer par email à la CAF")
                self.Bind(wx.EVT_BUTTON, self.OnSauverEnvoyerCAF, self.sauver_envoyer)
                sizer.Add(self.sauver_envoyer, 0, wx.LEFT | wx.RIGHT, 5)

        #btnsizer.Add(self.ok)
        btn = wx.Button(self, wx.ID_CANCEL)
        sizer.Add(btn, 0, wx.RIGHT, 5)
        self.sizer.Add(sizer, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)

        self.SetSizer(self.sizer)
        self.sizer.Fit(self)
        self.CenterOnScreen()
    
    def onFormat(self, _):
        filename = os.path.splitext(self.fbb.GetValue())[0]
        if self.format.GetSelection() == 0:
            self.fbb.SetValue(filename + self.extension, None)
        else:
            self.fbb.SetValue(filename + ".pdf", None)
            
    def Sauver(self):
        self.fbb.Disable()
        self.sauver.Disable()
        if self.sauver_ouvrir:
            self.sauver_ouvrir.Disable()
        self.filename = self.fbb.GetValue()
        f, e = os.path.splitext(self.filename)
        if e == ".pdf":
            self.pdf = True
            self.oo_filename = f + self.extension
        else:
            self.pdf = False
            self.oo_filename = self.filename
            
        config.documents_directory = os.path.dirname(self.filename)
        dlg = None
        try:
            if self.modifications.multi is not False:
                errors = {}
                simple_modifications = self.modifications.GetSimpleModifications(self.oo_filename)
                for i, (filename, modifs) in enumerate(simple_modifications):
                    self.gauge.SetValue((100 * i) / len(simple_modifications))
                    errors.update(GenerateDocument(modifs, filename=filename))
                    if self.pdf:
                        f, e = os.path.splitext(filename)
                        convert_to_pdf(filename, f+".pdf")
                        os.remove(filename)
            else:
                self.filename = self.filename.replace(" <prenom> <nom>", "")
                self.oo_filename = self.oo_filename.replace(" <prenom> <nom>", "")
                errors = GenerateDocument(self.modifications, filename=self.oo_filename, gauge=self.gauge)
                if self.pdf:
                    convert_to_pdf(self.oo_filename, self.filename)
                    os.remove(self.oo_filename)
            self.document_generated = True
            if errors:
                message = "Document %s généré avec des erreurs :\n" % self.filename
                for label in errors.keys():
                    message += '\n' + label + ' :\n  '
                    message += '\n  '.join(errors[label])
                dlg = wx.MessageDialog(self, message, 'Message', wx.OK | wx.ICON_WARNING)
        except IOError:
            print(sys.exc_info())
            dlg = wx.MessageDialog(self, "Impossible de sauver le document. Peut-être est-il déjà ouvert ?", 'Erreur', wx.OK | wx.ICON_WARNING)
            dlg.ShowModal()
            dlg.Destroy()
            return
        except Exception as e:
            info = sys.exc_info()
            message = ' [type: %s value: %s traceback: %s]' % (info[0], info[1], traceback.extract_tb(info[2]))
            dlg = wx.MessageDialog(self, message, 'Erreur', wx.OK | wx.ICON_WARNING)
        if dlg:
            dlg.ShowModal()
            dlg.Destroy()
        self.EndModal(wx.ID_OK)

    def OnSauver(self, _):
        self.modifications.multi = False
        self.Sauver()

    def OnSauverOuvrir(self, event):
        self.OnSauver(event)
        if self.document_generated:
            if self.filename.endswith("pdf"):
                StartAcrobatReader(self.filename)
            else:
                StartLibreOffice(self.filename)
                
    def OnSauverUnitaire(self, _):
        self.Sauver()

    def OnSauverEnvoyer(self, event):
        self.OnSauverUnitaire(event)
        if self.document_generated:
            if self.modifications.multi is not False:
                simple_modifications = self.modifications.GetSimpleModifications(self.oo_filename)
                emails = '\n'.join([" - %s (%s)" % (modifs.email_subject, ", ".join(modifs.email_to)) for filename, modifs in simple_modifications])
                if len(emails) > 1000:
                    emails = emails[:1000] + "\n..."
                dlg = wx.MessageDialog(self, "Ces emails seront envoyés :\n" + emails, 'Confirmation', wx.OK | wx.CANCEL | wx.ICON_WARNING)
                response = dlg.ShowModal()
                dlg.Destroy()
                if response != wx.ID_OK:
                    return
                
                for filename, modifs in simple_modifications:
                    if self.pdf:
                        oo_filename = filename
                        filename, e = os.path.splitext(oo_filename)
                        filename += ".pdf"
                    try:
                        SendDocument(filename, modifs)
                    except Exception as e:
                        dlg = wx.MessageDialog(self, "Impossible d'envoyer le document %s\n%r" % (filename, e), 'Erreur', wx.OK | wx.ICON_WARNING)
                        dlg.ShowModal()
                        dlg.Destroy()
            else:
                try:
                    SendDocument(self.filename, self.modifications)
                except Exception as e:
                    dlg = wx.MessageDialog(self, "Impossible d'envoyer le document %s\n%r" % (self.filename, e), 'Erreur', wx.OK | wx.ICON_WARNING)
                    dlg.ShowModal()
                    dlg.Destroy()

    def OnSauverEnvoyerCAF(self, event):
        self.OnSauver(event)
        if self.document_generated:
            try:
                root, ext = os.path.splitext(self.modifications.introduction_filename)
                introduction_filename = root + " CAF" + ext
                SendDocument(self.filename, to=[creche.caf_email], introduction_filename=GetTemplateFile(introduction_filename))
            except Exception as e:
                dlg = wx.MessageDialog(self, "Impossible d'envoyer le document %s\n%r" % (self.filename, e), 'Erreur', wx.OK | wx.ICON_WARNING)
                dlg.ShowModal()
                dlg.Destroy()
