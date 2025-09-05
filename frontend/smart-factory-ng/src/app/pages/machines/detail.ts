import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { ApiService, Machine, ActivityItem } from '../../services/api';

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

  constructor(private route: ActivatedRoute, private api: ApiService) {}

  ngOnInit() {
    const id = Number(this.route.snapshot.paramMap.get('id'));
    if (!id) { this.error.set('Machine invalide'); return; }
    this.fetch(id);
  }

  fetch(id: number) {
    this.loading.set(true); this.error.set(null);
    // charge la machine + derniers événements (2 appels en //)
    this.api.getMachine(id).subscribe({
      next: (m) => this.machine.set(m),
      error: () => this.error.set("Impossible de charger la machine"),
    });
    this.api.getMachineActivity(id, /*minutes*/ 60, /*limit*/ 20).subscribe({
      next: (items) => { this.events.set(items); this.loading.set(false); },
      error: () => { this.error.set("Impossible de charger l'activité"); this.loading.set(false); },
    });
  }
}
