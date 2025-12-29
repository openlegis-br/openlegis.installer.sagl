"""Inserir dados iniciais do sistema

Revision ID: 95b3df90d492
Revises: 
Create Date: 2025-12-25 12:45:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from pathlib import Path
import re
import os


# revision identifiers, used by Alembic.
revision = '95b3df90d492'
down_revision = None  # Primeira migration (ou ajuste se houver migrations anteriores)
branch_labels = None
depends_on = None


def load_initial_data_sql():
    """
    Carrega e processa o arquivo SQL de dados iniciais.
    Retorna lista de comandos INSERT para execução.
    """
    # Caminho do arquivo SQL relativo à raiz do projeto
    # migrations/versions/ -> migrations/ -> SAGL6/ -> src/openlegis.sagl/...
    current_file = Path(__file__)
    project_root = current_file.parent.parent.parent
    sql_file = project_root / 'src' / 'openlegis.sagl' / 'openlegis' / 'sagl' / 'instalacao' / 'db_initial_data.sql'
    
    if not sql_file.exists():
        # Tenta caminho alternativo
        sql_file = project_root / 'src/openlegis.sagl/openlegis/sagl/instalacao/db_initial_data.sql'
    
    if not sql_file.exists():
        raise FileNotFoundError(f"Arquivo SQL não encontrado: {sql_file}")
    
    with open(sql_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove comentários MySQL (otimizado para arquivos grandes)
    # Remove comentários de múltiplas linhas primeiro
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove comentários de linha única
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # Remove comentários que começam com --
        comment_pos = line.find('--')
        if comment_pos >= 0:
            line = line[:comment_pos]
        cleaned_lines.append(line)
    content = '\n'.join(cleaned_lines)
    
    # Remove comandos SET que não são necessários no Alembic (já gerencia transações)
    # Processa linha por linha para ser mais eficiente
    lines = content.split('\n')
    filtered_lines = []
    for line in lines:
        line_upper = line.upper().strip()
        # Pula linhas que são comandos SET desnecessários
        if (line_upper.startswith('SET FOREIGN_KEY_CHECKS') or
            line_upper.startswith('SET SQL_MODE') or
            line_upper.startswith('SET AUTOCOMMIT') or
            line_upper == 'START TRANSACTION' or
            line_upper.startswith('SET TIME_ZONE') or
            line_upper.startswith('SET @OLD_') or
            line_upper.startswith('SET NAMES') or
            line_upper.startswith('SET CHARACTER_SET') or
            line_upper == 'COMMIT'):
            continue
        filtered_lines.append(line)
    content = '\n'.join(filtered_lines)
    
    # Encontra todos os comandos INSERT (usa modo não-greedy para ser mais rápido)
    inserts = re.findall(r'INSERT\s+INTO[^;]+;', content, re.IGNORECASE | re.DOTALL)
    
    # Limpa os comandos (remove espaços em excesso, quebras de linha desnecessárias)
    cleaned_inserts = []
    for insert in inserts:
        insert = insert.strip()
        if insert:
            # Remove múltiplos espaços e quebras de linha dentro do comando
            insert = re.sub(r'\s+', ' ', insert)
            insert = insert.replace(' ;', ';')
            cleaned_inserts.append(insert)
    
    return cleaned_inserts


def get_tables_from_inserts(inserts):
    """
    Extrai nomes de tabelas dos comandos INSERT para uso no downgrade.
    """
    tables = set()
    for insert in inserts:
        match = re.search(r'INSERT INTO `?(\w+)`?', insert, re.IGNORECASE)
        if match:
            tables.add(match.group(1))
    return sorted(tables)


def adjust_insert_for_table(insert, table_name, connection, existing_columns=None):
    """
    Ajusta um comando INSERT removendo colunas que não existem na tabela.
    
    Args:
        insert: String com comando INSERT
        table_name: Nome da tabela
        connection: Conexão SQLAlchemy
        existing_columns: Set de colunas existentes (opcional, para evitar DESCRIBE repetido)
    
    Returns:
        String com INSERT ajustado ou None se não conseguir processar
    """
    try:
        # Extrai colunas e valores do INSERT
        match = re.match(
            r'INSERT\s+(?:IGNORE\s+)?INTO\s+`?(\w+)`?\s*\(([^)]+)\)\s*VALUES\s*(.+);',
            insert, re.IGNORECASE | re.DOTALL
        )
        if not match:
            return insert  # Não conseguiu parsear, retorna original
        
        table = match.group(1)
        columns_str = match.group(2)
        values_str = match.group(3)
        
        # Lista de colunas no SQL
        sql_columns = [col.strip().strip('`') for col in columns_str.split(',')]
        
        # Obtém colunas que realmente existem na tabela (se não foram passadas)
        if existing_columns is None:
            try:
                result = connection.execute(text(f"DESCRIBE `{table_name}`"))
                existing_columns = {row[0] for row in result}
            except Exception:
                # Se não conseguir obter colunas, retorna original (será tratado pelo INSERT IGNORE)
                return insert
        
        # Filtra colunas que existem
        valid_column_indices = []
        valid_columns = []
        for i, col in enumerate(sql_columns):
            if col in existing_columns:
                valid_column_indices.append(i)
                valid_columns.append(col)
        
        # Se nenhuma coluna válida, retorna None (pula este INSERT)
        if not valid_columns:
            return None
        
        # Se todas as colunas são válidas, retorna original
        if len(valid_columns) == len(sql_columns):
            return insert
        
        # Precisa ajustar os valores também
        # Parseia os valores (pode ter múltiplas linhas)
        # Remove espaços e quebras de linha
        values_str = values_str.strip()
        
        # Extrai cada tupla de valores (entre parênteses)
        value_tuples = re.findall(r'\(([^)]+)\)', values_str, re.DOTALL)
        
        if not value_tuples:
            return insert  # Não conseguiu parsear valores
        
        # Processa cada tupla, removendo valores das colunas que não existem
        adjusted_tuples = []
        for tuple_str in value_tuples:
            # Divide valores (respeitando strings entre aspas)
            values = []
            current = ''
            in_quotes = False
            quote_char = None
            
            for char in tuple_str:
                if char in ("'", '"') and (not current or current[-1] != '\\'):
                    if not in_quotes:
                        in_quotes = True
                        quote_char = char
                    elif char == quote_char:
                        in_quotes = False
                        quote_char = None
                    current += char
                elif char == ',' and not in_quotes:
                    values.append(current.strip())
                    current = ''
                else:
                    current += char
            
            if current.strip():
                values.append(current.strip())
            
            # Seleciona apenas valores das colunas válidas
            valid_values = [values[i] for i in valid_column_indices if i < len(values)]
            adjusted_tuples.append(f"({','.join(valid_values)})")
        
        # Reconstrói o INSERT
        columns_str_new = '(' + ','.join([f"`{col}`" for col in valid_columns]) + ')'
        values_str_new = ','.join(adjusted_tuples)
        
        # Preserva INSERT IGNORE se existir
        insert_prefix = "INSERT IGNORE INTO" if "IGNORE" in insert.upper() else "INSERT INTO"
        
        return f"{insert_prefix} `{table_name}` {columns_str_new} VALUES {values_str_new};"
        
    except Exception:
        # Em caso de erro, retorna original (será tratado pelo INSERT IGNORE)
        return insert


def upgrade() -> None:
    """
    Insere dados iniciais do sistema no banco de dados.
    Verifica se os dados já existem antes de inserir para evitar duplicação.
    
    Se a maioria dos dados já existir, marca a migration como concluída sem inserir nada.
    """
    # Importa logger
    import logging
    logger = logging.getLogger('alembic')
    
    try:
        logger.info("Inserindo dados iniciais do sistema...")
        
        # Verifica rapidamente se os dados já existem ANTES de carregar o arquivo SQL
        connection = op.get_bind()
        key_tables = ['cargo_bancada', 'cargo_comissao', 'tipo_materia_legislativa', 'status_tramitacao']
        tables_with_data = 0
        
        logger.debug(f"Verificando se dados já existem em {len(key_tables)} tabelas chave...")
        
        for table in key_tables:
            try:
                result = connection.execute(text(f"SELECT COUNT(*) FROM `{table}`"))
                count = result.scalar()
                if count > 0:
                    tables_with_data += 1
                    logger.debug(f"Tabela {table} já tem {count} registros")
            except Exception as e:
                # Tabela pode não existir, continua
                logger.debug(f"Erro ao verificar tabela {table}: {e}")
                pass
        
        # Se a maioria das tabelas já tem dados, assume que está completo
        if tables_with_data >= len(key_tables) * 0.5:  # 50% ou mais têm dados
            logger.info(f"Dados iniciais já existem ({tables_with_data}/{len(key_tables)} tabelas). Pulando inserção.")
            return
        
        # Carrega o arquivo SQL apenas se necessário
        logger.info(f"Carregando dados iniciais... ({tables_with_data}/{len(key_tables)} tabelas têm dados)")
        inserts = load_initial_data_sql()
        logger.info(f"Arquivo SQL carregado: {len(inserts)} INSERTs encontrados")
        
        if not inserts:
            logger.warning("Nenhum INSERT para executar")
            return
        
        logger.info(f"Inserindo dados iniciais. Total de INSERTs: {len(inserts)}")
        
        # Desabilita verificação de foreign keys temporariamente para inserção
        op.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        
        try:
            # Cache de colunas por tabela (evita múltiplos DESCRIBE)
            table_columns_cache = {}
            
            def get_table_columns(table_name, connection):
                """Obtém colunas de uma tabela usando cache"""
                if table_name not in table_columns_cache:
                    try:
                        result = connection.execute(text(f"DESCRIBE `{table_name}`"))
                        table_columns_cache[table_name] = {row[0] for row in result}
                    except Exception:
                        # Se não conseguir obter, retorna None
                        table_columns_cache[table_name] = None
                return table_columns_cache[table_name]
            
            # Executa cada comando INSERT com verificação de duplicação
            total_inserts = len(inserts)
            processed = 0
            for idx, insert in enumerate(inserts, 1):
                if not insert.strip():
                    continue
                
                # Log progresso a cada 10 INSERTs
                if idx % 10 == 0 or idx == total_inserts:
                    logger.debug(f"Processando INSERT {idx}/{total_inserts}...")
                
                # Extrai o nome da tabela do comando INSERT
                table_match = re.search(r'INSERT INTO `?(\w+)`?', insert, re.IGNORECASE)
                if not table_match:
                    # Se não conseguir identificar a tabela, usa INSERT IGNORE como segurança
                    insert_ignore = re.sub(r'INSERT INTO', 'INSERT IGNORE INTO', insert, flags=re.IGNORECASE)
                    op.execute(text(insert_ignore))
                    processed += 1
                    continue
                
                table_name = table_match.group(1)
                
                # Obtém colunas da tabela (com cache)
                existing_columns = get_table_columns(table_name, connection)
                
                # Se não conseguir obter colunas, usa INSERT IGNORE como segurança
                if existing_columns is None:
                    insert_ignore = re.sub(r'INSERT INTO', 'INSERT IGNORE INTO', insert, flags=re.IGNORECASE)
                    op.execute(text(insert_ignore))
                    processed += 1
                    continue
                
                # Ajusta o INSERT removendo colunas que não existem na tabela
                adjusted_insert = adjust_insert_for_table(insert, table_name, connection, existing_columns)
                
                if adjusted_insert is None:
                    # Nenhuma coluna válida, pula este INSERT
                    continue
                
                # Sempre usa INSERT IGNORE para evitar erros de duplicação
                # Isso é mais rápido que fazer COUNT(*) antes de cada INSERT
                # e é seguro mesmo se a tabela estiver vazia
                if "IGNORE" not in adjusted_insert.upper():
                    adjusted_insert = re.sub(r'INSERT INTO', 'INSERT IGNORE INTO', adjusted_insert, flags=re.IGNORECASE)
                
                op.execute(text(adjusted_insert))
                
                processed += 1
                
            logger.info(f"Dados iniciais inseridos: {processed} INSERTs processados")
            logger.debug("Finalizando inserção de dados...")
                    
        finally:
            # Reabilita verificação de foreign keys
            logger.debug("Reabilitando FOREIGN_KEY_CHECKS...")
            op.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            logger.debug("FOREIGN_KEY_CHECKS reabilitado")
        
        logger.info("Migration de dados iniciais concluída com sucesso")
        logger.info("Zope continuará inicializando. Servidores HTTP (porta 8080) e WebSocket (porta 8765) serão iniciados em breve...")
        # Função retorna implicitamente (Alembic gerencia transações)
            
    except FileNotFoundError as e:
        # Se o arquivo não existir, apenas loga um aviso mas não falha a migration
        logger.error(f"Arquivo SQL de dados iniciais não encontrado: {e}")
        logger.error("Migration continuará sem inserir dados iniciais")
        return
    except Exception as e:
        # Log erro completo
        logger.error(f"Erro durante inserção de dados iniciais: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Reabilita foreign keys mesmo em caso de erro
        try:
            op.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        except:
            pass
        # Re-raise para que o Alembic saiba que houve erro
        raise


def downgrade() -> None:
    """
    Remove os dados iniciais inseridos.
    
    ATENÇÃO: Esta função remove TODOS os dados das tabelas listadas.
    Use com cuidado em produção!
    """
    try:
        inserts = load_initial_data_sql()
        tables = get_tables_from_inserts(inserts)
        
        # Desabilita verificação de foreign keys temporariamente
        op.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        
        try:
            # Remove dados de cada tabela (DELETE para compatibilidade com transações)
            for table in tables:
                # Usa DELETE em vez de TRUNCATE para ser compatível com transações do Alembic
                op.execute(text(f"DELETE FROM `{table}`"))
        finally:
            # Reabilita verificação de foreign keys
            op.execute(text("SET FOREIGN_KEY_CHECKS=1"))
            
    except FileNotFoundError:
        # Se o arquivo não existir, não faz nada no downgrade
        pass
    except Exception as e:
        # Reabilita foreign keys mesmo em caso de erro
        try:
            op.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        except:
            pass
        raise
