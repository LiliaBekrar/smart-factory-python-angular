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
  // pour afficher les détails bruts de l’erreur dans l’UI
  errorDetail = signal<any>(null);

  machines = signal<Machine[]>([]);
  items    = signal<ActivityItem[]>([]);

  // 0 = toutes les machines
  selectedMachineId = signal<number | 0>(0);
  selectedPeriod    = signal<PeriodKey>('1h');

  // Affichage en Europe/Paris pour éviter le décalage
  readonly tz = 'Europe/Paris';

  periods: { key: PeriodKey; label: string; minutes: number }[] = [
    { key:'1h',  label:'Dernière heure', minutes: 60 },
    { key:'24h', label:'24 heures',      minutes: 24*60 },
    { key:'7d',  label:'7 jours',        minutes: 7*24*60 },
    { key:'30d', label:'30 jours',       minutes: 30*24*60 },
    { key:'1y',  label:'1 an',           minutes: 365*24*60 },
  ];

  minutes = computed(() =>
    this.periods.find(p => p.key === this.selectedPeriod())?.minutes ?? 60
  );

  constructor(private api: ApiService) {}

  ngOnInit() {
    this.loadMachines();
    this.refresh();
  }

  loadMachines() {
    this.api.getMachines().subscribe({
      next: (list) => this.machines.set(list),
      error: (err) => this.setError('Impossible de charger les machines', err)
    });
  }

  /** Affiche un message lisible + garde un raw detail pour debug à l’écran */
  private setError(prefix: string, err: any) {
    const status = err?.status ? `HTTP ${err.status}` : '';
    const detail =
      err?.error?.detail ??
      err?.error?.message ??
      err?.message ??
      JSON.stringify(err?.error ?? err ?? {}, null, 2);
    const msg = [prefix, status].filter(Boolean).join(' — ');
    console.error('[Activity] Error:', err);
    this.error.set(msg);
    this.errorDetail.set(detail);
  }

  /** Handler propre pour la machine (évite Number() dans le template) */
  onMachineChange(val: number | string | null | undefined) {
    const id = typeof val === 'number' ? val : (parseInt(String(val ?? '0'), 10) || 0);
    this.selectedMachineId.set(id);
    this.refresh();
  }

  /** Handler période */
  onPeriodChange(val: PeriodKey) {
    this.selectedPeriod.set(val);
    this.refresh();
  }

  /** Appelle l’API selon mid/minutes */
  private callApi(mid: number, minutes: number) {
    return mid === 0
      ? this.api.getRecentActivities(minutes, 100)
      : this.api.getMachineActivity(mid, minutes, 100);
  }

  refresh() {
    this.loading.set(true);
    this.error.set(null);
    this.errorDetail.set(null);

    let minutes = Math.max(1, this.minutes());
    let mid = Number(this.selectedMachineId());
    if (!Number.isFinite(mid) || mid < 0) mid = 0;

    // On essaie en cascade si le backend refuse des fenêtres trop larges :
    const fallbacks = [minutes];
    if (minutes > 43200) fallbacks.push(43200); // 30 jours
    if (minutes > 10080) fallbacks.push(10080); // 7 jours
    if (minutes > 1440)  fallbacks.push(1440);  // 24h

    const tryNext = (idx: number) => {
      const m = fallbacks[idx];
      if (m == null) { this.loading.set(false); return; }

      console.debug('[Activity] Fetch', { machineId: mid || 'ALL', minutes: m });
      this.callApi(mid, m).subscribe({
        next: (data) => { this.items.set(data); this.loading.set(false); },
        error: (err) => {
          // si on a encore un fallback, on réessaie
          if (idx + 1 < fallbacks.length) {
            console.warn(`[Activity] Failed @${m}min, retrying fallback`, err);
            tryNext(idx + 1);
          } else {
            this.setError('Erreur chargement activité', err);
            this.loading.set(false);
          }
        }
      });
    };

    tryNext(0);
  }
}
