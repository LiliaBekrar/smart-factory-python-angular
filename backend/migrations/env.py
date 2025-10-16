"""
==========================================================
🔧 Alembic environment script
Gère les migrations de base de données (création/modification des tables).
==========================================================
"""

import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# --- Import des modèles et de la base ---
from app.db import Base                # Contient la classe declarative_base()
from app import models                 # ⚠️ Importe tous les modèles pour remplir Base.metadata

# --- Configuration Alembic (.ini) ---
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Cible des métadonnées pour les migrations ---
# Alembic détecte les changements à partir de Base.metadata
target_metadata = Base.metadata

# ==========================================================
# 1️⃣ Lecture de l’URL de la base pour Alembic
# ==========================================================
# ⚠️ Utilise ALEMBIC_DATABASE_URL (sync, psycopg2)
# et non DATABASE_URL (async, asyncpg) !
ALEMBIC_DATABASE_URL = os.getenv("ALEMBIC_DATABASE_URL")

if not ALEMBIC_DATABASE_URL:
    raise RuntimeError(
        "❌ Variable d'environnement 'ALEMBIC_DATABASE_URL' manquante. "
        "Ajoute-la dans ton fichier .env (PostgreSQL sync psycopg2)."
    )

# Injecte dynamiquement l’URL dans la config Alembic
config.set_main_option("sqlalchemy.url", ALEMBIC_DATABASE_URL)

# ==========================================================
# 2️⃣ Mode offline — génère les migrations sans connexion DB
# ==========================================================
def run_migrations_offline():
    """Exécute les migrations en mode offline (pas de connexion à la DB)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,  # Compare aussi les types de colonnes
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

# ==========================================================
# 3️⃣ Mode online — exécute les migrations avec connexion DB
# ==========================================================
def run_migrations_online():
    """Exécute les migrations en se connectant à la DB (mode normal)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Pas de pool de connexions pour Alembic
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()

# ==========================================================
# 4️⃣ Choix du mode d’exécution
# ==========================================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
