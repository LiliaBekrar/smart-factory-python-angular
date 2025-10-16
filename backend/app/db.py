# backend/app/db.py
"""
📦 Module : Base de données SQLAlchemy (version synchrone)
=========================================================

Ce module configure :
- le moteur SQLAlchemy (`create_engine`)
- la session (`SessionLocal`)
- la base déclarative (`Base`)

⚙️ Utilisation :
    from app.db import SessionLocal, Base
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .settings import settings

# -------------------------------------------------
# 1️⃣ Récupération de l'URL de la base depuis les variables d'environnement
# -------------------------------------------------
#   Exemple attendu :
#   DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@HOST_POOLED:5432/DBNAME?sslmode=require"
#
# 👉 Cette variable est définie sur Render (onglet Environment)
# 👉 Le fichier app/settings.py lit cette valeur via python-dotenv ou os.environ
# -------------------------------------------------
DATABASE_URL = settings.database_url

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL manquante — vérifie les variables Render.")

# -------------------------------------------------
# 2️⃣ Création du moteur SQLAlchemy (mode synchrone)
# -------------------------------------------------
# future=True → compatibilité SQLAlchemy 2.0
# pool_pre_ping=True → vérifie la connexion avant chaque requête (utile sur Render)
# -------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    future=True,
    pool_pre_ping=True,
)

# -------------------------------------------------
# 3️⃣ Fabrique de sessions (SessionLocal)
# -------------------------------------------------
# autocommit=False : on valide explicitement avec .commit()
# autoflush=False  : pas de flush automatique à chaque requête
# -------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# -------------------------------------------------
# 4️⃣ Classe de base pour les modèles
# -------------------------------------------------
# Tous les modèles SQLAlchemy doivent hériter de Base
# Exemple :
#     class User(Base):
#         __tablename__ = "users"
#         id = Column(Integer, primary_key=True)
# -------------------------------------------------
Base = declarative_base()
