import sqlite3

conn = sqlite3.connect('db.sqlite3')
c = conn.cursor()

c.execute('''
CREATE TABLE IF NOT EXISTS entradas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    imagem TEXT NOT NULL,
    data TEXT NOT NULL
)
''')

conn.commit()
conn.close()