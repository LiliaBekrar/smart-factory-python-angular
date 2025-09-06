// src/app/pages/machines/machines.ts
import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, Machine } from '../../services/api';
import { AuthService } from '../../services/auth.service';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

type MachineDraft = {
  name: string;
  code: string;
  status: 'running' | 'stopped' | 'setup';
  target_rate_per_hour: number;
};

@Component({
  selector: 'app-machines',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './machines.html',
  styleUrls: ['./machines.scss'],
})
export class MachinesComponent implements OnInit {
  constructor(private api: ApiService, public auth: AuthService) {}

  // ----- vue (bulles / table)
  view: 'bubbles' | 'table' = 'bubbles';

  // ----- state de base
  loading = signal(false);
  error   = signal<string | null>(null);
  _machines = signal<Machine[]>([]);
  _filter = signal<'all'|'running'|'stopped'|'setup'>('all');

  // ----- dérivés / helpers
  machines = computed(() => this._machines());
  filter   = computed(() => this._filter());

  running  = computed(() => this._machines().filter(m => m.status === 'running'));
  stopped  = computed(() => this._machines().filter(m => m.status === 'stopped'));
  setup    = computed(() => this._machines().filter(m => m.status === 'setup'));

  filtered = computed(() => {
    const f = this._filter();
    const list = this._machines();
    if (f === 'all') return list;
    return list.filter(m => m.status === f);
  });

  // ----- création
  newMachine = signal<MachineDraft>({
    name: '', code: '', status: 'setup', target_rate_per_hour: 0,
  });

  // ----- édition en ligne
  editId = signal<number | null>(null);
  editForm = signal<Partial<Machine>>({});

  ngOnInit() { this.refresh(); }

  refresh() {
    this.loading.set(true); this.error.set(null);
    this.api.getMachines().subscribe({
      next: (data) => { this._machines.set(data ?? []); this.loading.set(false); },
      error: (err) => { console.error(err); this.error.set('Erreur chargement machines'); this.loading.set(false); }
    });
  }

  setFilter(f: 'all'|'running'|'stopped'|'setup') { this._filter.set(f); }

  machineTooltip(m: Machine): string {
  const statusLabel: Record<Machine['status'], string> = {
    running: 'En marche',
    stopped: 'À l’arrêt',
    setup:   'Réglage',
  };
  const trph = m.target_rate_per_hour > 0 ? ` • ${m.target_rate_per_hour} pcs/h` : '';
  return `${m.name} (${m.code}) • ${statusLabel[m.status]}${trph}`;
}

  // ----- règles d'affichage des actions
  canEdit(_m: Machine) {
    // Simplifié pour éviter les erreurs de types (pas besoin de created_by ici)
    const role = this.auth.role();
    return role === 'admin' || role === 'chef';
  }

  // ----- helpers de binding (signals + ngModel)
  updateNew<K extends keyof MachineDraft>(key: K, value: MachineDraft[K]) {
    this.newMachine.update(m => ({ ...m, [key]: value }));
  }

  updateEdit<K extends keyof Machine>(key: K, value: Machine[K]) {
    this.editForm.update(m => ({ ...m, [key]: value }));
  }

  // ----- création
  create() {
    if (!this.auth.isLoggedIn()) { this.error.set('Connecte-toi pour créer.'); return; }
    const form = this.newMachine();
    if (!form.name || !form.code) { this.error.set('Nom et code sont requis.'); return; }

    this.loading.set(true);
    this.api.createMachine(form).subscribe({
      next: () => {
        this.loading.set(false);
        this.newMachine.set({ name:'', code:'', status:'setup', target_rate_per_hour:0 });
        this.refresh();
      },
      error: (e) => { this.loading.set(false); this.error.set(e?.error?.detail || 'Création impossible'); }
    });
  }

  // ----- édition inline
  startEdit(m: Machine) {
    this.editId.set(m.id);
    this.editForm.set({
      name: m.name,
      code: m.code,
      status: m.status,
      target_rate_per_hour: m.target_rate_per_hour
    });
  }
  cancelEdit() { this.editId.set(null); this.editForm.set({}); }

  saveEdit(id: number) {
    this.loading.set(true);
    this.api.updateMachine(id, this.editForm()).subscribe({
      next: () => { this.loading.set(false); this.editId.set(null); this.refresh(); },
      error: (e) => { this.loading.set(false); this.error.set(e?.error?.detail || 'Mise à jour impossible'); }
    });
  }

  // ----- suppression
  remove(id: number) {
    if (!confirm('Supprimer cette machine ?')) return;
    this.loading.set(true);
    this.api.deleteMachine(id).subscribe({
      next: () => { this.loading.set(false); this.refresh(); },
      error: (e) => { this.loading.set(false); this.error.set(e?.error?.detail || 'Suppression impossible'); }
    });
  }
}
