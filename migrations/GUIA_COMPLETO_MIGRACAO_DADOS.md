# Guia Completo: Migração de Dados entre Bancos com Alembic

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Requisitos](#requisitos)
3. [Configuração](#configuração)
4. [Execução Passo a Passo](#execução-passo-a-passo)
5. [Troubleshooting](#troubleshooting)
6. [Referências](#referências)

---

## Visão Geral

Esta migração permite migrar **apenas os dados (registros)** de um banco de dados para outro usando Alembic, respeitando a estrutura do banco de destino.

### Características

- ✅ Migra apenas dados (registros), não estrutura
- ✅ Respeita a estrutura do banco de destino
- ✅ Ignora colunas que não existem no destino
- ✅ Usa `INSERT IGNORE` para evitar duplicatas
- ✅ Migra em lotes (batch) para melhor performance
- ✅ **Migração MANUAL** - não executa automaticamente
- ✅ Requer confirmação explícita via variável de ambiente

### Como Funciona

1. **Conecta aos dois bancos**: origem (de onde copia) e destino (para onde copia)
2. **Compara estruturas**: identifica quais colunas existem em ambos os bancos
3. **Migra apenas colunas comuns**: copia dados apenas das colunas que existem no destino
4. **Respeita estrutura do destino**: não tenta inserir dados em colunas que não existem

---

## Requisitos

### Banco de Destino

O banco de destino **DEVE** ter:
- ✅ **Estrutura criada** (tabelas, colunas, índices - via migrations Alembic)
- ❌ **SEM registros** (dados) - banco deve estar vazio

**Resumindo:**
- ✅ Estrutura (tabelas) = SIM
- ❌ Dados (registros) = NÃO

### Pré-requisitos

1. **Banco de origem** com dados que você quer migrar
2. **Banco de destino** limpo (vazio) com estrutura criada
3. **Acesso** a ambos os bancos de dados
4. **Alembic** configurado no projeto

### Comportamento com Dados Existentes

Se o banco de destino contiver dados, a migração:
- Por padrão, **falhará com erro** (requer banco limpo)
- Pode ser configurada para **limpar dados automaticamente** antes de migrar
- Pode ser configurada para **continuar com dados existentes** (usando INSERT IGNORE)

---

## Configuração

### 1. Editar o Arquivo de Migração

Abra `migrations/versions/exemplo_migracao_dados.py` e configure:

#### 1.1. Banco de Origem

```python
# URL do banco de origem (de onde os dados serão copiados)
# Formato: mysql+pymysql://usuario:senha@host:porta/banco
source_db_url = "mysql+pymysql://root:openlegis@127.0.0.1:3306/cmhortolandia"
```

**Formato**: `mysql+pymysql://usuario:senha@host:porta/banco`

#### 1.2. Banco de Destino

```python
# URL do banco de destino (para onde os dados serão copiados)
# Opção 1: Usar a conexão do Alembic (recomendado - usa variáveis de ambiente)
target_connection = op.get_bind()
target_db_url = str(target_connection.engine.url)

# Opção 2: Especificar manualmente (descomente e ajuste se necessário)
# target_db_url = "mysql+pymysql://root:openlegis@127.0.0.1:3306/openlegis"
```

#### 1.3. Tabelas (Opcional)

```python
# Migrar apenas tabelas específicas (None = todas)
table_names = None  # Exemplo: ['tabela1', 'tabela2', 'tabela3']

# Tabelas para excluir da migração
exclude_tables = [
    'alembic_version',
    # Adicione outras tabelas que não devem ser migradas
]
```

#### 1.4. Configurações de Segurança

```python
# Requer que o banco de destino esteja limpo (padrão: True)
require_clean_database = True

# Se True, limpa dados existentes antes de migrar (CUIDADO!)
clear_existing_data = False
```

**Opções:**
- `require_clean_database=True` + `clear_existing_data=False`: Exige banco limpo (falha se houver dados)
- `require_clean_database=True` + `clear_existing_data=True`: Limpa automaticamente antes de migrar
- `require_clean_database=False` + `clear_existing_data=False`: Continua com dados existentes (INSERT IGNORE)

---

## Execução Passo a Passo

### Passo 1: Criar Banco de Destino

```bash
# Criar banco novo
mysql -u root -p -e "CREATE DATABASE banco_destino CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

### Passo 2: Configurar Variáveis de Ambiente

O Alembic neste projeto usa variáveis de ambiente:

```bash
export MYSQL_HOST="localhost"
export MYSQL_USER="root"
export MYSQL_PASS="openlegis"
export MYSQL_DB="banco_destino"
```

**Ou tudo de uma vez:**
```bash
export MYSQL_HOST="localhost" && \
export MYSQL_USER="root" && \
export MYSQL_PASS="openlegis" && \
export MYSQL_DB="banco_destino"
```

**Verificar configuração:**
```bash
echo "Host: $MYSQL_HOST"
echo "User: $MYSQL_USER"
echo "DB: $MYSQL_DB"
```

### Passo 3: Criar Estrutura (Tabelas Vazias)

Execute as migrations de estrutura ANTES de migrar os dados:

```bash
# Ativar ambiente virtual (se houver)
source bin/activate

# Aplicar todas as migrations de estrutura
bin/alembic upgrade head
```

Isso criará:
- ✅ Todas as tabelas
- ✅ Todas as colunas
- ✅ Índices e constraints
- ❌ **SEM dados** (registros) - banco fica vazio

### Passo 4: Verificar que Banco está Limpo

```bash
mysql -u root -p banco_destino
```

```sql
-- Verificar que tabelas existem (estrutura criada)
SHOW TABLES;

-- Verificar que estão vazias (sem registros)
SELECT COUNT(*) FROM nome_da_tabela;  -- Deve retornar 0
SELECT COUNT(*) FROM outra_tabela;    -- Deve retornar 0

EXIT;
```

**Se alguma tabela retornar COUNT > 0, o banco não está limpo!**

### Passo 5: Verificar Status da Migration

```bash
# Verificar status atual
bin/alembic current

# Ver histórico de migrations
bin/alembic history
```

### Passo 6: Executar Migração de Dados (MANUAL)

⚠️ **IMPORTANTE**: Esta é uma migração **MANUAL** e **NÃO é executada automaticamente** com `alembic upgrade head`.

**Se a migration já foi aplicada anteriormente**, você precisa fazer downgrade primeiro:

```bash
# 1. Verificar se já foi aplicada
bin/alembic current

# 2. Se mostrar "exemplo_migracao_dados", fazer downgrade primeiro
bin/alembic downgrade -1

# 3. Executar a migration
ALLOW_MANUAL_DATA_MIGRATION=1 bin/alembic upgrade exemplo_migracao_dados
```

**Se ainda não foi aplicada:**

```bash
# Definir variável de ambiente
export ALLOW_MANUAL_DATA_MIGRATION=1

# Executar migração manual
bin/alembic upgrade exemplo_migracao_dados
```

**Ou em uma única linha:**
```bash
ALLOW_MANUAL_DATA_MIGRATION=1 bin/alembic upgrade exemplo_migracao_dados
```

**Por que manual?**
- Previne execução acidental durante `alembic upgrade head`
- Requer confirmação explícita do administrador
- Garante que você está ciente de que está migrando dados entre bancos

### Passo 7: Verificar Resultado

```bash
mysql -u root -p banco_destino
```

```sql
-- Verificar quantidade de registros
SELECT COUNT(*) FROM nome_da_tabela;

-- Comparar com banco de origem
-- (conecte ao banco de origem e execute a mesma query)
```

---

## Troubleshooting

### Erro: "Migração manual requer confirmação explícita"

**Causa**: Tentou executar sem definir a variável de ambiente.

**Solução**:
```bash
export ALLOW_MANUAL_DATA_MIGRATION=1
bin/alembic upgrade exemplo_migracao_dados
```

### Erro: "Banco de destino deve estar limpo (sem dados)"

**Causa**: O banco de destino contém dados e `require_clean_database=True`.

**Soluções**:
1. Limpe o banco manualmente:
   ```sql
   SET FOREIGN_KEY_CHECKS=0;
   TRUNCATE TABLE tabela1;
   TRUNCATE TABLE tabela2;
   SET FOREIGN_KEY_CHECKS=1;
   ```
2. Configure `clear_existing_data=True` na migration (limpa automaticamente)

### Erro: "Access denied for user 'root'@'localhost'"

**Causa**: Problema de autenticação MySQL.

**Soluções**:

1. **Testar conexão manualmente:**
   ```bash
   # Teste 1: Com localhost
   mysql -u root -popenlegis -h localhost -e "SELECT 1;"
   
   # Teste 2: Com 127.0.0.1
   mysql -u root -popenlegis -h 127.0.0.1 -e "SELECT 1;"
   ```

2. **Se funcionar, use o mesmo host na URL de conexão**

3. **Corrigir permissões:**
   ```sql
   GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' IDENTIFIED BY 'openlegis' WITH GRANT OPTION;
   GRANT ALL PRIVILEGES ON *.* TO 'root'@'127.0.0.1' IDENTIFIED BY 'openlegis' WITH GRANT OPTION;
   FLUSH PRIVILEGES;
   ```

4. **Diferença entre localhost e 127.0.0.1:**
   - `localhost` usa socket Unix (mais rápido)
   - `127.0.0.1` usa TCP/IP
   - Tente ambos na URL de conexão

### Erro: "Table doesn't exist"

**Causa**: A estrutura não foi criada no banco de destino.

**Solução**:
```bash
# Aplique as migrations de estrutura primeiro
bin/alembic upgrade head
```

### Erro: "A value is required for bind parameter"

**Causa**: SQLAlchemy interpretando padrões no texto como parâmetros.

**Solução**: Já corrigido no código - usa driver pymysql diretamente. Se ainda ocorrer, a migration divide automaticamente em lotes menores.

### Erro: "Cannot delete or update a parent row: a foreign key constraint fails"

**Causa**: Tentando limpar dados com foreign keys ativas.

**Solução**: Já corrigido no código - desabilita foreign keys antes de limpar.

### Aviso: "Tabela já contém dados"

**Causa**: Banco de destino tem dados existentes.

**Solução**: 
- Configure `clear_existing_data=True` para limpar automaticamente
- Ou limpe manualmente antes de migrar

---

## Checklist Completo

- [ ] Editar `source_db_url` no arquivo de migração
- [ ] Criar banco de destino no MySQL
- [ ] Configurar variáveis de ambiente (`MYSQL_*`)
- [ ] Executar `bin/alembic upgrade head` (cria estrutura)
- [ ] Verificar que banco está vazio (sem dados)
- [ ] Verificar status: `bin/alembic current`
- [ ] Se migration já aplicada, fazer `bin/alembic downgrade -1`
- [ ] Executar migration manual: `ALLOW_MANUAL_DATA_MIGRATION=1 bin/alembic upgrade exemplo_migracao_dados`
- [ ] Verificar dados migrados

---

## Exemplo Completo

### Cenário: Migrar dados de `cmhortolandia` para `openlegis`

```bash
# 1. Criar banco de destino (se não existir)
mysql -u root -p -e "CREATE DATABASE openlegis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. Configurar variáveis de ambiente
export MYSQL_HOST="localhost"
export MYSQL_USER="root"
export MYSQL_PASS="openlegis"
export MYSQL_DB="openlegis"

# 3. Criar estrutura
bin/alembic upgrade head

# 4. Verificar status
bin/alembic current

# 5. Se migration já aplicada, fazer downgrade
bin/alembic downgrade -1

# 6. Executar migração de dados
ALLOW_MANUAL_DATA_MIGRATION=1 bin/alembic upgrade exemplo_migracao_dados

# 7. Verificar
mysql -u root -popenlegis openlegis -e "SELECT COUNT(*) FROM nome_tabela;"
```

---

## Reverter a Migração

Se precisar reverter (remover dados migrados):

```bash
bin/alembic downgrade -1
```

⚠️ **ATENÇÃO**: Isso removerá os dados das tabelas migradas, retornando o banco ao estado sem registros!

**Nota**: Esta migração depende da migration `95b3df90d492` (dados iniciais) para evitar múltiplas heads.

---

## Características Técnicas

### O que a migração faz:

- ✅ **Verifica se o banco de destino está limpo** antes de migrar
- ✅ **Falha por padrão** se encontrar dados existentes (segurança)
- ✅ Migra apenas dados (registros), não estrutura
- ✅ Respeita a estrutura do banco de destino
- ✅ Ignora colunas que não existem no destino
- ✅ Usa `INSERT IGNORE` para evitar duplicatas
- ✅ Migra em lotes (batch) para melhor performance
- ✅ Desabilita temporariamente foreign keys durante inserção
- ✅ Loga progresso detalhado
- ✅ Opção para limpar dados automaticamente antes de migrar
- ✅ Usa driver pymysql diretamente (evita problemas de bind de parâmetros)
- ✅ Divide automaticamente em lotes menores se necessário

### Limitações:

- ⚠️ **Requer que o banco de destino esteja LIMPO (sem dados)**
- ⚠️ Não migra estrutura de tabelas (CREATE TABLE)
- ⚠️ Não migra índices, triggers, stored procedures
- ⚠️ Não migra foreign keys (apenas dados)
- ⚠️ Requer que as tabelas já existam no destino (estrutura criada via outras migrations)

---

## Segurança

- ⚠️ **Sempre faça backup** antes de executar migrações
- ⚠️ **Teste em ambiente de desenvolvimento** primeiro
- ⚠️ **Revise as configurações** antes de executar
- ⚠️ O `downgrade()` remove dados - use com cuidado
- ⚠️ `clear_existing_data=True` apaga dados - use com cuidado

---

## Referências

- [Documentação Alembic](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Engine URLs](https://docs.sqlalchemy.org/en/14/core/engines.html#database-urls)
- [MySQL Access Denied Troubleshooting](https://dev.mysql.com/doc/refman/8.0/en/access-denied.html)

---

## Suporte

Se encontrar problemas:
1. Verifique os logs detalhados da migração
2. Consulte a seção [Troubleshooting](#troubleshooting)
3. Verifique se todas as configurações estão corretas
4. Teste conexões manualmente com MySQL

---

**Última atualização**: 2025-12-25




