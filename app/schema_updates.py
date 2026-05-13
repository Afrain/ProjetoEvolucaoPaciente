from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name

    if "patients" in tables:
        _ensure_patient_schema(engine, dialect)
    if "attendances" in tables:
        _ensure_attendance_schema(engine, dialect)


def _ensure_patient_schema(engine: Engine, dialect: str) -> None:
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("patients")}

    if dialect == "sqlite":
        needs_rebuild = (
            "email" in columns
            or "location" not in columns
            or bool(columns.get("birth_date", {}).get("nullable") is False)
            or bool(columns.get("phone", {}).get("nullable") is False)
            or bool(columns.get("health_info", {}).get("nullable") is False)
        )
        if needs_rebuild:
            _rebuild_sqlite_patients(engine, columns)
        return

    with engine.begin() as connection:
        if "location" not in columns:
            connection.execute(
                text("ALTER TABLE patients ADD COLUMN location VARCHAR(20) NOT NULL DEFAULT 'Consultório'")
            )
        if "birth_date" in columns:
            connection.execute(text("ALTER TABLE patients ALTER COLUMN birth_date DROP NOT NULL"))
        if "phone" in columns:
            connection.execute(text("ALTER TABLE patients ALTER COLUMN phone DROP NOT NULL"))
        if "health_info" in columns:
            connection.execute(text("ALTER TABLE patients ALTER COLUMN health_info DROP NOT NULL"))
        if "email" in columns:
            connection.execute(text("ALTER TABLE patients DROP COLUMN email"))


def _rebuild_sqlite_patients(engine: Engine, columns: dict) -> None:
    location_value = "COALESCE(location, 'Consultório')" if "location" in columns else "'Consultório'"

    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
            """
            CREATE TABLE patients_new (
                id INTEGER NOT NULL,
                name VARCHAR(140) NOT NULL,
                birth_date DATE,
                phone VARCHAR(30),
                health_info TEXT,
                status VARCHAR(30) NOT NULL DEFAULT 'Em tratamento',
                location VARCHAR(20) NOT NULL DEFAULT 'Consultório',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id)
            )
            """
        )
        connection.exec_driver_sql(
            f"""
            INSERT INTO patients_new (
                id,
                name,
                birth_date,
                phone,
                health_info,
                status,
                location,
                created_at,
                updated_at
            )
            SELECT
                id,
                name,
                birth_date,
                phone,
                health_info,
                COALESCE(status, 'Em tratamento'),
                {location_value},
                created_at,
                updated_at
            FROM patients
            """
        )
        connection.exec_driver_sql("DROP TABLE patients")
        connection.exec_driver_sql("ALTER TABLE patients_new RENAME TO patients")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_patients_id ON patients (id)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_patients_name ON patients (name)")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_attendance_schema(engine: Engine, dialect: str) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("attendances")}
    if "surgeon_id" in columns:
        return

    with engine.begin() as connection:
        if dialect == "sqlite":
            connection.execute(text("ALTER TABLE attendances ADD COLUMN surgeon_id INTEGER REFERENCES surgeons(id)"))
        else:
            connection.execute(
                text("ALTER TABLE attendances ADD COLUMN surgeon_id INTEGER REFERENCES surgeons(id) ON DELETE SET NULL")
            )
