import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password, verify_password
from app.migrate_sqlite import upgrade
from app.models import User, UserRole
from tests.conftest import _clear_database


def test_functional_tests_keep_real_bcrypt_with_lower_cost():
    hashed = hash_password("fixture-password")
    assert int(hashed.split("$")[2]) == 4
    assert verify_password("fixture-password", hashed)
    assert not verify_password("wrong-password", hashed)


def test_cleanup_resets_committed_data_and_sequences_without_touching_other_schema(
    db_engine, postgres_url
):
    peer = create_engine(postgres_url)
    try:
        with peer.begin() as connection:
            upgrade(connection)
            connection.execute(
                User.__table__.insert().values(username="peer", role=UserRole.ADMIN)
            )
        with db_engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        for _ in range(2):
            with db_engine.begin() as connection:
                identifier = connection.execute(
                    User.__table__.insert()
                    .values(username="fixture", role=UserRole.ADMIN)
                    .returning(User.id)
                ).scalar_one()
                assert identifier == 1
            with pytest.raises(IntegrityError), db_engine.begin() as connection:
                connection.execute(
                    User.__table__.insert().values(
                        username="fixture", role=UserRole.ADMIN
                    )
                )
            _clear_database(db_engine)
            with db_engine.connect() as connection:
                for table in inspect(connection).get_table_names():
                    if table != "alembic_version":
                        name = db_engine.dialect.identifier_preparer.quote(table)
                        assert (
                            connection.execute(
                                text(f"SELECT count(*) FROM {name}")
                            ).scalar_one()
                            == 0
                        )
                assert (
                    connection.execute(
                        text("SELECT version_num FROM alembic_version")
                    ).scalar_one()
                    == revision
                )
            with peer.connect() as connection:
                assert connection.execute(select(User.username)).scalar_one() == "peer"
    finally:
        peer.dispose()
