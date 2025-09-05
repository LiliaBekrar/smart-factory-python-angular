import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';

export type Machine = {
  id: number;
  name: string;
  code: string;
  status: 'running'|'stopped'|'setup';
  target_rate_per_hour: number;
};

export type ActivityItem = {
  id: number;
  machine_id: number;
  machine_code?: string | null;
  machine_name?: string | null; // ← on l’exposera bien côté backend
  work_order_id?: number | null;
  work_order_number?: string | null;
  event_type: 'good'|'scrap'|'stop';
  qty: number;
  notes?: string | null;
  happened_at: string; // ISO
};

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  // Dashboard résumé
  getDashboardSummary(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/dashboard/summary`);
  }

  // Machines (liste)
  getMachines(): Observable<Machine[]> {
    return this.http.get<Machine[]>(`${environment.apiUrl}/machines`);
  }

  // Machine (détail) — OK si l’endpoint backend existe (cf. §2)
  getMachine(id: number): Observable<Machine> {
    return this.http.get<Machine>(`${environment.apiUrl}/machines/${id}`);
  }

  // Activités récentes (toutes machines)
  getRecentActivities(minutes = 120, limit = 50): Observable<ActivityItem[]> {
    const params = new HttpParams()
      .set('minutes', String(minutes))
      .set('limit', String(limit));
    return this.http.get<ActivityItem[]>(`${environment.apiUrl}/activities/recent`, { params });
  }

  // Activité d’une machine
  getMachineActivity(machineId: number, minutes = 120, limit = 50): Observable<ActivityItem[]> {
    const params = new HttpParams()
      .set('minutes', String(minutes))
      .set('limit', String(limit));
    return this.http.get<ActivityItem[]>(`${environment.apiUrl}/machines/${machineId}/activity`, { params });
  }
}
