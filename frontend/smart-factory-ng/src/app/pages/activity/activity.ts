import { Component, OnInit, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, ActivityItem, Machine } from '../../services/api';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

type PeriodKey = '1h'|'24h'|'7d'|'30d'|'1y';

@Component({
  selector: 'app-activity',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './activity.html',
  styleUrls: ['./activity.scss']
})
export class ActivityComponent implements OnInit {
  loading = signal(false);
  error = signal<string|null>(null);

  machines = signal<Machine[]>([]);
  items    = signal<ActivityItem[]>([]);

  selectedMachineId = signal<number|0>(0);  // 0 = toutes
  selectedPeriod    = signal<PeriodKey>('1h');

  periods: {key:PeriodKey; label:string; minutes:number}[] = [
    { key:'1h',  label:'Dernière heure', minutes: 60 },
    { key:'24h', label:'24 heures',      minutes: 24*60 },
    { key:'7d',  label:'7 jours',        minutes: 7*24*60 },
    { key:'30d', label:'30 jours',       minutes: 30*24*60 },
    { key:'1y',  label:'1 an',           minutes: 365*24*60 },
  ];

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.loadMachines();
    this.refresh();
  }

  loadMachines() {
    this.api.getMachines().subscribe({
      next: (list) => this.machines.set(list),
      error: () => this.error.set("Impossible de charger les machines")
    });
  }

refresh() {
  this.loading.set(true); this.error.set(null);

  const p = this.periods.find(p => p.key === this.selectedPeriod());
  if (!p) { this.error.set('Période inconnue'); this.loading.set(false); return; }

  const minutes = p.minutes;
  const mid = this.selectedMachineId();
  const done = () => this.loading.set(false);

  const sub = !mid
    ? this.api.getRecentActivities(minutes, 100)
    : this.api.getMachineActivity(mid, minutes, 100);

  sub.subscribe({
    next: (data) => { this.items.set(data); done(); },
    error: () => { this.error.set("Erreur chargement activité refresh"); done(); }
  });
}

}
