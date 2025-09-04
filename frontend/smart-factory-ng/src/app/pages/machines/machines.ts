import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api';

type Machine = {
  id: number;
  name: string;
  code: string;
  status: 'running' | 'stopped' | 'setup';
  target_rate_per_hour: number;
};

@Component({
  selector: 'app-machines',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './machines.html',
  styleUrls: ['./machines.scss'],
})
export class MachinesComponent implements OnInit {
  // state
  loading = signal(false);
  error   = signal<string | null>(null);
  _machines = signal<Machine[]>([]);
  _filter = signal<'all'|'running'|'stopped'|'setup'>('all');

  // dérivés
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

  constructor(private api: ApiService) {}

  ngOnInit() { this.refresh(); }

  refresh() {
    this.loading.set(true); this.error.set(null);
    this.api.getMachines().subscribe({
      next: (data: Machine[]) => { this._machines.set(data ?? []); this.loading.set(false); },
      error: (err) => { console.error(err); this.error.set('Erreur chargement machines'); this.loading.set(false); }
    });
  }

  setFilter(f: 'all'|'running'|'stopped'|'setup') { this._filter.set(f); }

  machineTooltip(m: Machine) {
    return `${m.code} — ${m.name} • ${m.status}`;
  }
}
