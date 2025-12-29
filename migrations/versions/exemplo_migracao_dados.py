"""Exemplo de migração de dados entre bancos

Revision ID: exemplo_migracao_dados
Revises: 95b3df90d492 (migração MANUAL)
Create Date: 2025-01-XX XX:XX:XX.XXXXXX

Este é um exemplo de como migrar apenas os dados (registros) de um banco de dados
para outro usando Alembic, respeitando a estrutura do banco de destino.

⚠️ IMPORTANTE: 
- Esta é uma migração MANUAL - NÃO é aplicada automaticamente com 'alembic upgrade head'
- Deve ser executada explicitamente: 'alembic upgrade exemplo_migracao_dados'
- Ajuste as configurações de conexão (source_db_url e target_db_url) antes de usar
- Depende da migration 95b3df90d492 (dados iniciais) para evitar múltiplas heads
- O downgrade limpa os dados migrados, retornando o banco ao estado sem registros
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text, create_engine, inspect
from sqlalchemy.engine import Connection
from typing import Tuple
import logging
import pymysql

logger = logging.getLogger('alembic')

# revision identifiers, used by Alembic.
revision = 'exemplo_migracao_dados'
down_revision = '95b3df90d492'  # Depende da migration de dados iniciais para evitar múltiplas heads
branch_labels = None
depends_on = None


def get_table_columns(connection: Connection, table_name: str) -> set:
    """
    Obtém as colunas de uma tabela no banco de dados.
    
    Args:
        connection: Conexão SQLAlchemy
        table_name: Nome da tabela
    
    Returns:
        Set com nomes das colunas
    """
    inspector = inspect(connection)
    columns = inspector.get_columns(table_name)
    return {col['name'] for col in columns}


def check_table_has_data(connection: Connection, table_name: str) -> bool:
    """
    Verifica se uma tabela tem dados.
    
    Args:
        connection: Conexão SQLAlchemy
        table_name: Nome da tabela
    
    Returns:
        True se a tabela tem dados, False caso contrário
    """
    try:
        result = connection.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
        count = result.scalar()
        return count > 0
    except Exception:
        return False


def migrate_table_data(
    source_conn: Connection,
    target_conn: Connection,
    table_name: str,
    batch_size: int = 1000,
    clear_existing_data: bool = False
):
    """
    Migra dados de uma tabela do banco de origem para o banco de destino,
    respeitando apenas as colunas que existem no destino.
    
    Args:
        source_conn: Conexão com banco de origem
        target_conn: Conexão com banco de destino
        table_name: Nome da tabela
        batch_size: Tamanho do lote para inserção em batch
        clear_existing_data: Se True, limpa dados existentes antes de migrar
    """
    logger.info(f"Migrando dados da tabela: {table_name}")
    
    # Verifica se há dados existentes no destino
    has_existing_data = check_table_has_data(target_conn, table_name)
    if has_existing_data:
        if clear_existing_data:
            logger.warning(f"⚠️  Tabela {table_name} tem dados existentes. Limpando antes de migrar...")
            target_conn.execute(text(f"DELETE FROM `{table_name}`"))
            target_conn.commit()
        else:
            logger.warning(f"⚠️  ATENÇÃO: Tabela {table_name} já contém dados!")
            logger.warning(f"   A migração usará INSERT IGNORE para evitar duplicatas.")
            logger.warning(f"   Para limpar dados antes de migrar, defina clear_existing_data=True")
    
    # Obtém colunas do banco de destino (estrutura que será respeitada)
    target_columns = get_table_columns(target_conn, table_name)
    
    if not target_columns:
        logger.warning(f"Tabela {table_name} não existe no destino. Pulando...")
        return
    
    # Obtém colunas do banco de origem
    try:
        source_columns = get_table_columns(source_conn, table_name)
    except Exception as e:
        logger.warning(f"Tabela {table_name} não existe na origem: {e}. Pulando...")
        return
    
    # Intersecção: apenas colunas que existem em ambos os bancos
    common_columns = source_columns & target_columns
    
    if not common_columns:
        logger.warning(f"Nenhuma coluna comum entre origem e destino para {table_name}. Pulando...")
        return
    
    # Ordena colunas para garantir consistência
    common_columns_sorted = sorted(common_columns)
    columns_str = ', '.join([f"`{col}`" for col in common_columns_sorted])
    
    # Conta registros na origem
    count_result = source_conn.execute(text(f"SELECT COUNT(*) FROM `{table_name}`"))
    total_rows = count_result.scalar()
    
    if total_rows == 0:
        logger.info(f"Tabela {table_name} está vazia na origem. Nada para migrar.")
        return
    
    logger.info(f"Migrando {total_rows} registros de {table_name}...")
    
    # Desabilita foreign keys temporariamente no destino
    target_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    
    try:
        # Limpa dados existentes na tabela de destino (opcional - comente se não quiser)
        # target_conn.execute(text(f"DELETE FROM `{table_name}`"))
        
        # Migra dados em lotes
        offset = 0
        migrated = 0
        
        while offset < total_rows:
            # Seleciona lote de dados da origem
            # Usa colunas com nomes explícitos para evitar problemas
            columns_list = [f"`{col}`" for col in common_columns_sorted]
            query = f"SELECT {', '.join(columns_list)} FROM `{table_name}` LIMIT {batch_size} OFFSET {offset}"
            result = source_conn.execute(text(query))
            rows = result.fetchall()
            
            if not rows:
                break
            
            # Prepara valores para INSERT em batch
            # Constrói múltiplos VALUES para inserção em uma única query
            values_parts = []
            for row in rows:
                # Extrai valores na ordem das colunas
                # row pode ser tupla ou objeto Row do SQLAlchemy
                row_values = []
                for idx, col in enumerate(common_columns_sorted):
                    # Tenta acessar por nome primeiro, depois por índice
                    try:
                        if hasattr(row, col):
                            value = getattr(row, col)
                        elif hasattr(row, '__getitem__'):
                            # Tenta acessar como dicionário/Row primeiro
                            if hasattr(row, 'keys') and col in row.keys():
                                value = row[col]
                            elif hasattr(row, '_mapping') and col in row._mapping:
                                value = row._mapping[col]
                            else:
                                value = row[idx] if idx < len(row) else None
                        else:
                            value = row[idx] if idx < len(row) else None
                    except (KeyError, IndexError, AttributeError, TypeError):
                        # Se falhar, tenta por índice
                        try:
                            value = row[idx] if isinstance(row, (tuple, list)) and idx < len(row) else None
                        except:
                            value = None
                    
                    # Trata valores None e strings
                    if value is None:
                        row_values.append('NULL')
                    elif isinstance(value, str):
                        # Escapa aspas simples e quebras de linha
                        escaped_value = value.replace("'", "''").replace('\n', '\\n').replace('\r', '\\r')
                        row_values.append(f"'{escaped_value}'")
                    elif isinstance(value, bool):
                        # MySQL usa 0/1 para boolean
                        row_values.append('1' if value else '0')
                    elif isinstance(value, (int, float)):
                        row_values.append(str(value))
                    elif isinstance(value, bytes):
                        # Para dados binários, converte para hex
                        row_values.append(f"0x{value.hex()}")
                    else:
                        # Para outros tipos (datetime, date, etc), converte para string
                        escaped_value = str(value).replace("'", "''").replace('\n', '\\n').replace('\r', '\\r')
                        row_values.append(f"'{escaped_value}'")
                
                values_parts.append(f"({', '.join(row_values)})")
            
            # Executa INSERT IGNORE com múltiplos VALUES
            if values_parts:
                values_str = ', '.join(values_parts)
                insert_query = f"INSERT IGNORE INTO `{table_name}` ({columns_str}) VALUES {values_str}"
                
                # Usa driver pymysql diretamente desde o início para evitar interpretação de parâmetros pelo SQLAlchemy
                # Isso evita que padrões no texto (como 'PROCESSO', '00', etc) sejam interpretados como parâmetros
                try:
                    # Obtém a conexão raw do pymysql
                    raw_connection = target_conn.connection.dbapi_connection
                    if raw_connection and hasattr(raw_connection, 'cursor'):
                        # Usa cursor do pymysql diretamente (não passa pelo SQLAlchemy)
                        cursor = raw_connection.cursor()
                        try:
                            cursor.execute(insert_query)
                            raw_connection.commit()
                        finally:
                            cursor.close()
                    else:
                        # Fallback: tenta via SQLAlchemy (pode ter problemas com bind de parâmetros)
                        target_conn.execute(text(insert_query))
                        target_conn.commit()
                except Exception as e:
                    error_str = str(e)
                    # Se falhar, divide em lotes menores
                    logger.warning(f"Erro ao inserir lote completo ({len(values_parts)} registros). Dividindo em partes menores...")
                    chunk_size = 25  # Lotes menores
                    successful_chunks = 0
                    failed_chunks = 0
                    
                    for i in range(0, len(values_parts), chunk_size):
                        chunk = values_parts[i:i+chunk_size]
                        chunk_values_str = ', '.join(chunk)
                        chunk_query = f"INSERT IGNORE INTO `{table_name}` ({columns_str}) VALUES {chunk_values_str}"
                        
                        try:
                            # Usa driver pymysql diretamente para cada chunk
                            raw_connection = target_conn.connection.dbapi_connection
                            if raw_connection and hasattr(raw_connection, 'cursor'):
                                cursor = raw_connection.cursor()
                                try:
                                    cursor.execute(chunk_query)
                                    raw_connection.commit()
                                    successful_chunks += 1
                                finally:
                                    cursor.close()
                            else:
                                # Fallback: SQLAlchemy
                                target_conn.execute(text(chunk_query))
                                target_conn.commit()
                                successful_chunks += 1
                        except Exception as chunk_error:
                            failed_chunks += 1
                            logger.warning(f"Erro ao inserir lote {i//chunk_size + 1}: {chunk_error}")
                            # Continua com próximo lote
                            continue
                    
                    if successful_chunks > 0:
                        logger.info(f"Inseridos {successful_chunks} lotes de {(len(values_parts)-1)//chunk_size + 1} total ({failed_chunks} falharam)")
                    else:
                        # Se todos falharam, re-lança o erro original
                        raise e
                
                target_conn.commit()
            
            migrated += len(rows)
            offset += batch_size
            
            if migrated % (batch_size * 10) == 0:
                logger.info(f"Progresso: {migrated}/{total_rows} registros migrados...")
        
        logger.info(f"Migração de {table_name} concluída: {migrated} registros migrados")
        
    finally:
        # Reabilita foreign keys
        target_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        target_conn.commit()


def check_target_database_is_clean(
    target_conn: Connection,
    table_names: list,
    exclude_tables: list = None
) -> Tuple[bool, list]:
    """
    Verifica se o banco de destino está limpo (sem dados).
    
    IMPORTANTE: O banco de destino DEVE ter a estrutura de tabelas criada,
    mas NÃO deve conter registros (dados).
    
    Args:
        target_conn: Conexão com banco de destino
        table_names: Lista de tabelas para verificar
        exclude_tables: Lista de tabelas para excluir da verificação
    
    Returns:
        Tupla (is_clean, tables_with_data) onde:
        - is_clean: True se todas as tabelas estão vazias
        - tables_with_data: Lista de tabelas que contêm dados
    """
    exclude_tables = exclude_tables or []
    tables_with_data = []
    
    for table_name in table_names:
        if table_name in exclude_tables:
            continue
        if check_table_has_data(target_conn, table_name):
            tables_with_data.append(table_name)
    
    return len(tables_with_data) == 0, tables_with_data


def migrate_all_tables(
    source_db_url: str,
    target_db_url: str,
    table_names: list = None,
    exclude_tables: list = None,
    clear_existing_data: bool = False,
    require_clean_database: bool = True
):
    """
    Migra dados de múltiplas tabelas entre bancos de dados.
    
    Args:
        source_db_url: URL de conexão do banco de origem (ex: mysql+pymysql://user:pass@host/db)
        target_db_url: URL de conexão do banco de destino
        table_names: Lista de tabelas para migrar (None = todas)
        exclude_tables: Lista de tabelas para excluir da migração
        clear_existing_data: Se True, limpa dados existentes antes de migrar
        require_clean_database: Se True, exige que o banco de destino esteja limpo
    """
    # Testa conexões antes de continuar
    logger.info("Testando conexões com os bancos de dados...")
    
    try:
        # Ocultar senha nos logs (segurança)
        source_display = source_db_url.split('@')[1] if '@' in source_db_url else source_db_url
        logger.info(f"Testando conexão com banco de origem: {source_display}")
        source_engine = create_engine(source_db_url)
        with source_engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
        logger.info("✅ Conexão com banco de origem: OK")
    except Exception as e:
        error_msg = (
            f"\n{'=' * 60}\n"
            f"ERRO ao conectar ao banco de ORIGEM\n"
            f"{'=' * 60}\n"
            f"Erro: {e}\n\n"
            f"Verifique:\n"
            f"1. Credenciais (usuário/senha) estão corretas?\n"
            f"2. Host e porta estão corretos? (127.0.0.1:3306)\n"
            f"3. Banco de dados 'cmhortolandia' existe?\n"
            f"4. Usuário 'root' tem permissões de acesso?\n"
            f"5. MySQL está rodando? (sudo systemctl status mysql)\n"
            f"6. Firewall permite conexão na porta 3306?\n\n"
            f"Teste manualmente:\n"
            f"  mysql -u root -p -h 127.0.0.1 -P 3306 cmhortolandia\n\n"
            f"Se funcionar com 'localhost', tente usar 'localhost' ao invés de '127.0.0.1'\n"
            f"{'=' * 60}\n"
        )
        logger.error(error_msg)
        raise
    
    try:
        # Ocultar senha nos logs (segurança)
        target_display = target_db_url.split('@')[1] if '@' in target_db_url else target_db_url
        logger.info(f"Testando conexão com banco de destino: {target_display}")
        target_engine = create_engine(target_db_url)
        with target_engine.connect() as test_conn:
            test_conn.execute(text("SELECT 1"))
        logger.info("✅ Conexão com banco de destino: OK")
    except Exception as e:
        # Extrai informações da URL para diagnóstico
        import re
        url_match = re.search(r'mysql\+pymysql://([^:]+):([^@]+)@([^/]+)/([^?]+)', target_db_url)
        if url_match:
            user = url_match.group(1)
            host_port = url_match.group(3)
            db = url_match.group(4)
            host = host_port.split(':')[0] if ':' in host_port else host_port
            port = host_port.split(':')[1] if ':' in host_port else '3306'
        else:
            user = "?"
            host = "?"
            port = "?"
            db = "?"
        
        error_msg = (
            f"\n{'=' * 60}\n"
            f"ERRO ao conectar ao banco de DESTINO\n"
            f"{'=' * 60}\n"
            f"Erro: {e}\n\n"
            f"URL tentada: mysql+pymysql://{user}:***@{host}:{port}/{db}\n\n"
            f"DIAGNÓSTICO:\n"
            f"1. Teste manual com as MESMAS credenciais da URL acima:\n"
            f"   mysql -u {user} -p -h {host} -P {port} {db}\n"
            f"   (Use a senha que está configurada em target_db_url)\n\n"
            f"2. Se o teste manual funcionar, mas a migração não:\n"
            f"   - Verifique se a senha na URL está correta\n"
            f"   - Verifique se não há caracteres especiais na senha que precisam ser codificados\n"
            f"   - Tente usar 'localhost' ao invés de '127.0.0.1' (ou vice-versa)\n\n"
            f"3. Se estiver usando variáveis de ambiente (Opção 2):\n"
            f"   - Verifique: echo $MYSQL_HOST, $MYSQL_USER, $MYSQL_PASS, $MYSQL_DB\n"
            f"   - Considere usar Opção 1 (especificar manualmente)\n\n"
            f"4. SOLUÇÃO RÁPIDA: Use as mesmas credenciais que funcionam no teste manual\n"
            f"   Edite target_db_url com as credenciais que funcionam\n"
            f"{'=' * 60}\n"
        )
        logger.error(error_msg)
        raise
    
    exclude_tables = exclude_tables or []
    exclude_tables.extend([
        'alembic_version',  # Tabela de controle do Alembic
        'schema_migrations',  # Outras tabelas de controle
    ])
    
    with source_engine.connect() as source_conn, target_engine.connect() as target_conn:
        # Se não especificou tabelas, obtém todas do banco de destino
        if table_names is None:
            inspector = inspect(target_conn)
            table_names = inspector.get_table_names()
        
        # Filtra tabelas excluídas
        table_names = [t for t in table_names if t not in exclude_tables]
        
        # Verifica se o banco de destino está limpo
        # IMPORTANTE: O banco deve ter a estrutura (tabelas criadas), mas sem registros
        logger.info("Verificando se banco de destino está limpo (estrutura criada, sem registros)...")
        is_clean, tables_with_data = check_target_database_is_clean(
            target_conn, table_names, exclude_tables
        )
        
        if not is_clean:
            logger.warning("=" * 60)
            logger.warning("⚠️  ATENÇÃO: Banco de destino contém dados!")
            logger.warning("=" * 60)
            logger.warning(f"Tabelas com dados encontradas: {', '.join(tables_with_data)}")
            logger.warning("=" * 60)
            
            # Se clear_existing_data=True, limpa os dados automaticamente
            if clear_existing_data:
                logger.warning("")
                logger.warning("⚠️  Limpando dados existentes automaticamente...")
                logger.warning("   (clear_existing_data=True foi configurado)")
                logger.warning("")
                
                # Desabilita foreign key checks para permitir limpeza sem problemas de constraints
                logger.info("Desabilitando verificação de foreign keys para limpeza...")
                target_conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
                
                try:
                    for table_name in tables_with_data:
                        logger.info(f"Limpando tabela: {table_name}")
                        target_conn.execute(text(f"DELETE FROM `{table_name}`"))
                        target_conn.commit()
                    logger.info("✅ Dados existentes foram limpos. Continuando com a migração...")
                finally:
                    # Reabilita foreign key checks
                    logger.info("Reabilitando verificação de foreign keys...")
                    target_conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
                    target_conn.commit()
            # Se require_clean_database=True E clear_existing_data=False, exige banco limpo
            elif require_clean_database:
                error_msg = (
                    "ERRO: Banco de destino deve estar limpo (sem dados) para esta migração.\n"
                    "\n"
                    "REQUISITOS:\n"
                    "  ✅ Estrutura de tabelas deve estar criada (execute 'alembic upgrade head' primeiro)\n"
                    "  ❌ Banco NÃO deve conter registros (dados)\n"
                    "\n"
                    "Opções:\n"
                    "1. Limpe o banco de destino manualmente antes de executar a migração\n"
                    "2. Defina require_clean_database=False na função upgrade()\n"
                    "3. Defina clear_existing_data=True para limpar automaticamente"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            else:
                # Se ambos são False, continua com dados existentes
                logger.warning("Continuando com dados existentes (usando INSERT IGNORE)...")
        
        logger.info(f"Iniciando migração de {len(table_names)} tabelas...")
        
        for table_name in table_names:
            try:
                migrate_table_data(
                    source_conn, 
                    target_conn, 
                    table_name,
                    clear_existing_data=clear_existing_data
                )
            except Exception as e:
                logger.error(f"Erro ao migrar tabela {table_name}: {e}")
                # Continua com próxima tabela mesmo em caso de erro
                continue
        
        logger.info("Migração de dados concluída!")


def upgrade() -> None:
    """
    Migra dados do banco de origem para o banco de destino.
    
    ⚠️ MIGRAÇÃO MANUAL - Esta função NÃO é executada automaticamente.
    Para executar, use: alembic upgrade exemplo_migracao_dados
    
    CONFIGURAÇÃO NECESSÁRIA:
    1. Ajuste source_db_url com a URL do banco de origem
    2. Ajuste target_db_url com a URL do banco de destino
    3. Opcionalmente, especifique quais tabelas migrar em table_names
    4. Opcionalmente, especifique tabelas para excluir em exclude_tables
    """
    # ============================================
    # CONFIGURAÇÕES - AJUSTE AQUI
    # ============================================
    
    # URL do banco de origem (de onde os dados serão copiados)
    # Formato: mysql+pymysql://usuario:senha@host:porta/banco
    # Exemplo: mysql+pymysql://root:openlegis@127.0.0.1:3306/cmexemplo
    source_db_url = "mysql+pymysql://root:senha@127.0.0.1:3306/cmexemplo"
    
    # URL do banco de destino (para onde os dados serão copiados)
    # IMPORTANTE: Use as MESMAS credenciais que funcionam no teste manual
    # Se mysql -u root -p -h 127.0.0.1 funciona, use as mesmas credenciais aqui
    
    # Opção 1: Especificar manualmente (RECOMENDADO - mais confiável)
    # Use as MESMAS credenciais que funcionam no teste manual: mysql -u root -p -h 127.0.0.1
    target_db_url = "mysql+pymysql://root:senha@127.0.0.1:3306/openlegis"
    
    # Opção 2: Usar a conexão do Alembic (usa variáveis de ambiente MYSQL_*)
    # ATENÇÃO: Pode ter credenciais diferentes das variáveis de ambiente
    # NÃO descomente as linhas abaixo a menos que tenha certeza das credenciais
    # target_connection = op.get_bind()
    # target_db_url = str(target_connection.engine.url)
    
    # Log para confirmar qual URL está sendo usada (sem mostrar senha)
    logger.debug(f"URL de destino configurada: mysql+pymysql://***@{target_db_url.split('@')[1] if '@' in target_db_url else 'ERRO'}")
    
    # Lista de tabelas para migrar (None = todas)
    table_names = None  # Exemplo: ['tabela1', 'tabela2', 'tabela3']
    
    # Lista de tabelas para excluir
    exclude_tables = [
        # Adicione aqui tabelas que não devem ser migradas
        # 'tabela_logs',
        # 'tabela_sessao',
    ]
    
    # ============================================
    # CONFIGURAÇÕES DE SEGURANÇA
    # ============================================
    
    # IMPORTANTE: Esta migração requer que o banco de destino esteja LIMPO (sem dados)
    # Se require_clean_database=True, a migração falhará se encontrar dados existentes
    require_clean_database = True
    
    # Se clear_existing_data=True, limpa dados existentes antes de migrar
    # ATENÇÃO: Isso apagará todos os dados das tabelas antes de migrar!
    clear_existing_data = True
    
    # ============================================
    # VERIFICAÇÃO DE EXECUÇÃO MANUAL
    # ============================================
    
    # Esta migração é MANUAL e requer confirmação explícita
    # Para executar, defina a variável de ambiente: export ALLOW_MANUAL_DATA_MIGRATION=1
    import os
    allow_manual = os.environ.get('ALLOW_MANUAL_DATA_MIGRATION', '0')
    
    if allow_manual != '1':
        # Se não tiver a variável, apenas pula silenciosamente (não quebra o processo)
        # Isso permite que o sistema continue iniciando sem problemas
        logger.info("=" * 60)
        logger.info("⚠️  MIGRAÇÃO MANUAL - PULANDO EXECUÇÃO AUTOMÁTICA")
        logger.info("=" * 60)
        logger.info("Esta migração de dados NÃO é executada automaticamente.")
        logger.info("Para executar manualmente, defina a variável de ambiente:")
        logger.info("")
        logger.info("  export ALLOW_MANUAL_DATA_MIGRATION=1")
        logger.info("  alembic upgrade exemplo_migracao_dados")
        logger.info("")
        logger.info("Ou execute diretamente:")
        logger.info("  ALLOW_MANUAL_DATA_MIGRATION=1 alembic upgrade exemplo_migracao_dados")
        logger.info("=" * 60)
        logger.info("Migration pulada. Sistema continuará inicializando normalmente.")
        return  # Retorna silenciosamente sem erro
    
    # ============================================
    # EXECUÇÃO DA MIGRAÇÃO
    # ============================================
    
    logger.info("=" * 60)
    logger.info("INICIANDO MIGRAÇÃO DE DADOS ENTRE BANCOS (MANUAL)")
    logger.info("=" * 60)
    # Ocultar senha na URL para logs (segurança)
    source_display = source_db_url.split('@')[1] if '@' in source_db_url else source_db_url
    target_display = target_db_url.split('@')[1] if '@' in target_db_url else target_db_url
    logger.info(f"Origem: mysql+pymysql://***@{source_display}")
    logger.info(f"Destino: mysql+pymysql://***@{target_display}")
    logger.info("=" * 60)
    logger.info("⚠️  REQUISITOS DO BANCO DE DESTINO:")
    logger.info("  ✅ Estrutura de tabelas criada (via migrations Alembic)")
    logger.info("  ❌ NÃO deve conter registros (dados)")
    logger.info("=" * 60)
    
    try:
        migrate_all_tables(
            source_db_url=source_db_url,
            target_db_url=target_db_url,
            table_names=table_names,
            exclude_tables=exclude_tables,
            clear_existing_data=clear_existing_data,
            require_clean_database=require_clean_database
        )
        logger.info("=" * 60)
        logger.info("MIGRAÇÃO CONCLUÍDA COM SUCESSO")
        logger.info("=" * 60)
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"ERRO DURANTE MIGRAÇÃO: {e}")
        logger.error("=" * 60)
        import traceback
        logger.error(traceback.format_exc())
        raise


def downgrade() -> None:
    """
    Reverte a migração removendo os dados migrados.
    
    ATENÇÃO: Esta função remove TODOS os dados das tabelas migradas.
    Use com cuidado em produção!
    """
    logger.warning("=" * 60)
    logger.warning("REVERTENDO MIGRAÇÃO DE DADOS")
    logger.warning("=" * 60)
    logger.warning("ATENÇÃO: Esta operação removerá dados das tabelas!")
    logger.warning("=" * 60)
    
    # Lista de tabelas que foram migradas (ajuste conforme necessário)
    table_names = []  # Exemplo: ['tabela1', 'tabela2', 'tabela3']
    
    if not table_names:
        logger.warning("Nenhuma tabela especificada para limpeza. Nada a fazer.")
        return
    
    connection = op.get_bind()
    
    # Desabilita foreign keys temporariamente
    connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
    
    try:
        for table_name in table_names:
            try:
                logger.info(f"Removendo dados da tabela: {table_name}")
                connection.execute(text(f"DELETE FROM `{table_name}`"))
                logger.info(f"Dados removidos de {table_name}")
            except Exception as e:
                logger.error(f"Erro ao remover dados de {table_name}: {e}")
                continue
    finally:
        # Reabilita foreign keys
        connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
        connection.commit()
    
    logger.info("Revertida migração de dados concluída")

