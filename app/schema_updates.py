from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_runtime_schema(engine: Engine) -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    dialect = engine.dialect.name

    if "patients" in tables:
        _ensure_patient_schema(engine, dialect)
        _ensure_patient_contract_fields(engine)
    if "surgeries" in tables:
        _ensure_surgery_schema(engine, dialect)
    if "attendances" in tables:
        _ensure_attendance_schema(engine, dialect)
    if "surgeries" in tables and "treatment_episodes" in tables:
        _ensure_treatment_episode_schema(engine, dialect)
    if "treatment_episodes" in tables:
        _ensure_episode_contract_fields(engine)
    if "users" in tables:
        _ensure_professional_profile_table(engine, dialect)


def _ensure_patient_schema(engine: Engine, dialect: str) -> None:
    inspector = inspect(engine)
    columns = {column["name"]: column for column in inspector.get_columns("patients")}

    if dialect == "sqlite":
        needs_rebuild = (
            "status" in columns
            or "location" in columns
            or bool(columns.get("birth_date", {}).get("nullable") is False)
            or bool(columns.get("phone", {}).get("nullable") is False)
            or bool(columns.get("health_info", {}).get("nullable") is False)
        )
        if needs_rebuild:
            _rebuild_sqlite_patients(engine, set(columns))
        return

    with engine.begin() as connection:
        if "birth_date" in columns:
            connection.execute(text("ALTER TABLE patients ALTER COLUMN birth_date DROP NOT NULL"))
        if "phone" in columns:
            connection.execute(text("ALTER TABLE patients ALTER COLUMN phone DROP NOT NULL"))
        if "health_info" in columns:
            connection.execute(text("ALTER TABLE patients ALTER COLUMN health_info DROP NOT NULL"))
        if "status" in columns:
            connection.execute(text("ALTER TABLE patients DROP COLUMN status"))
        if "location" in columns:
            connection.execute(text("ALTER TABLE patients DROP COLUMN location"))


def _rebuild_sqlite_patients(engine: Engine, existing_columns: set[str]) -> None:
    optional_columns = [
        ("birth_date", "DATE"),
        ("phone", "VARCHAR(30)"),
        ("health_info", "TEXT"),
        ("cpf", "VARCHAR(14)"),
        ("rg", "VARCHAR(20)"),
        ("address", "VARCHAR(300)"),
        ("email", "VARCHAR(120)"),
        ("legal_guardian_name", "VARCHAR(140)"),
        ("legal_guardian_cpf", "VARCHAR(14)"),
        ("legal_guardian_relationship", "VARCHAR(60)"),
    ]
    column_definitions = ",\n                ".join(
        f"{name} {sql_type}" for name, sql_type in optional_columns
    )
    insert_columns = ["id", "name", *[name for name, _ in optional_columns], "created_at", "updated_at"]
    select_columns = [
        "id",
        "name",
        *[name if name in existing_columns else f"NULL AS {name}" for name, _ in optional_columns],
        "created_at",
        "updated_at",
    ]
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
            f"""
            CREATE TABLE patients_new (
                id INTEGER NOT NULL,
                name VARCHAR(140) NOT NULL,
                {column_definitions},
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                PRIMARY KEY (id)
            )
            """
        )
        connection.exec_driver_sql(
            f"INSERT INTO patients_new ({', '.join(insert_columns)}) "
            f"SELECT {', '.join(select_columns)} FROM patients"
        )
        connection.exec_driver_sql("DROP TABLE patients")
        connection.exec_driver_sql("ALTER TABLE patients_new RENAME TO patients")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_patients_id ON patients (id)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_patients_name ON patients (name)")
        connection.exec_driver_sql("CREATE UNIQUE INDEX IF NOT EXISTS ux_patients_cpf ON patients (cpf)")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_patient_contract_fields(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("patients")}
    contract_columns = [
        ("cpf", "VARCHAR(14)"),
        ("rg", "VARCHAR(20)"),
        ("address", "VARCHAR(300)"),
        ("email", "VARCHAR(120)"),
        ("legal_guardian_name", "VARCHAR(140)"),
        ("legal_guardian_cpf", "VARCHAR(14)"),
        ("legal_guardian_relationship", "VARCHAR(60)"),
    ]
    with engine.begin() as connection:
        for name, sql_type in contract_columns:
            if name not in columns:
                connection.execute(text(f"ALTER TABLE patients ADD COLUMN {name} {sql_type}"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ux_patients_cpf ON patients (cpf)"))


def _ensure_episode_contract_fields(engine: Engine) -> None:
    columns = {column["name"] for column in inspect(engine).get_columns("treatment_episodes")}
    contract_columns = [
        ("service_type", "VARCHAR(30)"),
        ("contracted_procedure", "TEXT"),
        ("session_value", "NUMERIC(10,2)"),
        ("package_value", "NUMERIC(10,2)"),
        ("payment_method", "VARCHAR(40)"),
        ("payment_condition", "VARCHAR(20)"),
        ("installment_count", "INTEGER"),
        ("installment_due_dates", "TEXT"),
    ]
    with engine.begin() as connection:
        for name, sql_type in contract_columns:
            if name not in columns:
                connection.execute(text(f"ALTER TABLE treatment_episodes ADD COLUMN {name} {sql_type}"))


def _ensure_professional_profile_table(engine: Engine, dialect: str) -> None:
    id_definition = "INTEGER PRIMARY KEY AUTOINCREMENT" if dialect == "sqlite" else "SERIAL PRIMARY KEY"
    with engine.begin() as connection:
        connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS professional_profiles (
                    id {id_definition},
                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    cpf_cnpj VARCHAR(14),
                    crefito VARCHAR(30),
                    professional_address VARCHAR(300),
                    professional_email VARCHAR(120),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_professional_profiles_user_id "
                "ON professional_profiles (user_id)"
            )
        )
        connection.execute(
            text(
                "UPDATE professional_profiles SET cpf_cnpj = "
                "REPLACE(REPLACE(REPLACE(REPLACE(cpf_cnpj, '.', ''), '-', ''), '/', ''), ' ', '') "
                "WHERE cpf_cnpj IS NOT NULL"
            )
        )


def _ensure_surgery_schema(engine: Engine, dialect: str) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("surgeries")}

    with engine.begin() as connection:
        if "planned_attendances" not in columns:
            connection.execute(text("ALTER TABLE surgeries ADD COLUMN planned_attendances INTEGER NOT NULL DEFAULT 10"))
        if "status" not in columns:
            connection.execute(text("ALTER TABLE surgeries ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'Em tratamento'"))
        else:
            connection.execute(text("UPDATE surgeries SET status = 'Em tratamento' WHERE status = 'Em progresso'"))


def _ensure_attendance_schema(engine: Engine, dialect: str) -> None:
    inspector = inspect(engine)
    raw_columns = inspector.get_columns("attendances")
    columns = {column["name"] for column in raw_columns}
    column_map = {column["name"]: column for column in raw_columns}

    if dialect == "sqlite":
        needs_rebuild = "duration_minutes" in columns
        if needs_rebuild:
            _rebuild_sqlite_attendances(engine)
            inspector = inspect(engine)
            columns = {column["name"] for column in inspector.get_columns("attendances")}

    with engine.begin() as connection:
        if "surgeon_id" not in columns and dialect == "sqlite":
            connection.execute(text("ALTER TABLE attendances ADD COLUMN surgeon_id INTEGER REFERENCES surgeons(id)"))
        elif "surgeon_id" not in columns:
            connection.execute(
                text("ALTER TABLE attendances ADD COLUMN surgeon_id INTEGER REFERENCES surgeons(id) ON DELETE SET NULL")
            )

        if "treatment_episode_id" not in columns and dialect == "sqlite":
            connection.execute(
                text("ALTER TABLE attendances ADD COLUMN treatment_episode_id INTEGER REFERENCES treatment_episodes(id)")
            )
        elif "treatment_episode_id" not in columns:
            connection.execute(
                text(
                    "ALTER TABLE attendances ADD COLUMN treatment_episode_id "
                    "INTEGER REFERENCES treatment_episodes(id) ON DELETE SET NULL"
                )
            )

        if "location" not in columns:
            connection.execute(text("ALTER TABLE attendances ADD COLUMN location VARCHAR(20) NOT NULL DEFAULT 'Consultorio'"))
        if "status" not in columns:
            connection.execute(text("ALTER TABLE attendances ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'Em andamento'"))

        # Older schemas still had this field. Keep migration conservative and nullable-safe.
        if "duration_minutes" in columns and dialect != "sqlite":
            connection.execute(text("ALTER TABLE attendances DROP COLUMN duration_minutes"))

        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_attendances_treatment_episode_id ON attendances (treatment_episode_id)")
        )


def _rebuild_sqlite_attendances(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.exec_driver_sql(
            """
            CREATE TABLE attendances_new (
                id INTEGER NOT NULL,
                patient_id INTEGER NOT NULL,
                surgeon_id INTEGER,
                attendance_date DATE NOT NULL,
                treatment_type VARCHAR(120) NOT NULL,
                evolution_notes TEXT NOT NULL,
                created_at DATETIME NOT NULL,
                treatment_episode_id INTEGER,
                location VARCHAR(20) NOT NULL DEFAULT 'Consultorio',
                status VARCHAR(20) NOT NULL DEFAULT 'Em andamento',
                PRIMARY KEY (id),
                FOREIGN KEY(patient_id) REFERENCES patients (id) ON DELETE CASCADE,
                FOREIGN KEY(surgeon_id) REFERENCES surgeons (id) ON DELETE SET NULL,
                FOREIGN KEY(treatment_episode_id) REFERENCES treatment_episodes (id) ON DELETE SET NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO attendances_new (
                id,
                patient_id,
                surgeon_id,
                attendance_date,
                treatment_type,
                evolution_notes,
                created_at,
                treatment_episode_id,
                location,
                status
            )
            SELECT
                id,
                patient_id,
                surgeon_id,
                attendance_date,
                treatment_type,
                evolution_notes,
                created_at,
                treatment_episode_id,
                COALESCE(location, 'Consultorio'),
                COALESCE(status, 'Em andamento')
            FROM attendances
            """
        )
        connection.exec_driver_sql("DROP TABLE attendances")
        connection.exec_driver_sql("ALTER TABLE attendances_new RENAME TO attendances")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendances_id ON attendances (id)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendances_attendance_date ON attendances (attendance_date)")
        connection.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_attendances_treatment_episode_id ON attendances (treatment_episode_id)")
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")


def _ensure_treatment_episode_schema(engine: Engine, dialect: str) -> None:
    inspector = inspect(engine)
    attendance_columns = (
        {column["name"] for column in inspector.get_columns("attendances")}
        if "attendances" in inspector.get_table_names()
        else set()
    )

    with engine.begin() as connection:
        if "treatment_episode_id" not in attendance_columns and dialect == "sqlite":
            connection.execute(
                text("ALTER TABLE attendances ADD COLUMN treatment_episode_id INTEGER REFERENCES treatment_episodes(id)")
            )
        elif "treatment_episode_id" not in attendance_columns:
            connection.execute(
                text(
                    "ALTER TABLE attendances ADD COLUMN treatment_episode_id "
                    "INTEGER REFERENCES treatment_episodes(id) ON DELETE SET NULL"
                )
            )

        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_treatment_episodes_patient_id ON treatment_episodes (patient_id)")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_treatment_episodes_surgery_id ON treatment_episodes (surgery_id)")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_attendances_treatment_episode_id ON attendances (treatment_episode_id)")
        )

        surgeries_without_episode = (
            connection.execute(
                text(
                    """
                    SELECT s.id AS surgery_id, s.patient_id AS patient_id, s.surgery_date AS started_on
                    FROM surgeries s
                    LEFT JOIN treatment_episodes e ON e.surgery_id = s.id
                    WHERE e.id IS NULL
                    """
                )
            )
            .mappings()
            .all()
        )
        for surgery in surgeries_without_episode:
            connection.execute(
                text(
                    """
                    INSERT INTO treatment_episodes (
                        patient_id,
                        surgery_id,
                        started_on,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :patient_id,
                        :surgery_id,
                        :started_on,
                        CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "patient_id": surgery["patient_id"],
                    "surgery_id": surgery["surgery_id"],
                    "started_on": surgery["started_on"],
                },
            )

        unlinked_attendances = (
            connection.execute(
                text(
                    """
                    SELECT id, patient_id, attendance_date
                    FROM attendances
                    WHERE treatment_episode_id IS NULL
                    """
                )
            )
            .mappings()
            .all()
        )
        for attendance in unlinked_attendances:
            episode = connection.execute(
                text(
                    """
                    SELECT e.id
                    FROM treatment_episodes e
                    WHERE e.patient_id = :patient_id
                      AND e.started_on <= :attendance_date
                    ORDER BY e.started_on DESC, e.id DESC
                    LIMIT 1
                    """
                ),
                {
                    "patient_id": attendance["patient_id"],
                    "attendance_date": attendance["attendance_date"],
                },
            ).first()

            if episode is None:
                episode = connection.execute(
                    text(
                        """
                        SELECT e.id
                        FROM treatment_episodes e
                        WHERE e.patient_id = :patient_id
                        ORDER BY e.started_on DESC, e.id DESC
                        LIMIT 1
                        """
                    ),
                    {"patient_id": attendance["patient_id"]},
                ).first()

            if episode is not None:
                connection.execute(
                    text("UPDATE attendances SET treatment_episode_id = :episode_id WHERE id = :attendance_id"),
                    {"episode_id": episode[0], "attendance_id": attendance["id"]},
                )
