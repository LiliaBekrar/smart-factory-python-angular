import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../environments/environment';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './login.html',
  styleUrls: ['./login.scss']
})
export class LoginComponent {
  email = '';
  password = '';
  error: string | null = null;
  loading = false;

  constructor(private http: HttpClient, private auth: AuthService, private router: Router) {}

  submit() {
    this.error = null;
    this.loading = true;

    // ⚠️ L’API FastAPI attend username=..., password=...
    const body = new URLSearchParams();
    body.set('username', this.email);
    body.set('password', this.password);

    this.http.post<any>(`${environment.apiUrl}/auth/login`, body.toString(), {
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
    }).subscribe({
      next: (resp) => {
        this.auth.login(resp.access_token); // stocke le token
        this.router.navigateByUrl('/');     // redirige
        this.loading = false;
      },
      error: () => {
        this.error = 'Identifiants invalides';
        this.loading = false;
      }
    });
  }
}
