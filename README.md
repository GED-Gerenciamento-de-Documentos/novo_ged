# NOVO GED — Gerenciamento Eletrônico de Documentos

Documentação completa para digitalização, armazenamento e consulta de documentos institucionais, com integração ao sistema legado **Oracle 11g + NFS** e armazenamento em nuvem.

---

## 🏗️ Estrutura do Projeto

```text
NOVO-GED/
├── api/             # Backend FastAPI (PostgreSQL, Oracle, Redis)
├── frontend/        # Interface Web (React + TypeScript + Vite)
└── README.md        # Esta documentação principal
```

---

## 🚀 Guia de Setup Rápido (Pós-Clone)

Se você acabou de clonar este repositório, siga os passos abaixo para subir o ambiente completo via Docker.

### 1. Configurar Variáveis de Ambiente
Na pasta `api/`, crie o arquivo `.env` copiando o exemplo:

```bash
cd api
cp .env.example .env
# Edite o .env para configurar acessos ao Oracle, NFS e senhas de banco.
```

### 2. Subir a Infraestrutura (Docker)
Ainda dentro da pasta `api/`, execute:

```bash
# Sobe API, Banco de Dados e Cache
docker-compose up -d

# (Opcional) Sobe o pgAdmin para visualizar o banco de dados
docker-compose --profile dev up -d
```
> **pgAdmin:** [http://localhost:5050](http://localhost:5050)
> **Usuário:** `admin@ged.com` (após correção) | **Senha:** `pgadmin_password`

### 3. Iniciar o Frontend
Em uma nova janela do terminal, entre na pasta `frontend` e rode o servidor de desenvolvimento:

```bash
cd frontend
npm install
npm run dev
```
> **Acesse:** [http://localhost:5173](http://localhost:5173)

---

## 🗄️ Estrutura do Banco de Dados (PostgreSQL)

O sistema centraliza metadados no Postgres (schema `ged`). Abaixo as tabelas principais:

### 1. `ged.users` (Usuários)
Gerencia o controle de acesso (RBAC).
- `id`: UUID (Primary Key)
- `name`: Nome completo
- `email`: E-mail de login (Único)
- `role`: Papel (`ADMINISTRADOR`, `GESTOR`, `OPERADOR`)
- `is_active`: Controle de ativação/desativação

### 2. `ged.documents` (Documentos)
Metadados técnicos e de negócio.
- `id`: UUID (Primary Key)
- `title`: Título descritivo
- `document_type`: Ex: EXAME, LAUDO, PRONTUARIO
- `storage_path`: Localização física (NFS/Cloud)
- `file_format`: PDF, JPEG, JBIG2, etc.
- `owner_record_number`: Número do prontuário vinculado

### 3. `ged.audit_logs` (Auditoria)
Log de conformidade LGPD.
- `action`: VIEW, UPLOAD, DELETE, etc.
- `user_id`: ID do usuário responsável
- `timestamp`: Data e hora da operação
- `success`: Status da conclusão

---

## 🧰 Stack Tecnológica Principal

- **Backend:** Python + FastAPI + SQLAlchemy 2.0
- **Frontend:** React + TypeScript + Vite
- **Banco de Metadados:** PostgreSQL 16
- **Cache/Session:** Redis 7
- **Legado:** Oracle 11g (oracledb)
- **Conversão de Imagem:** jbig2dec + Pillow

---

## 🧪 Comandos Úteis de Diagnóstico

Caso precise testar a conexão com o Oracle ou caminhos de rede manualmente, a API dispõe de uma ferramenta de diagnóstico:

```bash
# Execute o teste de conexão Oracle diretamente (via terminal)
python api/test_oracle_api.py
```

---

## 🛡️ Conformidade e Segurança

- **Criptografia:** CPF e dados sensíveis são criptografados com AES-256-GCM.
- **RBAC:** Controle rígido de quem pode ver documentos confidenciais.
- **LGPD:** Trilhas de auditoria imutáveis para cada visualização de documento.

Para detalhes específicos sobre a estrutura do backend, consulte a arquitetura DDD dentro da pasta `api/src/`.
