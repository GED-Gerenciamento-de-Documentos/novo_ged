-- Script de inicialização do PostgreSQL para o GED
-- Executado automaticamente pelo Docker na primeira inicialização

-- Criar schema para organização
CREATE SCHEMA IF NOT EXISTS ged;

-- Extensão para UUIDs
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Extensão para busca full-text em português
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- Conceder permissões ao usuário da aplicação
GRANT ALL PRIVILEGES ON SCHEMA ged TO root;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA ged TO root;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA ged TO root;
ALTER DEFAULT PRIVILEGES IN SCHEMA ged GRANT ALL ON TABLES TO root;
ALTER DEFAULT PRIVILEGES IN SCHEMA ged GRANT ALL ON SEQUENCES TO root;
