import sqlite3, os, time
from pathlib import Path

DB = Path(r"C:\T18\data\t18.db")
DB.parent.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(DB)
cur = con.cursor()

cur.executescript('''
CREATE TABLE IF NOT EXISTS signals(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_utc TEXT,
  symbol TEXT,
  side TEXT,
  entry REAL,
  sl REAL,
  tp REAL,
  state TEXT
);
CREATE TABLE IF NOT EXISTS paper_orders(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  signal_id INTEGER,
  ts_utc TEXT,
  fill_price REAL,
  pnl REAL,
  state TEXT
);
CREATE TABLE IF NOT EXISTS kpi_daily(
  d TEXT PRIMARY KEY,
  realized_pl REAL,
  trades INT,
  win_pct REAL,
  max_dd REAL
);
''')

# Seed some rows if empty
if not cur.execute('select count(*) from signals').fetchone()[0]:
    cur.executemany(
        'insert into signals(ts_utc,symbol,side,entry,sl,tp,state) values(?,?,?,?,?,?,?)',
        [
            ('2025-09-21T10:00:00Z','NIFTY24SEP','BUY',  23000, 22950, 23100,'new'),
            ('2025-09-21T10:05:00Z','BANKNIFTY24SEP','SELL', 49500, 49600, 49300,'filled'),
            ('2025-09-21T10:12:00Z','RELIANCE','BUY',  2800,  2788,  2835, 'tp_hit'),
        ]
    )

if not cur.execute('select count(*) from paper_orders').fetchone()[0]:
    cur.executemany(
        'insert into paper_orders(signal_id,ts_utc,fill_price,pnl,state) values(?,?,?,?,?)',
        [
            (2,'2025-09-21T10:05:07Z',49490, +800, 'filled'),
            (3,'2025-09-21T10:12:09Z',2835, +350, 'tp_hit'),
        ]
    )

if not cur.execute('select count(*) from kpi_daily').fetchone()[0]:
    cur.execute('insert into kpi_daily(d,realized_pl,trades,win_pct,max_dd) values(?,?,?,?,?)',
                ('2025-09-21', 1150, 2, 75.0, -300))

con.commit()
con.close()
print(f"OK -> seeded {DB}")
