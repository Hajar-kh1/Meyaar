from sqlalchemy import text
from src.api.auth import database_engine

engine = database_engine()
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema='public'
          AND table_name='app_users'
        ORDER BY ordinal_position
    """)).fetchall()

for r in rows:
    print(r[0])
