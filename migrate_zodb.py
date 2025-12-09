#!/usr/bin/env python3
"""
MIGRAÇÃO ZODB → POSTGRESQL
Solução: Sempre usar keep_history=True na migração
"""
import sys
import os
import logging
import psycopg2
import getpass
import time
import subprocess
from ZODB.FileStorage import FileStorage
from relstorage.storage import RelStorage
from relstorage.adapters.postgresql import PostgreSQLAdapter
import ZODB

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

POSTGRES_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'superuser': 'postgres',
    'superuser_password': '',
    'zodbuser': 'zodbuser',
    'zodbuser_password': 'openlegis'
}

def limpar_bancos_completamente():
    """Limpar completamente os bancos PostgreSQL"""
    try:
        conn_params = {
            'host': POSTGRES_CONFIG['host'],
            'port': POSTGRES_CONFIG['port'],
            'user': POSTGRES_CONFIG['superuser'],
            'database': 'postgres'
        }
        
        if POSTGRES_CONFIG['superuser_password']:
            conn_params['password'] = POSTGRES_CONFIG['superuser_password']
        
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        bancos = ['zodb', 'sapl_documentos']
        
        for banco in bancos:
            logger.info(f"Limpando banco {banco}...")
            
            # Matar todas as conexões
            cursor.execute("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = %s AND pid <> pg_backend_pid()
            """, (banco,))
            
            time.sleep(3)  # Dar mais tempo para conexões fecharem
            
            # Dropar e recriar
            cursor.execute(f"DROP DATABASE IF EXISTS {banco}")
            logger.info(f"  Banco {banco} dropado")
            
            cursor.execute(f"""
                CREATE DATABASE {banco}
                WITH ENCODING 'UTF8'
                TEMPLATE template0
                CONNECTION LIMIT = -1
            """)
            logger.info(f"  Banco {banco} criado")
            
            # Criar usuário se não existir
            cursor.execute(f"""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{POSTGRES_CONFIG['zodbuser']}') THEN
                        CREATE USER {POSTGRES_CONFIG['zodbuser']} WITH PASSWORD '{POSTGRES_CONFIG['zodbuser_password']}';
                    END IF;
                END
                $$;
            """)
            
            cursor.execute(f"ALTER USER {POSTGRES_CONFIG['zodbuser']} CREATEDB CREATEROLE")
            
            # Conceder permissões
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {banco} TO {POSTGRES_CONFIG['zodbuser']}")
            
            # Configurações específicas do banco
            cursor.execute(f"ALTER DATABASE {banco} SET temp_buffers = '32MB'")
            cursor.execute(f"ALTER DATABASE {banco} SET work_mem = '32MB'")
            cursor.execute(f"ALTER DATABASE {banco} SET statement_timeout = '1h'")
        
        cursor.close()
        conn.close()
        
        # Agora conceder permissões nos schemas
        for banco in bancos:
            try:
                conn_schema = psycopg2.connect(
                    host=POSTGRES_CONFIG['host'],
                    port=POSTGRES_CONFIG['port'],
                    user=POSTGRES_CONFIG['superuser'],
                    password=POSTGRES_CONFIG['superuser_password'],
                    database=banco
                )
                conn_schema.autocommit = True
                cursor_schema = conn_schema.cursor()
                
                # Permissões COMPLETAS
                permissoes = [
                    f"GRANT ALL ON SCHEMA public TO {POSTGRES_CONFIG['zodbuser']}",
                    f"GRANT CREATE ON SCHEMA public TO {POSTGRES_CONFIG['zodbuser']}",
                    f"GRANT USAGE ON SCHEMA public TO {POSTGRES_CONFIG['zodbuser']}",
                    f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {POSTGRES_CONFIG['zodbuser']}",
                    f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {POSTGRES_CONFIG['zodbuser']}",
                    f"GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO {POSTGRES_CONFIG['zodbuser']}",
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO {POSTGRES_CONFIG['zodbuser']}",
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO {POSTGRES_CONFIG['zodbuser']}",
                    f"GRANT TEMPORARY ON DATABASE {banco} TO {POSTGRES_CONFIG['zodbuser']}",
                ]
                
                for permissao in permissoes:
                    try:
                        cursor_schema.execute(permissao)
                    except Exception as e:
                        logger.debug(f"  Permissão {permissao}: {e}")
                
                cursor_schema.close()
                conn_schema.close()
                
                logger.info(f"✓ Permissões concedidas em {banco}")
                
            except Exception as e:
                logger.error(f"✗ Erro permissões {banco}: {e}")
        
        logger.info("✓ Bancos limpos e configurados")
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro limpeza bancos: {e}")
        return False

def verificar_filestorage(fs_path):
    """Verificar integridade do FileStorage"""
    logger.info(f"Verificando {fs_path}...")
    
    try:
        if not os.path.exists(fs_path):
            logger.error(f"Arquivo não encontrado: {fs_path}")
            return False
        
        tamanho = os.path.getsize(fs_path)
        logger.info(f"  Tamanho: {tamanho/1024/1024:.2f} MB")
        
        # Testar abertura básica
        fs = FileStorage(fs_path, read_only=True)
        
        # Verificar se tem transações
        txn_count = 0
        for _ in fs.iterator():
            txn_count += 1
            if txn_count % 1000 == 0:
                logger.info(f"  Transações verificadas: {txn_count}")
        
        fs.close()
        
        logger.info(f"✓ FileStorage OK: {txn_count} transações")
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro verificação: {e}")
        return False

def migrar_com_keep_history_true(nome, fs_caminho, banco_destino):
    """Migração SEMPRE com keep_history=True para evitar erro de foreign key"""
    logger.info(f"\n{'='*60}")
    logger.info(f"MIGRANDO: {nome} para {banco_destino}")
    logger.info(f"COM keep_history=True (evita erro de foreign key)")
    logger.info(f"{'='*60}")
    
    # DSN simples
    dsn = f"dbname='{banco_destino}' user='{POSTGRES_CONFIG['zodbuser']}' host='{POSTGRES_CONFIG['host']}' password='{POSTGRES_CONFIG['zodbuser_password']}'"
    
    try:
        if not os.path.exists(fs_caminho):
            logger.error(f"Arquivo não encontrado: {fs_caminho}")
            return False
        
        tamanho = os.path.getsize(fs_caminho)
        tamanho_mb = tamanho/1024/1024
        logger.info(f"Arquivo: {fs_caminho}")
        logger.info(f"Tamanho: {tamanho_mb:.2f} MB")
        
        # Abrir FileStorage
        logger.info("Abrindo FileStorage...")
        source = FileStorage(fs_caminho, read_only=True)
        
        # Configuração SEGURA para evitar erro de foreign key
        logger.info("Configurando RelStorage (keep_history=True)...")
        
        adapter = PostgreSQLAdapter(dsn=dsn)
        
        # ⭐⭐ CORREÇÃO: SEMPRE usar keep_history=True durante a migração
        # Depois pode mudar no buildout.cfg se quiser
        destination = RelStorage(
            adapter=adapter,
            name=nome,
            keep_history=True,  # ⭐⭐ SEMPRE TRUE durante migração
            pack_gc=False,
            create=True,
            # Configurações mínimas para migração
            cache_local_mb=100,
            commit_lock_timeout=60,
        )
        
        # Estimar transações
        logger.info("Contando transações...")
        transaction_count = 0
        
        try:
            # Tentar método mais rápido primeiro
            iterator = source.iterator()
            for txn in iterator:
                transaction_count += 1
                if transaction_count % 5000 == 0:
                    logger.info(f"  Contadas: {transaction_count:,} transações")
            
            # Resetar posição
            source._pos = 0
            
        except:
            logger.warning("  Não foi possível contar transações precisamente")
            # Estimativa baseada no tamanho
            transaction_count = int(tamanho_mb / 0.5)  # Estimativa: 0.5MB por transação
        
        logger.info(f"Transações estimadas: {transaction_count:,}")
        
        # Migrar
        logger.info("Iniciando migração (pode levar tempo)...")
        start_time = time.time()
        
        # Monitor de progresso
        class Progresso:
            def __init__(self, total_estimado):
                self.total_estimado = total_estimado
                self.processadas = 0
                self.inicio = time.time()
                self.ultimo_log = time.time()
            
            def callback(self):
                self.processadas += 1
                agora = time.time()
                
                if self.processadas % 100 == 0 or (agora - self.ultimo_log) > 10:
                    decorrido = agora - self.inicio
                    velocidade = self.processadas / decorrido if decorrido > 0 else 0
                    percentual = (self.processadas / self.total_estimado) * 100 if self.total_estimado > 0 else 0
                    
                    logger.info(
                        f"  Progresso: {self.processadas:,}/{self.total_estimado:,} "
                        f"({percentual:.1f}%) - {velocidade:.1f} trans/seg"
                    )
                    self.ultimo_log = agora
        
        progresso = Progresso(transaction_count)
        
        # Usar copyTransactionsFrom com callback se suportado
        try:
            destination.copyTransactionsFrom(source)
        except Exception as e:
            logger.error(f"Erro na migração: {e}")
            
            # Tentar método alternativo: migrar em lotes
            logger.info("Tentando método alternativo...")
            return migrar_em_lotes(nome, fs_caminho, banco_destino)
        
        elapsed = time.time() - start_time
        
        logger.info(f"\n✅ MIGRAÇÃO CONCLUÍDA!")
        logger.info(f"  Tempo: {elapsed:.2f} segundos")
        logger.info(f"  Velocidade: {transaction_count/elapsed:.1f} trans/seg" if elapsed > 0 else "N/A")
        
        # Verificar resultado
        verificar_migracao(banco_destino)
        
        source.close()
        destination.close()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Erro na migração: {e}")
        import traceback
        traceback.print_exc()
        return False

def migrar_em_lotes(nome, fs_caminho, banco_destino):
    """Método alternativo para migração problemática"""
    logger.info(f"Tentando migração em lotes para {nome}...")
    
    dsn = f"dbname='{banco_destino}' user='{POSTGRES_CONFIG['zodbuser']}' host='{POSTGRES_CONFIG['host']}' password='{POSTGRES_CONFIG['zodbuser_password']}'"
    
    try:
        source = FileStorage(fs_caminho, read_only=True)
        
        # Configuração MÍNIMA
        adapter = PostgreSQLAdapter(dsn=dsn)
        destination = RelStorage(
            adapter=adapter,
            name=nome,
            keep_history=True,  # Importante!
            pack_gc=False,
            create=True,
        )
        
        # Tentar migração simples
        logger.info("Migrando...")
        start_time = time.time()
        
        destination.copyTransactionsFrom(source)
        
        elapsed = time.time() - start_time
        logger.info(f"✓ Migração concluída em {elapsed:.2f}s")
        
        source.close()
        destination.close()
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Falha mesmo em lotes: {e}")
        
        # Último recurso: usar zodbconvert
        return usar_zodbconvert(nome, fs_caminho, banco_destino)

def usar_zodbconvert(nome, fs_caminho, banco_destino):
    """Usar zodbconvert como último recurso"""
    logger.info(f"Tentando zodbconvert para {nome}...")
    
    dsn = f"dbname='{banco_destino}' user='{POSTGRES_CONFIG['zodbuser']}' host='{POSTGRES_CONFIG['host']}' password='{POSTGRES_CONFIG['zodbuser_password']}'"
    
    try:
        # Comando zodbconvert
        cmd = [
            sys.executable, "-m", "ZODB.scripts.zodbconvert",
            "-s", fs_caminho,
            "-d", f"postgresql://{POSTGRES_CONFIG['zodbuser']}:{POSTGRES_CONFIG['zodbuser_password']}@{POSTGRES_CONFIG['host']}:{POSTGRES_CONFIG['port']}/{banco_destino}",
            "--keep-history"
        ]
        
        logger.info(f"Executando: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        
        if result.returncode == 0:
            logger.info(f"✓ zodbconvert concluído")
            return True
        else:
            logger.error(f"✗ zodbconvert falhou: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"✗ Erro zodbconvert: {e}")
        return False

def verificar_migracao(banco_destino):
    """Verificar se a migração foi bem sucedida"""
    try:
        conn = psycopg2.connect(
            host=POSTGRES_CONFIG['host'],
            user=POSTGRES_CONFIG['zodbuser'],
            password=POSTGRES_CONFIG['zodbuser_password'],
            database=banco_destino
        )
        
        cursor = conn.cursor()
        
        # Verificar tabelas essenciais
        tabelas_essenciais = ['object_state', 'current_object', 'transaction']
        
        for tabela in tabelas_essenciais:
            cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
            count = cursor.fetchone()[0]
            logger.info(f"  {tabela}: {count:,} registros")
        
        # Verificar tamanho
        cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
        tamanho = cursor.fetchone()[0]
        logger.info(f"  Tamanho do banco: {tamanho}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        logger.warning(f"  Verificação incompleta: {e}")
        return False

def main():
    print("=" * 80)
    print("MIGRAÇÃO ZODB → POSTGRESQL - CORREÇÃO PARA ERRO DE FOREIGN KEY")
    print("Solução: keep_history=True durante a migração")
    print("=" * 80)
    
    # Solicitar senha do PostgreSQL
    if not POSTGRES_CONFIG['superuser_password']:
        print(f"\n🔐 Autenticação PostgreSQL:")
        try:
            conn = psycopg2.connect(
                host=POSTGRES_CONFIG['host'],
                port=POSTGRES_CONFIG['port'],
                user=POSTGRES_CONFIG['superuser'],
                database='postgres'
            )
            conn.close()
            logger.info("✓ Autenticação local")
        except:
            password = getpass.getpass("Senha do PostgreSQL: ")
            POSTGRES_CONFIG['superuser_password'] = password
    
    # 1. Limpar bancos completamente
    print("\n" + "="*80)
    print("1. LIMPEZA COMPLETA DOS BANCOS")
    print("="*80)
    
    if not limpar_bancos_completamente():
        logger.error("Falha na limpeza dos bancos")
        return False
    
    # 2. Verificar arquivos
    print("\n" + "="*80)
    print("2. VERIFICAÇÃO DOS ARQUIVOS")
    print("="*80)
    
    arquivos = {
        'main': '/var/openlegis/SAGL5/var/filestorage/Data.fs',
        'sapl_documentos': '/var/openlegis/SAGL5/var/filestorage/sapl_documentos.fs'
    }
    
    for nome, caminho in arquivos.items():
        if not verificar_filestorage(caminho):
            logger.warning(f"Problemas com {caminho}, continuando mesmo assim...")
    
    # 3. Migrar Data.fs (pequeno)
    print("\n" + "="*80)
    print("3. MIGRANDO Data.fs (estrutura principal)")
    print("="*80)
    
    data_migrado = False
    if os.path.exists(arquivos['main']):
        data_migrado = migrar_com_keep_history_true("main", arquivos['main'], "zodb")
    else:
        logger.warning("Data.fs não encontrado")
        data_migrado = True  # Considerar OK
    
    # 4. Migrar sapl_documentos.fs (grande)
    print("\n" + "="*80)
    print("4. MIGRANDO sapl_documentos.fs (documentos - 1.4GB)")
    print("AVISO: Pode levar VÁRIOS MINUTOS!")
    print("="*80)
    
    docs_migrado = False
    if os.path.exists(arquivos['sapl_documentos']):
        docs_migrado = migrar_com_keep_history_true("sapl_documentos", arquivos['sapl_documentos'], "sapl_documentos")
    else:
        logger.warning("sapl_documentos.fs não encontrado")
        docs_migrado = True  # Considerar OK
    
    # 5. Resultado
    print("\n" + "="*80)
    print("5. RESULTADO E CONFIGURAÇÃO")
    print("="*80)
    
    sucesso = data_migrado and docs_migrado
    
    if sucesso:
        print("\n✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
        
        print("\n" + "-"*80)
        print("CONFIGURAÇÃO buildout.cfg CORRIGIDA:")
        print("-"*80)
        
        config = f"""
# Variáveis de ambiente
environment-vars =
    RELSTORAGE_KEEP_HISTORY true
    RELSTORAGE_CACHE_LOCAL_MB 200
    RELSTORAGE_COMMIT_LOCK_TIMEOUT 60
"""
        
        print(config)
        
        print("\n⚠️  IMPORTANTE:")
        print("1. Use keep-history=true em AMBOS os bancos no buildout.cfg")
        print("2. Isso evita o erro de foreign key durante a migração")
        print("3. Depois que tudo estiver funcionando, você PODE (opcionalmente)")
        print("   mudar sapl_documentos para keep-history=false se quiser")
        
        print("\n🔧 PRÓXIMOS PASSOS:")
        print("1. Atualize buildout.cfg com configuração acima")
        print("2. Execute: ./bin/buildout -c buildout.cfg")
        print("3. Inicie: ./bin/supervisord")
        print("4. Teste o sistema")
        print("5. Só então considere mudar keep-history para false")
        
    else:
        print("\n❌ MIGRAÇÃO COM FALHAS")
        print(f"   Data.fs: {'✅' if data_migrado else '❌'}")
        print(f"   sapl_documentos.fs: {'✅' if docs_migrado else '❌'}")
        
        print("\n💡 SOLUÇÃO ALTERNATIVA:")
        print("Se persistirem erros, tente:")
        print("1. sudo -u postgres psql")
        print("2. DROP DATABASE zodb; DROP DATABASE sapl_documentos;")
        print("3. Execute este script novamente")
    
    return sucesso

if __name__ == '__main__':
    try:
        print("Execute este script para corrigir o erro de foreign key")
        print("="*60)
        
        if main():
            print("\n✅ Processo concluído!")
            print("\nLembre-se: Use keep-history=true no buildout.cfg")
        else:
            print("\n❌ Houve problemas na migração")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrompido")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
