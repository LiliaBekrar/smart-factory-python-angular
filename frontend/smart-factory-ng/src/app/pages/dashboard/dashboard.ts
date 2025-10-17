// ========================================================================
// 🌍 FICHIER : src/app/pages/dashboard/dashboard.ts
// ------------------------------------------------------------------------
// Ce fichier définit le *composant Angular* du tableau de bord principal.
// C’est l’un des “écrans” de l’application Smart Factory.
//
// ▶ Rôle de ce composant :
//   - afficher les indicateurs globaux du parc de machines (résumé),
//   - visualiser la répartition des états (“en marche”, “à l’arrêt”, “réglage”),
//   - afficher un graphique en donut interactif,
//   - permettre à l’utilisateur de cliquer sur le graphique pour accéder
//     directement à la liste des machines correspondantes.
//
// ▶ Il est directement lié à deux éléments :
//   - son *template HTML* associé → `dashboard.html` (affichage visuel),
//   - le *service d’API* → `src/app/services/api.ts` (communication avec le backend FastAPI).
// ========================================================================

// Import des fonctionnalités de base d’Angular (composant, cycle de vie, signaux réactifs)
import { Component, OnInit, signal } from '@angular/core';

// Import du module “CommonModule” (nécessaire pour utiliser *ngIf, *ngFor, etc. dans le template HTML)
import { CommonModule } from '@angular/common';

// Import du service interne `ApiService`
// Ce service est défini dans `src/app/services/api.ts` et gère toutes les requêtes HTTP vers ton backend FastAPI
import { ApiService } from '../../services/api';

// Import du module qui permet d’afficher des graphiques Chart.js dans Angular
// Il provient de la librairie open source “ng2-charts”
import { BaseChartDirective } from 'ng2-charts';

// Import des types nécessaires pour typer les données du graphique Chart.js
import { ChartData, ChartOptions, ChartType } from 'chart.js';

// Import du service de navigation Angular
// Il permet de rediriger l’utilisateur vers une autre page, comme “/machines”
import { Router } from '@angular/router';

// ========================================================================
// 🧩 DÉFINITION DU COMPOSANT ANGULAR
// ------------------------------------------------------------------------
// Chaque composant Angular correspond à une “brique visuelle” de ton application.
// Il est défini à l’aide du décorateur `@Component()`.
// ========================================================================

@Component({
  // Nom utilisé dans le HTML parent pour insérer ce composant (ex: <app-dashboard>)
  selector: 'app-dashboard',

  // Ce composant est “standalone” → il ne dépend pas d’un module Angular externe
  standalone: true,

  // Liste des modules Angular nécessaires à ce composant
  // Ici : CommonModule (pour les directives Angular) + BaseChartDirective (pour les graphiques)
  imports: [CommonModule, BaseChartDirective],

  // Lien vers le fichier HTML associé (vue du tableau de bord)
  templateUrl: './dashboard.html',
})
export class DashboardComponent implements OnInit {
  // =====================================================================
  // ⚙️ PARTIE 1 — VARIABLES ET ÉTATS INTERNES DU COMPOSANT
  // =====================================================================

  // Signal réactif indiquant si le composant est en cours de chargement.
  // signal(false) = valeur initiale (non chargé)
  // Un “signal” est une fonctionnalité Angular 16+ qui rend les données réactives sans besoin d’observables.
  loading = signal(false);

  // Signal pour stocker un éventuel message d’erreur
  error = signal<string | null>(null);

  // Signal contenant les données globales récupérées depuis le backend FastAPI
  // (renvoyées par la route `/api/dashboard/summary` dans ton backend)
  summary = signal<any>(null);

  // =====================================================================
  // 📈 PARTIE 2 — GETTERS MÉTIER (calculs à partir des données brutes)
  // =====================================================================

  // Nombre total de machines, issu du champ “kpis.total_machines” renvoyé par l’API
  get total() {
    return this.summary()?.kpis?.total_machines ?? 0;
  }

  // Nombre de machines “en marche” (kpis.running)
  get running() {
    return this.summary()?.kpis?.running ?? 0;
  }

  // Nombre de machines “à l’arrêt” (kpis.stopped)
  get stopped() {
    return this.summary()?.kpis?.stopped ?? 0;
  }

  // Nombre de machines “en réglage” → calculé localement :
  // total - running - stopped (pour éviter d’avoir un champ manquant)
  get setup() {
    return Math.max(0, this.total - this.running - this.stopped);
  }

  // TRS moyen sur la dernière heure (KPI envoyé par l’API)
  // TRS = Taux de Rendement Synthétique, indicateur de performance industrielle.
  get trs() {
    return this.summary()?.kpis?.trs_avg_last_hour ?? 0;
  }

  // =====================================================================
  // 🍩 PARTIE 3 — CONFIGURATION DU GRAPHIQUE (Chart.js)
  // =====================================================================

  // Type du graphique utilisé : “doughnut” = graphique circulaire avec un trou au centre
  pieType: ChartType = 'doughnut';

  // Données initiales du graphique (avant le chargement de l’API)
  pieData: ChartData<'doughnut'> = {
    labels: ['Running', 'Stopped', 'Setup'], // libellés affichés dans la légende ou au survol
    datasets: [
      {
        data: [0, 0, 0], // valeurs par défaut (mises à jour ensuite)
        backgroundColor: ['#1DB954', '#E03131', '#FFB020'], // couleurs (vert, rouge, orange)
      },
    ],
  };

  // Options graphiques (initialisées dans ngOnInit pour ajouter le clic)
  pieOptions!: ChartOptions<'doughnut'>;

  // Dictionnaire de correspondance entre le libellé du graphique (en anglais)
  // et la valeur du paramètre de filtre attendu dans la page /machines
  // Exemple : “Running” → ?status=running
  private statusMap: Record<string, 'running' | 'stopped' | 'setup'> = {
    'Running': 'running',
    'Stopped': 'stopped',
    'Setup': 'setup',
  };

  // =====================================================================
  // 🧭 PARTIE 4 — CONSTRUCTEUR
  // =====================================================================

  // Le constructeur reçoit deux “injections de dépendances” :
  // - api : pour parler au backend (récupération des données),
  // - router : pour rediriger l’utilisateur vers une autre page Angular.
  constructor(private api: ApiService, private router: Router) {}

  // =====================================================================
  // 🚀 PARTIE 5 — INITIALISATION DU COMPOSANT (méthode ngOnInit)
  // =====================================================================
  // Cette méthode est automatiquement appelée par Angular au moment où
  // le composant est affiché pour la première fois à l’écran.
  ngOnInit() {
    // Configuration complète du graphique “donut”
    this.pieOptions = {
      // Taille du trou central (en pourcentage)
      cutout: '70%',

      // On désactive la légende intégrée de Chart.js (car une légende custom existe dans dashboard.html)
      plugins: { legend: { display: false } },

      // Animation douce du graphique à l’affichage
      animation: { animateRotate: true, duration: 600 },

      // Fonction appelée automatiquement quand l’utilisateur clique sur le graphique
      onClick: (_event, activeEls, chart) => {
        // “activeEls” contient les éléments du graphique cliqués (segments)
        // Si aucun segment n’est sélectionné, on ne fait rien
        if (!activeEls.length) return;

        // On récupère l’index du segment cliqué (0 = Running, 1 = Stopped, 2 = Setup)
        const index = activeEls[0].index;

        // On retrouve le label (texte) correspondant dans les labels du graphique
        const label = chart.data.labels?.[index] as string | undefined;

        // On convertit ce label (“Running”) en valeur utilisable par la page “Machines”
        const status = label ? this.statusMap[label] : undefined;

        // Si on a trouvé un statut valide → redirection vers la page /machines
        // Exemple : /machines?status=running
        if (status) {
          this.router.navigate(['/machines'], { queryParams: { status } });
        }
      },
    };

    // Dès l’affichage du composant, on lance un premier chargement des données
    this.refresh();
  }

  // =====================================================================
  // 🔄 PARTIE 6 — RAFRAÎCHISSEMENT DES DONNÉES
  // =====================================================================
  // Cette méthode appelle l’API backend pour récupérer les données du dashboard.
  // Elle est utilisée au démarrage (dans ngOnInit) et pourrait être reliée à un bouton “Rafraîchir”.
  refresh() {
    this.loading.set(true); // on active l’indicateur de chargement (utile pour afficher un spinner)
    this.error.set(null);   // on efface les erreurs précédentes

    // Appel du backend via ApiService → méthode getDashboardSummary()
    // Ce service fait une requête HTTP GET vers ton API FastAPI.
    this.api.getDashboardSummary().subscribe({
      // ✅ Si l’appel réussit :
      next: (data) => {
        // On stocke les données reçues dans le signal “summary”
        this.summary.set(data);

        // On met à jour le graphique avec les vraies valeurs reçues du backend
        this.pieData = {
          ...this.pieData, // on garde les labels et couleurs inchangés
          datasets: [
            {
              ...this.pieData.datasets[0],
              data: [this.running, this.stopped, this.setup], // nouvelles valeurs réelles
            },
          ],
        };

        // On indique que le chargement est terminé
        this.loading.set(false);
      },

      // ❌ Si l’appel échoue (par ex. API inaccessible)
      error: (err) => {
        console.error(err); // utile pour le débogage dans la console du navigateur
        this.error.set('Erreur lors du chargement du dashboard');
        this.loading.set(false);
      },
    });
  }
}
