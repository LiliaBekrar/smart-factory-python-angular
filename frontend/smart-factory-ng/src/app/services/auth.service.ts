import { Injectable, computed, signal } from '@angular/core';

type JwtPayload = { sub?: string; role?: string; exp?: number; [k: string]: any };

function decodeJwt(token: string | null): JwtPayload | null {
  if (!token) return null;
  try {
    const base = token.split('.')[1];
    const json = atob(base.replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decodeURIComponent(escape(json)));
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  // on initialise depuis localStorage
  private _token = signal<string | null>(localStorage.getItem('token'));
  // payload décodé (ou null)
  payload = computed(() => decodeJwt(this._token()));
  // état pratique
  isLoggedIn = computed(() => !!this._token());
  role = computed(() => this.payload()?.role ?? null);

  /** Renvoie le token courant (ou null) */
  token() { return this._token(); }

  /** Login: stocke le token et met à jour les signaux */
  login(accessToken: string) {
    localStorage.setItem('token', accessToken);
    this._token.set(accessToken);
  }

  /** Logout: efface le token */
  logout() {
    localStorage.removeItem('token');
    this._token.set(null);
  }
}
