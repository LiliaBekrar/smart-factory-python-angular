import { Component, OnInit } from '@angular/core';          // décorateur @Component + cycle de vie OnInit
import { CommonModule } from '@angular/common';             // ngIf, ngFor, pipe date, etc.
import { ApiService } from '../../services/api';            // notre service HTTP (appels vers FastAPI)

/**
 * Composant Dashboard (standalone)
 * - Appelle /dashboard/summary via ApiService
 * - Gère 3 états : loading / error / data (summary)
 */
@Component({
  selector: 'app-dashboard',       // balise HTML à utiliser <app-dashboard></app-dashboard>
  standalone: true,                // composant standalone (Angular v15+), pas besoin d'être déclaré dans un module
  imports: [CommonModule],         // importe ngIf, ngFor, date pipe, etc.
  templateUrl: './dashboard.html', // ton fichier de template (tu n'utilises pas .component.html)
  styleUrl: './dashboard.scss'     // ton fichier de styles
})
export class Dashboard implements OnInit {
  // --- état UI ---
  loading = false;            // vrai pendant le chargement
  error: string | null = null; // message d'erreur éventuel
  summary: any = null;        // objet renvoyé par /dashboard/summary

  constructor(private api: ApiService) {} // injection du service HTTP

  // hook appelé à l'initialisation du composant (une seule fois)
  ngOnInit(): void {
    this.refresh(); // on charge les données dès l'arrivée sur la page
  }

  /**
   * Recharge les données du dashboard en appelant l'API.
   */
  refresh(): void {
    this.loading = true;     // active le spinner
    this.error = null;       // reset l'erreur

    // Appel HTTP → GET /dashboard/summary
    this.api.getDashboardSummary().subscribe({
      next: (res) => {
        this.summary = res;  // stocke la réponse (sera utilisée par le template)
        this.loading = false;
      },
      error: (err) => {
        // essaie d'afficher un message renvoyé par l'API, sinon générique
        this.error = err?.error?.detail || 'Erreur lors du chargement du dashboard';
        this.loading = false;
      }
    });
  }
}
