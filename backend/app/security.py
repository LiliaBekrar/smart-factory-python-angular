# app/security.py
"""
Sécurité & authentification pour l’API Smart Factory :
- Hachage sécurisé des mots de passe (pbkdf2_sha256)
- Création et vérification de tokens JWT
- Vérification de mot de passe utilisateur
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from jose import jwt, JWTError
from passlib.context import CryptContext

# ==========================================================
# 🔐 PARAMÈTRES GLOBAUX : JWT + CONFIG ENVIRONNEMENT
# ==========================================================

# Clé secrète (⚠️ chargée depuis .env / Render → SECRET_KEY)
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

# Algo de signature du token JWT
ALGORITHM = "HS256"

# Durée de validité du token d’accès (minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))


# ==========================================================
# 🔒 HACHAGE DES MOTS DE PASSE
# ==========================================================
# ✅ On utilise PBKDF2-SHA256 (algorithme standard, fiable, sans dépendance C)
#    → évite les bugs de bcrypt sur certains serveurs Render (ValueError 72 bytes)
#    → compatible 100% Passlib + Python pur
#
# bcrypt/bcrypt_sha256 ≠ stable sur Render Free (compilation & versioning)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hache un mot de passe en clair avec pbkdf2_sha256.
    - Entrée : mot de passe utilisateur ("pass1234")
    - Sortie : chaîne hachée (commence par '$pbkdf2-sha256$...')
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie si un mot de passe en clair correspond à son hash stocké.
    - Retourne True si OK, False sinon.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ==========================================================
# 🪪 GESTION DES JETONS JWT
# ==========================================================

def create_access_token(
    data: dict, expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    """
    Crée un token JWT signé avec une date d’expiration.

    - `data` contient les claims (ex: {"sub": user.id, "role": user.role})
    - Le token est signé avec SECRET_KEY
    - Retourne une chaîne encodée utilisable comme Bearer Token
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Décode et valide un token JWT.
    - Retourne le payload décodé (dictionnaire)
    - Retourne None si le token est invalide ou expiré
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
