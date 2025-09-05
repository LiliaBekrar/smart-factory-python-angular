import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';

export type Machine = {
  id: number;
  name: string;
  code: string;
  status: 'running' | 'stopped' | 'setup';
  target_rate_per_hour: number;
};

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

export type User = {
  id: number;
  email: string;
  role: 'admin' | 'chef' | 'operator';
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

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // --- helpers ---
  /** Construit des HttpParams en ignorant les valeurs null/undefined */
  private params(obj: Record<string, unknown>): HttpParams {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(obj)) {
      if (v !== null && v !== undefined) p = p.set(k, String(v));
    }
    return p;
  }

  private base(url: string) {
    return `${environment.apiUrl}${url}`;
  }

  // =======================
  // Admin / Users
  // =======================
  getUsers(): Observable<User[]> {
    return this.http.get<User[]>(this.base('/admin/users'));
  }

  createUser(p: { email: string; password: string; role: User['role'] }): Observable<User> {
    return this.http.post<User>(this.base('/admin/users'), p);
  }

  updateUser(
    id: number,
    p: Partial<{ email: string; password: string; role: User['role'] }>
  ): Observable<User> {
    return this.http.patch<User>(this.base(`/admin/users/${id}`), p);
  }

  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(this.base(`/admin/users/${id}`));
  }

  // =======================
  // Dashboard résumé
  // =======================
  getDashboardSummary(minutes?: number, limit_recent: number = 5): Observable<any> {
    const params = this.params({ minutes, limit_recent });
    return this.http.get(this.base('/dashboard/summary'), { params });
  }

  // =======================
  // Machines
  // =======================
  getMachines(): Observable<Machine[]> {
    return this.http.get<Machine[]>(this.base('/machines'));
  }

  getMachine(id: number): Observable<Machine> {
    return this.http.get<Machine>(this.base(`/machines/${id}`));
  }

  // KPIs (si les routes existent côté backend)
  getMachineKpis(
    machineId: number,
    minutes?: number
  ): Observable<{ good: number; scrap: number; trs: number }> {
    const params = this.params({ minutes });
    return this.http.get<{ good: number; scrap: number; trs: number }>(
      this.base(`/machines/${machineId}/kpis`),
      { params }
    );
  }

  getGlobalKpis(minutes?: number): Observable<{ good: number; scrap: number; trs: number }> {
    const params = this.params({ minutes });
    return this.http.get<{ good: number; scrap: number; trs: number }>(
      this.base('/kpis/global'),
      { params }
    );
  }

  // =======================
  // Activités
  // =======================
  getRecentActivities(minutes?: number, limit: number = 50): Observable<ActivityItem[]> {
    const params = this.params({ minutes, limit });
    return this.http.get<ActivityItem[]>(this.base('/activities/recent'), { params });
  }

  getMachineActivity(
    machineId: number,
    minutes?: number,
    limit: number = 50
  ): Observable<ActivityItem[]> {
    const params = this.params({ minutes, limit });
    return this.http.get<ActivityItem[]>(this.base(`/machines/${machineId}/activity`), {
      params,
    });
  }

  // =======================
  // Événements (création)
  // =======================
  createEvent(payload: EventCreate): Observable<EventOut> {
    return this.http.post<EventOut>(this.base('/events'), payload);
  }
}
