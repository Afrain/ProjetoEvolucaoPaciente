# Diagrama do Banco de Dados

Diagrama baseado nos modelos SQLAlchemy em `app/models`.

```mermaid
erDiagram
    PATIENTS ||--o{ ATTENDANCES : "possui"
    PATIENTS ||--o{ SURGERIES : "possui"
    PATIENTS ||--o{ TREATMENT_EPISODES : "possui"
    SURGERY_TYPES ||--o{ SURGERIES : "classifica"
    SURGEONS ||--o{ SURGERIES : "realiza"
    SURGEONS |o--o{ ATTENDANCES : "acompanha opcionalmente"
    SURGERIES |o--o| TREATMENT_EPISODES : "origina opcionalmente"
    TREATMENT_EPISODES |o--o{ ATTENDANCES : "agrupa opcionalmente"

    PATIENTS {
        int id PK
        string name
        date birth_date "nullable"
        string phone "nullable"
        text health_info "nullable"
        datetime created_at
        datetime updated_at
    }

    ATTENDANCES {
        int id PK
        int patient_id FK
        int treatment_episode_id FK "nullable, on delete set null"
        int surgeon_id FK "nullable, on delete set null"
        date attendance_date
        string location
        string status
        string treatment_type
        text evolution_notes
        datetime created_at
    }

    SURGERIES {
        int id PK
        int patient_id FK
        int surgery_type_id FK
        int surgeon_id FK
        date surgery_date
        int planned_attendances
        string status
        datetime created_at
    }

    SURGERY_TYPES {
        int id PK
        string name UK
        datetime created_at
    }

    SURGEONS {
        int id PK
        string name UK
        datetime created_at
    }

    TREATMENT_EPISODES {
        int id PK
        int patient_id FK
        int surgery_id FK "unique, nullable, on delete set null"
        date started_on
        date closed_on "nullable"
        datetime created_at
        datetime updated_at
    }

    USERS {
        int id PK
        string username UK
        string full_name
        string hashed_password
        datetime created_at
    }
```

## Relacionamentos

- `patients` tem muitos `attendances`, `surgeries` e `treatment_episodes`.
- `surgeries` pertence a um `patient`, um `surgery_type` e um `surgeon`.
- `treatment_episodes` pertence a um `patient` e pode estar vinculado a uma `surgery`.
- `attendances` pertence a um `patient` e pode estar vinculado a um `treatment_episode` e a um `surgeon`.
- `users` controla autenticação e nao se relaciona diretamente com as entidades clinicas.
