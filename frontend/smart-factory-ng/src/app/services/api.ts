import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment'; // <-- prend l'URL du backend
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  constructor(private http: HttpClient) {}

  /**
   * Récupère le résumé global du dashboard
   * - total machines / running / stopped
   * - TRS moyen
   * - Activités récentes
   */
  getDashboardSummary(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/dashboard/summary`);
  }

  /**
   * Récupère la liste de toutes les machines
   */
  getMachines(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/machines`);
  }

  /**
   * Récupère les activités récentes (limite 50, sur 120 minutes par défaut)
   */
  getRecentActivities(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/activities/recent`);
  }
}
