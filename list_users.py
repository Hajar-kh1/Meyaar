from sqlalchemy import text
from src.api.auth import database_engine

engine = database_engine()
with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT user_id, name, email, username, personal_email, role, must_change_password
        FROM public.app_users
        ORDER BY created_at
    """)).fetchall()

for r in rows:
    print(r)
