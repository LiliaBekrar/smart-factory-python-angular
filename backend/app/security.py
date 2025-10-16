# ============================================================
# app/security.py
# ------------------------------------------------------------
# 🔐 Gestion de la sécurité et de l’authentification
# ------------------------------------------------------------
# Fonctions :
#   - hash_password()  : hachage sécurisé des mots de passe
#   - verify_password(): vérification des mots de passe
#   - create_access_token(): génération d’un JWT
#   - decode_token()   : décodage / validation d’un JWT
# ============================================================

from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from jose import jwt, JWTError
from passlib.context import CryptContext

# ============================================================
# ⚙️ Paramètres globaux
# ============================================================

# Clé secrète pour signer les tokens JWT
# ⚠️ En production, la clé doit venir d’une variable d’environnement !
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

# Algorithme de signature JWT (HS256 = standard symétrique)
ALGORITHM = "HS256"

# Durée de validité du token d’accès (en minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ============================================================
# 🔑 Gestion du hachage des mots de passe
# ============================================================
# bcrypt_sha256 : Passlib fait d’abord un SHA256 → supprime la limite de 72 bytes
# et renforce légèrement la sécurité contre certains vecteurs d’attaque.
pwd_context = CryptContext(schemes=["bcrypt_sha256"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hache un mot de passe en clair avec bcrypt_sha256.
    Retourne une chaîne de hachage sécurisée (stockable en base).
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Vérifie qu’un mot de passe correspond à son hash.
    Retourne True si ok, False sinon.
    """
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================
# 🧾 Gestion des tokens JWT
# ============================================================

def create_access_token(
    data: dict,
    expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
) -> str:
    """
    Génère un token JWT signé contenant les données fournies.
    Exemple de payload : {"sub": user_id, "role": "admin"}
    """
    to_encode = data.copy()

    # Expiration du token
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})

    # Génération du JWT signé avec la clé secrète
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """
    Décode et valide un token JWT.
    Retourne le payload (dict) si valide, sinon None.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        # Token expiré, malformé ou clé invalide
        return None
