// src/app/services/api.ts
// -------------------------------------------------------------
// Service Angular centralisant tous les appels HTTP vers l’API
// - Garde une seule source de vérité pour les URLs et les types
// - Facilite le refactor (changement de routes, d’URL base, etc.)
// -------------------------------------------------------------

import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';

// =======================
// Types (DTO côté front)
// =======================

// --- Utilisateurs ---
export type User = {
  id: number;
  email: string;
  role: 'admin' | 'chef' | 'operator';
};

// --- Machines ---
export type Machine = {
  id: number;
  name: string;
  code: string;
  status: 'running' | 'stopped' | 'setup';
  target_rate_per_hour: number;
  created_by?: number | null; // (exposé par le backend pour savoir qui peut éditer/supprimer)
};

// --- Activité / Événements ---
export type ActivityItem = {
  id: number;
  machine_id: number;
  machine_code?: string | null;
  machine_name?: string | null;
  work_order_id?: number | null;
  work_order_number?: string | null;
  event_type: 'good' | 'scrap' | 'stop';
  qty: number;
  notes?: string | null;
  happened_at: string; // ISO
};

export type EventCreate = {
  machine_id: number;
  work_order_id?: number | null;
  event_type: 'good' | 'scrap' | 'stop';
  qty: number;
  notes?: string | null;
  happened_at?: string | null; // ISO optionnel
};

export type EventOut = {
  id: number;
  machine_id: number;
  work_order_id?: number | null;
  event_type: 'good' | 'scrap' | 'stop';
  qty: number;
  notes?: string | null;
  happened_at: string; // ISO
};

// --- KPIs (exemples de réponses attendues) ---
export type MachineKpis = { good: number; scrap: number; trs: number };
export type GlobalKpis  = { good: number; scrap: number; trs: number };

// =======================
// Service
// =======================
@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // -----------------------
  // Helpers internes
  // -----------------------

  /** Construit des HttpParams en ignorant les valeurs null/undefined. */
  private params(obj: Record<string, unknown>): HttpParams {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(obj)) {
      if (v !== null && v !== undefined) p = p.set(k, String(v));
    }
    return p;
  }

  /** Préfixe toutes les routes par l’URL du backend. */
  private base(url: string) {
    return `${environment.apiUrl}${url}`;
  }

  // =======================
  // Admin / Users
  // =======================

  /** Liste tous les utilisateurs (rôles admin/chef requises côté backend). */
  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(this.base('/admin/users'));
  }

  /** Crée un utilisateur (email, password, role). */
  createUser(p: { email: string; password: string; role: User['role'] }): Observable<User> {
    return this.http.post<User>(this.base('/admin/users'), p);
  }

  /** Met à jour un utilisateur (partiel). */
  updateUser(
    id: number,
    p: Partial<{ email: string; password: string; role: User['role'] }>
  ): Observable<User> {
    return this.http.patch<User>(this.base(`/admin/users/${id}`), p);
  }

  /** Supprime un utilisateur. */
  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(this.base(`/admin/users/${id}`));
  }

  // =======================
  // Dashboard
  // =======================

  /**
   * Récupère un résumé global (KPIs + activités récentes).
   * - `minutes` est optionnel (si omis: valeur par défaut backend)
   * - `limit_recent` = nombre d'items récents (défaut 5)
   */
  getDashboardSummary(minutes?: number, limit_recent: number = 5): Observable<any> {
    const params = this.params({ minutes, limit_recent });
    return this.http.get(this.base('/dashboard/summary'), { params });
  }

  // =======================
  // Machines (lecture)
  // =======================

  /** Liste toutes les machines. */
  getMachines(): Observable<Machine[]> {
    return this.http.get<Machine[]>(this.base('/machines'));
  }

  /** Récupère une machine par id. */
  getMachine(id: number): Observable<Machine> {
    return this.http.get<Machine>(this.base(`/machines/${id}`));
  }

  // =======================
  // Machines (CRUD)
  // =======================

  /**
   * Crée une machine.
   * - Le backend renseignera `created_by` = id de l’utilisateur connecté.
   */
  createMachine(payload: {
    name: string;
    code: string;
    status?: 'running' | 'stopped' | 'setup';
    target_rate_per_hour?: number;
  }): Observable<Machine> {
    return this.http.post<Machine>(this.base('/machines'), payload);
  }

  /**
   * Met à jour une machine (PATCH partiel).
   * - Seuls les champs fournis seront modifiés côté backend.
   */
  updateMachine(id: number, payload: Partial<Machine>): Observable<Machine> {
    return this.http.patch<Machine>(this.base(`/machines/${id}`), payload);
  }

  /**
   * Supprime une machine.
   */
  deleteMachine(id: number): Observable<{ ok: boolean }> {
    return this.http.delete<{ ok: boolean }>(this.base(`/machines/${id}`));
  }

  // =======================
  // KPIs (si routes existantes)
  // =======================

  /** KPIs d’une machine sur une fenêtre (minutes optionnel). */
  getMachineKpis(machineId: number, minutes?: number): Observable<MachineKpis> {
    const params = this.params({ minutes });
    return this.http.get<MachineKpis>(this.base(`/machines/${machineId}/kpis`), { params });
  }

  /** KPIs globaux (si route /kpis/global existe côté backend). */
  getGlobalKpis(minutes?: number): Observable<GlobalKpis> {
    const params = this.params({ minutes });
    return this.http.get<GlobalKpis>(this.base('/kpis/global'), { params });
  }

  // =======================
  // Activités
  // =======================

  /** Flux récent toutes machines (minutes optionnel, limit=50 par défaut). */
  getRecentActivities(minutes?: number, limit: number = 50): Observable<ActivityItem[]> {
    const params = this.params({ minutes, limit });
    return this.http.get<ActivityItem[]>(this.base('/activities/recent'), { params });
  }

  /** Activité d’une machine donnée (minutes optionnel, limit=50 par défaut). */
  getMachineActivity(
    machineId: number,
    minutes?: number,
    limit: number = 50
  ): Observable<ActivityItem[]> {
    const params = this.params({ minutes, limit });
    return this.http.get<ActivityItem[]>(this.base(`/machines/${machineId}/activity`), { params });
  }

  // =======================
  // Événements (création opérateur/chef/admin)
  // =======================

  /** Crée un événement de production. */
  createEvent(payload: EventCreate): Observable<EventOut> {
    return this.http.post<EventOut>(this.base('/events'), payload);
  }
}
