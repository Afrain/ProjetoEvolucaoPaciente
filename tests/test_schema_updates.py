from sqlalchemy import create_engine, inspect, text

from app.schema_updates import ensure_runtime_schema


def test_runtime_schema_updates_legacy_database_idempotently():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL, "
                "full_name VARCHAR(120) NOT NULL, hashed_password VARCHAR(255) NOT NULL, "
                "created_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE patients (id INTEGER PRIMARY KEY, name VARCHAR(140) NOT NULL, "
                "birth_date DATE, phone VARCHAR(30), health_info TEXT, "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE treatment_episodes (id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL, "
                "surgery_id INTEGER, started_on DATE NOT NULL, closed_on DATE, "
                "created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL)"
            )
        )

    ensure_runtime_schema(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, full_name, hashed_password, created_at) "
                "VALUES (1, 'fisio', 'Fisio', 'hash', CURRENT_TIMESTAMP)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO professional_profiles (user_id, cpf_cnpj, created_at, updated_at) "
                "VALUES (1, '12.345.678/0001-90', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    ensure_runtime_schema(engine)

    inspector = inspect(engine)
    patient_columns = {item["name"] for item in inspector.get_columns("patients")}
    episode_columns = {item["name"] for item in inspector.get_columns("treatment_episodes")}
    assert {"cpf", "rg", "address", "email", "legal_guardian_name"} <= patient_columns
    assert {
        "service_type",
        "session_value",
        "payment_condition",
        "installment_count",
        "installment_due_dates",
    } <= episode_columns
    assert "professional_profiles" in inspector.get_table_names()
    with engine.connect() as connection:
        stored_document = connection.execute(
            text("SELECT cpf_cnpj FROM professional_profiles WHERE user_id = 1")
        ).scalar_one()
    assert stored_document == "12345678000190"


def test_sqlite_patient_rebuild_preserves_contract_email_and_existing_data():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE patients (id INTEGER PRIMARY KEY, name VARCHAR(140) NOT NULL, "
                "birth_date DATE NOT NULL, phone VARCHAR(30) NOT NULL, health_info TEXT NOT NULL, "
                "email VARCHAR(120), status VARCHAR(20), created_at DATETIME NOT NULL, "
                "updated_at DATETIME NOT NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO patients VALUES (1, 'Paciente legado', '1990-01-01', '11999999999', "
                "'Saúde', 'legado@example.com', 'Ativo', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )

    ensure_runtime_schema(engine)

    with engine.connect() as connection:
        row = connection.execute(text("SELECT name, email, phone FROM patients WHERE id = 1")).one()
    columns = {item["name"]: item for item in inspect(engine).get_columns("patients")}
    assert row == ("Paciente legado", "legado@example.com", "11999999999")
    assert columns["phone"]["nullable"] is True
    assert "status" not in columns
