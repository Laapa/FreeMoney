from __future__ import annotations

from importlib import util
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.sqltypes import BigInteger

from app.models.user import User


def _load_revision_values(path: Path) -> tuple[str, str | None]:
    module_name = f"_alembic_{path.stem}"
    spec = util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load migration module: {path}")

    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.revision, module.down_revision


def test_user_telegram_id_column_uses_bigint() -> None:
    telegram_column = User.__table__.c.telegram_id
    assert isinstance(telegram_column.type, BigInteger)


def test_postgresql_query_does_not_render_integer_cast_for_telegram_id() -> None:
    stmt = select(User).where(User.telegram_id == 123456789012)
    compiled = str(stmt.compile(dialect=postgresql.dialect()))

    assert "::INTEGER" not in compiled


def test_alembic_revision_identifiers_fit_default_version_num_limit() -> None:
    migrations_dir = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    migration_files = sorted(migrations_dir.glob("*.py"))

    assert migration_files

    for migration_file in migration_files:
        revision, down_revision = _load_revision_values(migration_file)

        assert len(revision) <= 32
        if down_revision is not None:
            assert len(down_revision) <= 32
