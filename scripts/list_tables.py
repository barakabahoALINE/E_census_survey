import sqlite3
conn=sqlite3.connect('db.sqlite3')
c=conn.cursor()
c.execute("SELECT name FROM sqlite_master WHERE type='table'")
print('\n'.join(r[0] for r in c.fetchall()))
conn.close()
