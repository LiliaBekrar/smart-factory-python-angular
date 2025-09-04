import { Component, OnInit, computed, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api';

type Machine = {
  id: number;
  name: string;
  code: string;
  status: 'running' | 'stopped' | 'setup' | string;
  target_rate_per_hour: number;
};

@Component({
  selector: 'app-machines',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './machines.html',
  styleUrl: './machines.scss',
})
export class Machines implements OnInit {
  // état UI
  loading = signal(false);
  error = signal<string | null>(null);

  // données
  machines = signal<Machine[]>([]);

  // filtre courant (all / running / stopped / setup)
  filter = signal<'all' | 'running' | 'stopped' | 'setup'>('all');

  // dérivés (computed)
  running = computed(() => this.machines().filter(m => m.status === 'running'));
  stopped = computed(() => this.machines().filter(m => m.status === 'stopped'));
  setup   = computed(() => this.machines().filter(m => m.status === 'setup'));

  filtered = computed(() => {
    const f = this.filter();
    const list = this.machines();
    return f === 'all' ? list : list.filter(m => m.status === f);
  });

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.refresh();
  }

  refresh(): void {
    this.loading.set(true);
    this.error.set(null);

    this.api.getMachines().subscribe({
      next: (res: any) => {
        // On trie par code pour un rendu stable
        const sorted = [...res].sort((a, b) => (a.code || '').localeCompare(b.code || ''));
        this.machines.set(sorted);
        this.loading.set(false);
      },
      error: (err) => {
        console.error(err);
        this.error.set(err?.error?.detail || 'Impossible de charger les machines');
        this.loading.set(false);
      }
    });
  }

  setFilter(f: 'all' | 'running' | 'stopped' | 'setup') {
    this.filter.set(f);
  }

  // petite aide pour le titre dans la bulle
  machineTooltip(m: Machine): string {
    const rate = m.target_rate_per_hour ?? 0;
    return `${m.name} (${m.code}) • ${m.status.toUpperCase()} • Cible ${rate}/h`;
  }
}
