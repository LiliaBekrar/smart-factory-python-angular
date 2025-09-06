// src/app/services/auth.service.ts
// -------------------------------------------------------------
// Service d’authentification côté front (Angular).
// - Stocke/récupère le JWT dans localStorage
// - Décode le payload (sub, role, exp, …)
// - Expose des signaux (isLoggedIn, role, userId)
// - Fournit login()/logout()
// -------------------------------------------------------------

import { Injectable, computed, signal } from '@angular/core';

// ---- Typage du payload JWT ---------------------------------
// On indique explicitement les champs standard qu’on attend.
// (On garde [k: string]: any pour être tolérant aux champs en plus)
export type JwtPayload = {
  sub?: string;                                   // id utilisateur (string → on convertira en number)
  role?: 'admin' | 'chef' | 'operator';           // rôle de l’utilisateur
  exp?: number;                                    // expiration (epoch seconds)
  [k: string]: any;                                // champs additionnels éventuels
};

// ---- Helper: décodage base64url vers UTF-8 -----------------
// Les JWT utilisent du base64 *URL-safe*. On remet les bons caractères,
// on padde si besoin (=), puis on atob(). On reconstruit une chaîne UTF-8.
function base64UrlDecode(input: string): string {
  // pad (pour que la longueur soit multiple de 4)
  const pad = '='.repeat((4 - (input.length % 4)) % 4);
  const base64 = (input + pad).replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(base64);
  // Convertit le binaire en chaîne UTF-8 “safe”
  try {
    const utf8 = decodeURIComponent(
      binary
        .split('')
        .map((c) => '%' + c.charCodeAt(0).toString(16).padStart(2, '0'))
        .join('')
    );
    return utf8;
  } catch {
    // Au pire, on renvoie la chaîne ASCII (souvent suffisant pour un JWT)
    return binary;
  }
}

// ---- Helper: décode un JWT (ou null si invalide) -----------
function decodeJwt(token: string | null): JwtPayload | null {
  if (!token) return null;
  try {
    // Un JWT = "header.payload.signature" → on prend la 2e partie
    const payloadPart = token.split('.')[1];
    if (!payloadPart) return null;
    const json = base64UrlDecode(payloadPart);
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null; // token malformé / JSON invalide
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  // ---- État interne (signal) --------------------------------
  // On initialise le token depuis localStorage (si présent).
  private _token = signal<string | null>(localStorage.getItem('token'));

  // ---- Sélecteurs (computed) --------------------------------
  // Payload décodé (ou null si pas de token / invalide)
  payload = computed<JwtPayload | null>(() => decodeJwt(this._token()));

  // Vrai si un token est stocké
  isLoggedIn = computed<boolean>(() => !!this._token());

  // Rôle utilisateur ('admin' | 'chef' | 'operator' | null)
  role = computed<JwtPayload['role'] | null>(() => this.payload()?.role ?? null);

  // Id utilisateur (number | null) → on convertit le `sub` (string) en number
  userId = computed<number | null>(() => {
    const sub = this.payload()?.sub;
    return sub ? Number(sub) : null;
  });

  // Petits helpers pratiques pour le template
  isAdmin = computed<boolean>(() => this.role() === 'admin');
  isChef = computed<boolean>(() => this.role() === 'chef');
  isOperator = computed<boolean>(() => this.role() === 'operator');

  // ---- Méthodes publiques -----------------------------------
  /** Renvoie le token courant (ou null) — pratique pour les interceptors */
  token(): string | null {
    return this._token();
  }

  /**
   * Enregistre le token après un /auth/login réussi.
   * - persiste en localStorage
   * - met à jour les signaux (payload, role, isLoggedIn, …)
   */
  login(accessToken: string): void {
    localStorage.setItem('token', accessToken);
    this._token.set(accessToken);
  }

  /**
   * Déconnecte l’utilisateur :
   * - supprime le token du localStorage
   * - remet l’état à “déconnecté”
   */
  logout(): void {
    localStorage.removeItem('token');
    this._token.set(null);
  }
}
