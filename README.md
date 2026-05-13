# FisioGestão

Sistema monolítico de gestão de pacientes para fisioterapeutas, feito com FastAPI, SQLAlchemy ORM e templates Jinja2. Usa SQLite por padrão no ambiente local e PostgreSQL quando `DATABASE_URL` estiver definida.

## Como executar

Crie um arquivo `.env` local com suas credenciais reais. Esse arquivo está no `.gitignore` e não deve ser enviado ao GitHub.

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
http://127.0.0.1:8000/dashboard
```

Health check:

```text
http://127.0.0.1:8000
```

Na primeira execução local, o SQLite cria automaticamente o arquivo `fisio_pacientes.db` e cadastra o primeiro administrador usando `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD` e `INITIAL_ADMIN_FULL_NAME`. Depois que já existir algum usuário no banco, essas variáveis não criam novos usuários automaticamente.

## Render + PostgreSQL

No Render, configure a variável de ambiente `DATABASE_URL` do Web Service com a Internal Database URL do PostgreSQL criado no Render. Sem essa variável, a aplicação usa o fallback local `sqlite:///./fisio_pacientes.db`, que não persiste entre reinícios do serviço.

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
  auth.py              # Hash de senha, login/logout e dependência de usuário autenticado
  database.py          # Engine SQLAlchemy, Base e sessao por request
  models/              # User, Patient, Attendance e Surgery com relacionamentos ORM
  routes/              # Login, painel, pacientes, atendimentos e cirurgias
  schemas.py           # Validação Pydantic dos formulários
  seed.py              # Criação segura do primeiro admin via variáveis de ambiente
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

- Login com sessão assinada por cookie.
- Rotas protegidas por dependência `get_current_user`.
- CRUD de pacientes.
- CRUD de atendimentos vinculados ao paciente.
- CRUD de cirurgias vinculadas ao paciente.
- Painel com total de pacientes, pacientes ativos, atendimentos, cirurgias, última visita e busca local.
- Histórico completo de evolução por paciente.
