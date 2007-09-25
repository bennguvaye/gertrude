##    This file is part of Gertrude.
##
##    Gertrude is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    Gertrude is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License
##    along with Gertrude; if not, write to the Free Software
##    Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

try:
    import sqlite3
except:
    from pysqlite2 import dbapi2 as sqlite3
from common import *
from sqlinterface import *

def Translate():
    cur = connection.cursor()
    try:
        cur.execute('SELECT value FROM DATA WHERE key="VERSION"')
        version = int(cur.fetchall()[0][0])
    except:
        version = 0

    print version, '=>', VERSION

    if version < 1:
        cur.execute("""
          CREATE TABLE DATA(
            key VARCHAR,
            value VARCHAR
          );""")
        
        cur.execute("""
          CREATE TABLE USERS(
            idx INTEGER PRIMARY KEY,
            login VARCHAR,
            password VARCHAR,
            profile INTEGER
          );""")

    if version < 2:
        cur.execute("ALTER TABLE CRECHE ADD server_url VARCHAR;")
        cur.execute('UPDATE CRECHE SET server_url=?', ("",))

    if version < 3:
        cur.execute("ALTER TABLE PRESENCES RENAME TO OLD;")
        cur.execute("""
          CREATE TABLE PRESENCES(
            idx INTEGER PRIMARY KEY,
            inscrit INTEGER REFERENCES INSCRITS(idx),
            date DATE,
            previsionnel INTEGER,
            value INTEGER,
            details VARCHAR
          );""")
        def encode_details(details):
            details = eval(details)
            if details is None:
                return None
            result = 0
            for i, v in enumerate(details):
                result += v << i
            return result
        cur.execute('SELECT inscrit, date, previsionnel, value, details FROM OLD')
        for inscrit, date, previsionnel, value, details in cur.fetchall():
            cur.execute('INSERT INTO PRESENCES (idx, inscrit, date, previsionnel, value, details) VALUES (NULL,?,?,?,?,?)', (inscrit, date, previsionnel, value, encode_details(details)))
        cur.execute('DROP TABLE OLD')

    if version < 4:
        cur.execute('SELECT details, idx FROM PRESENCES')
        for details, idx in cur.fetchall():
            if details is not None:
                details = eval(details) << 7
                cur.execute('UPDATE PRESENCES SET details=? WHERE idx=?', (details, idx))
        
    if version < 5:
        cur.execute("""
          CREATE TABLE CONGES(
            idx INTEGER PRIMARY KEY,
            debut VARCHAR,
            fin VARCHAR
          );""")

    if version < 6:
        cur.execute("ALTER TABLE CRECHE ADD mois_payes INTEGER;")
        cur.execute("ALTER TABLE CRECHE ADD presences_previsionnelles BOOLEAN;")
        cur.execute("ALTER TABLE CRECHE ADD modes_inscription INTEGER;")
        cur.execute('UPDATE CRECHE SET mois_payes=?', (12,))
        cur.execute('UPDATE CRECHE SET presences_previsionnelles=?', (True,))
        cur.execute('UPDATE CRECHE SET modes_inscription=?', (MODE_HALTE_GARDERIE+MODE_4_5+MODE_3_5,))

    if version < 7:
        cur.execute("ALTER TABLE INSCRITS ADD sexe INTEGER;")
        cur.execute('UPDATE INSCRITS SET sexe=?', (1,))
        
    if version < 8:
        cur.execute("""
          CREATE TABLE EMPLOYES(
            idx INTEGER PRIMARY KEY,
            date_embauche DATE,
            prenom VARCHAR,
            nom VARCHAR,
            telephone_domicile VARCHAR,
            telephone_domicile_notes VARCHAR,
            telephone_portable VARCHAR,
            telephone_portable_notes VARCHAR,
            email VARCHAR
        );""")            

    if version < VERSION:
        try:
            cur.execute("DELETE FROM DATA WHERE key=?", ("VERSION", ))
        except sqlite3.OperationalError:
            pass

        cur.execute("INSERT INTO DATA (key, value) VALUES (?, ?)", ("VERSION", VERSION))
        cur.execute("VACUUM")

        connection.commit()
