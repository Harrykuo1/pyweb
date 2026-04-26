from sqlalchemy import inspect


def test_init_models_creates_users_table(db_engine):
    tables = inspect(db_engine).get_table_names()
    assert "users" in tables
