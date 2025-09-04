import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../environments/environment';
import { Observable } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  getDashboardSummary(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/dashboard/summary`);
  }

  getMachines(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/machines`);
  }

  getRecentActivities(): Observable<any> {
    return this.http.get(`${environment.apiUrl}/activities/recent`);
  }
}
