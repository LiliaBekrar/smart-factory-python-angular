// ======================================================================
// 🌍 FICHIER : src/app/pages/machines/machines.ts
// ----------------------------------------------------------------------
// Ce composant Angular gère l'écran "Parc Machines" :
//  - affiche la liste des machines (vue "bulles" ou "table")
//  - permet de filtrer par statut (all / running / stopped / setup)
//  - création / édition / suppression d'une machine
//  - lit un paramètre d'URL (?status=running|stopped|setup) pour appliquer
//    automatiquement un filtre (ex: lien venant du donut du dashboard).
//
// 🔗 Liens importants vers d'autres fichiers :
//  - HTML associé (la vue) : src/app/pages/machines/machines.html
//  - Styles SCSS :         : src/app/pages/machines/machines.scss
//  - Service API (HTTP)    : src/app/services/api.ts  (définit `ApiService` et le type `Machine`)
//  - Service Auth          : src/app/services/auth.service.ts (définit `AuthService`)
//  - Router Angular        : configuration de routes dans src/app/app.routes.ts (ou équivalent)
//
// 🧠 Notions :
//  - "Composant" = un bloc d'interface avec son code + son HTML + ses styles.
//  - "Signal" Angular = variable réactive (la vue se met à jour auto quand la valeur change).
//  - "Service" = classe partagée (ex: `ApiService` pour parler au backend).
// ======================================================================

import { Component, OnInit, OnDestroy, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';

// ⛓️ Service interne qui parle à ton backend FastAPI (fichier : src/app/services/api.ts)
//  - expose des méthodes comme getMachines(), createMachine(), updateMachine(), deleteMachine()
//  - exporte aussi le type `Machine` (forme d'un objet machine renvoyé par l'API)
import { ApiService, Machine } from '../../services/api';

// 🔐 Service d'authentification (fichier : src/app/services/auth.service.ts)
//  - expose isLoggedIn(), role() ... pour gérer droits d'accès
import { AuthService } from '../../services/auth.service';

// 🔤 Module pour <form>, [(ngModel)] etc. utilisé dans le template HTML
import { FormsModule } from '@angular/forms';

// 🔗 Directive pour les liens internes Angular dans le HTML (ex: [routerLink]="['/machines', m.id]")
import { RouterLink, ActivatedRoute, Router } from '@angular/router';

// 🔁 Utilisé pour se désabonner proprement à la fin de vie du composant
import { Subscription } from 'rxjs';

// ----------------------------------------------------------------------
// ✍️ Type local pour le formulaire de création (brouillon machine)
// ----------------------------------------------------------------------
type MachineDraft = {
  name: string;
  code: string;
  status: 'running' | 'stopped' | 'setup';
  target_rate_per_hour: number;
};

// ======================================================================
// 🧩 DÉCLARATION DU COMPOSANT
// ======================================================================
@Component({
  selector: 'app-machines',          // <app-machines> dans le HTML parent
  standalone: true,                  // Composant autonome (Angular 16+)
  imports: [CommonModule, FormsModule, RouterLink], // Modules/direc. utilisés dans machines.html
  templateUrl: './machines.html',    // Vue (le "template")
  styleUrls: ['./machines.scss'],    // Styles associés à cette page
})
export class MachinesComponent implements OnInit, OnDestroy {
  // --------------------------------------------------------------------
  // 🧭 Le constructeur "injecte" les services dont on a besoin.
  //  - ApiService : pour parler au backend FastAPI (R/W machines)
  //  - AuthService : pour savoir qui est connecté et ses droits
  //  - ActivatedRoute + Router : lire/écrire paramètres d'URL (?status=)
  // --------------------------------------------------------------------
  constructor(
    private api: ApiService,
    public auth: AuthService,
    private route: ActivatedRoute,
    private router: Router
  ) {}

  // ====================================================================
  // 👁️ Vue : mode d'affichage "bulles" (par défaut) ou "table"
  // --------------------------------------------------------------------
  // Cette valeur est lue par le HTML (machines.html) pour afficher
  // soit le nuage de bulles, soit la table.
  // ====================================================================
  view: 'bubbles' | 'table' = 'bubbles';

  // ====================================================================
  // ⚙️ ÉTATS DE BASE (réactifs via `signal()`)
  // --------------------------------------------------------------------
  // loading : pour afficher "Chargement…" dans la vue
  // error   : pour montrer un message d'erreur utilisateur
  // _machines : liste brute des machines (renvoyée par l'API)
  // _filter   : filtre courant (all / running / stopped / setup)
  // ====================================================================
  loading   = signal(false);
  error     = signal<string | null>(null);
  _machines = signal<Machine[]>([]);
  _filter   = signal<'all'|'running'|'stopped'|'setup'>('all');

  // ====================================================================
  // 🧮 DÉRIVÉS / "computed" (calculés automatiquement)
  // --------------------------------------------------------------------
  // Ces valeurs se recalculent dès que _machines() ou _filter() change.
  // Le template (machines.html) les lit pour se mettre à jour.
  // ====================================================================
  machines = computed(() => this._machines());
  filter   = computed(() => this._filter());

  // Listes par statut (utilisées pour les gros cercles / stats rapides)
  running  = computed(() => this._machines().filter(m => m.status === 'running'));
  stopped  = computed(() => this._machines().filter(m => m.status === 'stopped'));
  setup    = computed(() => this._machines().filter(m => m.status === 'setup'));

  // Liste filtrée (utilisée par l'affichage principal)
  filtered = computed(() => {
    const f = this._filter();
    const list = this._machines();
    if (f === 'all') return list;
    return list.filter(m => m.status === f);
  });

  // ====================================================================
  // 🆕 FORMULAIRE DE CRÉATION (brouillon)
  // --------------------------------------------------------------------
  // Le HTML (machines.html) lie les champs du formulaire à `newMachine`
  // via [(ngModel)] avec des helpers updateNew() ci-dessous.
  // ====================================================================
  newMachine = signal<MachineDraft>({
    name: '', code: '', status: 'setup', target_rate_per_hour: 0,
  });

  // ====================================================================
  // ✏️ ÉDITION EN LIGNE (dans la table)
  // --------------------------------------------------------------------
  // editId   : id de la machine en cours d'édition (sinon null)
  // editForm : les champs modifiables (liés au formulaire de la ligne)
  // ====================================================================
  editId   = signal<number | null>(null);
  editForm = signal<Partial<Machine>>({});

  // ====================================================================
  // 🔗 Gestion du paramètre d'URL ?status=...
  // --------------------------------------------------------------------
  // Objectif :
  //  - Au chargement, si l'URL contient ?status=running|stopped|setup,
  //    on applique automatiquement ce filtre.
  //  - Quand l'utilisateur clique sur un bouton filtre, on met aussi
  //    l'URL à jour (pour partage, favoris, etc.).
  // ====================================================================
  private qpSub?: Subscription; // on s'abonnera aux query params et se désabonnera dans ngOnDestroy()

  // ====================================================================
  // 🚀 Cycle de vie : au montage du composant
  // --------------------------------------------------------------------
  // 1) On lit/observe l'URL pour appliquer le filtre initial
  // 2) On charge la liste des machines depuis l'API
  // ====================================================================
  ngOnInit() {
    // 1) Lire les query params (?status=...) et appliquer le filtre
    this.qpSub = this.route.queryParamMap.subscribe((params) => {
      const raw = (params.get('status') ?? 'all').toLowerCase();
      const allowed = ['all', 'running', 'stopped', 'setup'] as const;
      const isAllowed = (allowed as readonly string[]).includes(raw);
      this._filter.set((isAllowed ? raw : 'all') as typeof allowed[number]);
      // NB : le HTML lit `filter()` pour afficher le bouton actif et la liste filtrée
    });

    // 2) Charger depuis l'API
    this.refresh();
  }

  // ====================================================================
  // 🧹 Cycle de vie : au démontage (bonne pratique)
  // --------------------------------------------------------------------
  ngOnDestroy() {
    this.qpSub?.unsubscribe();
  }

  // ====================================================================
  // 🔄 Charger/rafraîchir la liste des machines depuis l'API
  // --------------------------------------------------------------------
  // Dépend de ApiService.getMachines() (src/app/services/api.ts)
  // ====================================================================
  refresh() {
    this.loading.set(true);
    this.error.set(null);

    this.api.getMachines().subscribe({
      next: (data) => {
        // data est un tableau de Machine[] (ou undefined en cas edge)
        this._machines.set(data ?? []);
        this.loading.set(false);
      },
      error: (err) => {
        console.error(err);
        this.error.set('Erreur chargement machines');
        this.loading.set(false);
      }
    });
  }

  // ====================================================================
  // 🎛️ Changer le filtre depuis le code
  // --------------------------------------------------------------------
  // 👉 Astuce UX : on met aussi l'URL à jour (sans recharger la page)
  // afin que /machines?status=stopped reflète le filtre courant.
  // --------------------------------------------------------------------
  setFilter(f: 'all'|'running'|'stopped'|'setup') {
    this._filter.set(f);
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { status: f === 'all' ? null : f }, // supprime le param si "all"
      queryParamsHandling: 'merge', // conserve d'autres éventuels params
    });
  }

  // ====================================================================
  // 🛈 Infobulle (tooltips) pour les bulles/lignes (utilisé dans machines.html)
  // --------------------------------------------------------------------
  // Montre : Nom + Code + Statut lisible + cadence/h si > 0
  // ====================================================================
  machineTooltip(m: Machine): string {
    const statusLabel: Record<Machine['status'], string> = {
      running: 'En marche',
      stopped: 'À l’arrêt',
      setup:   'Réglage',
    };
    const trph = m.target_rate_per_hour > 0 ? ` • ${m.target_rate_per_hour} pcs/h` : '';
    return `${m.name} (${m.code}) • ${statusLabel[m.status]}${trph}`;
  }

  // ====================================================================
  // 🔒 Règles d'affichage : qui peut éditer ?
  // --------------------------------------------------------------------
  // Dépend d'AuthService.role() (src/app/services/auth.service.ts)
  //  - ex : 'admin' et 'chef' peuvent modifier
  // ====================================================================
  canEdit(_m: Machine) {
    const role = this.auth.role();
    return role === 'admin' || role === 'chef';
  }

  // ====================================================================
  // 🔧 Helpers de binding pour les formulaires [(ngModel)] (création/édition)
  // --------------------------------------------------------------------
  // Ces fonctions mettent à jour proprement les "signals" quand un champ change.
  // ====================================================================
  updateNew<K extends keyof MachineDraft>(key: K, value: MachineDraft[K]) {
    this.newMachine.update(m => ({ ...m, [key]: value }));
  }

  updateEdit<K extends keyof Machine>(key: K, value: Machine[K]) {
    this.editForm.update(m => ({ ...m, [key]: value }));
  }

  // ====================================================================
  // ➕ Créer une machine
  // --------------------------------------------------------------------
  // Dépend de ApiService.createMachine(form) (src/app/services/api.ts)
  // Règles simples :
  //  - l'utilisateur doit être connecté (AuthService.isLoggedIn())
  //  - name et code obligatoires
  // Après succès :
  //  - on réinitialise le brouillon
  //  - on recharge la liste
  // ====================================================================
  create() {
    if (!this.auth.isLoggedIn()) {
      this.error.set('Connecte-toi pour créer.');
      return;
    }
    const form = this.newMachine();
    if (!form.name || !form.code) {
      this.error.set('Nom et code sont requis.');
      return;
    }

    this.loading.set(true);
    this.api.createMachine(form).subscribe({
      next: () => {
        this.loading.set(false);
        // reset du formulaire de création
        this.newMachine.set({ name:'', code:'', status:'setup', target_rate_per_hour:0 });
        // recharge la liste à jour
        this.refresh();
      },
      error: (e) => {
        this.loading.set(false);
        this.error.set(e?.error?.detail || 'Création impossible');
      }
    });
  }

  // ====================================================================
  // ✏️ Édition "inline" : démarrer/annuler/enregistrer
  // --------------------------------------------------------------------
  // startEdit : met la ligne en mode édition (remplit editForm)
  // cancelEdit : annule l'édition en cours
  // saveEdit : envoie les modifs à l'API, puis recharge la liste
  // ====================================================================
  startEdit(m: Machine) {
    this.editId.set(m.id);
    this.editForm.set({
      name: m.name,
      code: m.code,
      status: m.status,
      target_rate_per_hour: m.target_rate_per_hour
    });
  }

  cancelEdit() {
    this.editId.set(null);
    this.editForm.set({});
  }

  saveEdit(id: number) {
    this.loading.set(true);
    this.api.updateMachine(id, this.editForm()).subscribe({
      next: () => {
        this.loading.set(false);
        this.editId.set(null);
        this.refresh();
      },
      error: (e) => {
        this.loading.set(false);
        this.error.set(e?.error?.detail || 'Mise à jour impossible');
      }
    });
  }

  // ====================================================================
  // 🗑️ Supprimer une machine
  // --------------------------------------------------------------------
  // Demande confirmation, appelle l'API, recharge la liste.
  // ====================================================================
  remove(id: number) {
    if (!confirm('Supprimer cette machine ?')) return;
    this.loading.set(true);
    this.api.deleteMachine(id).subscribe({
      next: () => {
        this.loading.set(false);
        this.refresh();
      },
      error: (e) => {
        this.loading.set(false);
        this.error.set(e?.error?.detail || 'Suppression impossible');
      }
    });
  }
}
