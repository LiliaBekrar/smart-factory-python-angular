import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { ApiService, Machine, ActivityItem } from '../../services/api';

type Kpi = { good: number; scrap: number; trs: number };

@Component({
  selector: 'app-machine-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './detail.html',
  styleUrls: ['./detail.scss'],
})
export class MachineDetailComponent implements OnInit {
  loading = signal(false);
  error = signal<string|null>(null);

  machine = signal<Machine|null>(null);
  events  = signal<ActivityItem[]>([]);

  kpiDay  = signal<Kpi | null>(null);
  kpiAll  = signal<Kpi | null>(null);

  readonly tz = 'Europe/Paris';

  constructor(private route: ActivatedRoute, private api: ApiService) {}

  ngOnInit() {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (!id) { this.error.set('Machine invalide'); return; }
    this.fetch(id);
  }

  fetch(id: number) {
    this.loading.set(true); this.error.set(null);

    this.api.getMachine(id).subscribe({
      next: (m) => this.machine.set(m),
      error: () => this.error.set("Impossible de charger la machine"),
    });

    // KPI "journée" = dernières 24h
    this.api.getMachineKpis(id, 24 * 60).subscribe({
      next: (k) => this.kpiDay.set(k),
      error: () => this.error.set("Impossible de charger le KPI 24h"),
    });

    // KPI global = minutes omis
    this.api.getMachineKpis(id).subscribe({
      next: (k) => this.kpiAll.set(k),
      error: () => this.error.set("Impossible de charger le KPI global"),
    });

    // Événements (sans filtre temps), limite 20
    this.api.getMachineActivity(id, undefined, 20).subscribe({
      next: (items) => { this.events.set(items); this.loading.set(false); },
      error: () => { this.error.set("Impossible de charger l'activité"); this.loading.set(false); },
    });
  }
}
