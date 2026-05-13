# FisioGestao

Sistema monolitico de gestao de pacientes para fisioterapeutas, feito com FastAPI, SQLAlchemy ORM e templates Jinja2. Usa SQLite por padrao no ambiente local e PostgreSQL quando `DATABASE_URL` estiver definida.

## Como executar

Crie um arquivo `.env` local com suas credenciais reais. Esse arquivo esta no `.gitignore` e nao deve ser enviado ao GitHub.

```env
SESSION_SECRET_KEY=gere-uma-chave-grande-com-pelo-menos-32-caracteres
DATABASE_URL=sqlite:///./fisio_pacientes.db
INITIAL_ADMIN_USERNAME=seu_usuario_admin
INITIAL_ADMIN_PASSWORD=sua_senha_forte
INITIAL_ADMIN_FULL_NAME=Nome do Administrador
```

```bash
pip install -r requirements.txt
python main.py
```

Acesse no navegador:

```text
http://127.0.0.1:8000
```

Na primeira execucao local, o SQLite cria automaticamente o arquivo `fisio_pacientes.db` e cadastra o primeiro administrador usando `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD` e `INITIAL_ADMIN_FULL_NAME`. Depois que ja existir algum usuario no banco, essas variaveis nao criam novos usuarios automaticamente.

## Render + PostgreSQL

No Render, configure a variavel de ambiente `DATABASE_URL` do Web Service com a Internal Database URL do PostgreSQL criado no Render. Sem essa variavel, a aplicacao usa o fallback local `sqlite:///./fisio_pacientes.db`, que nao persiste entre reinicios do servico.

Variaveis esperadas no Web Service:

```env
SESSION_SECRET_KEY=uma-chave-grande-com-pelo-menos-32-caracteres
DATABASE_URL=postgresql://usuario:senha@host:porta/banco
INITIAL_ADMIN_USERNAME=seu_usuario_admin
INITIAL_ADMIN_PASSWORD=sua_senha_forte
INITIAL_ADMIN_FULL_NAME=Nome do Administrador
```

## Estrutura

```text
app/
  auth.py              # Hash de senha, login/logout e dependencia de usuario autenticado
  database.py          # Engine SQLAlchemy, Base e sessao por request
  models/              # User, Patient e Attendance com relacionamentos ORM
  routes/              # Login, dashboard, pacientes e atendimentos
  schemas.py           # Validacao Pydantic dos formularios
  seed.py              # Criacao segura do primeiro admin via variaveis de ambiente
static/
  css/styles.css
  js/app.js
templates/
  auth/
  patients/
  attendances/
main.py
requirements.txt
```

## Funcionalidades

- Login com sessao assinada por cookie.
- Rotas protegidas por dependencia `get_current_user`.
- CRUD de pacientes.
- CRUD de atendimentos vinculados ao paciente.
- Dashboard com total de pacientes, pacientes ativos, total de atendimentos, ultima visita e busca local.
- Historico completo de evolucao por paciente.
