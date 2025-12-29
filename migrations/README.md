# Migrations - Alembic

Este diretório contém as migrations do Alembic para o projeto SAGL.

## 📚 Documentação

### Guia Completo de Migração de Dados

**📖 [GUIA_COMPLETO_MIGRACAO_DADOS.md](GUIA_COMPLETO_MIGRACAO_DADOS.md)** - Guia consolidado e completo sobre migração de dados entre bancos.

Este guia contém:
- ✅ Visão geral e conceitos
- ✅ Requisitos e pré-requisitos
- ✅ Configuração passo a passo
- ✅ Execução detalhada
- ✅ Troubleshooting completo
- ✅ Exemplos práticos
- ✅ Checklist de verificação

**👉 Comece por aqui para migrar dados entre bancos!**

## 📁 Estrutura

- `versions/` - Arquivos de migration do Alembic
- `env.py` - Configuração do ambiente Alembic
- `GUIA_COMPLETO_MIGRACAO_DADOS.md` - **Guia principal** (consolidado)

## 🚀 Quick Start

### Migração de Dados entre Bancos

```bash
# 1. Verificar status
bin/alembic current

# 2. Se migration já aplicada, fazer downgrade
bin/alembic downgrade -1

# 3. Executar migração manual
ALLOW_MANUAL_DATA_MIGRATION=1 bin/alembic upgrade exemplo_migracao_dados
```

**📖 Consulte [GUIA_COMPLETO_MIGRACAO_DADOS.md](GUIA_COMPLETO_MIGRACAO_DADOS.md) para instruções completas.**

## 📝 Migrations Disponíveis

- `95b3df90d492` - Inserir dados iniciais do sistema
- `exemplo_migracao_dados` - Migração manual de dados entre bancos

## ⚠️ Importante

- A migration `exemplo_migracao_dados` é **MANUAL** e não executa automaticamente
- Requer variável de ambiente `ALLOW_MANUAL_DATA_MIGRATION=1` para executar
- Consulte o guia completo para detalhes




