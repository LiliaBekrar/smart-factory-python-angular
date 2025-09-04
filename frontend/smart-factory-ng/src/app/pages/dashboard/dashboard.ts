import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService } from '../../services/api';
import { BaseChartDirective } from 'ng2-charts';
import { ChartData, ChartOptions, ChartType } from 'chart.js';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, BaseChartDirective],
  templateUrl: './dashboard.html',
})
export class DashboardComponent implements OnInit {
  loading = signal(false);
  error   = signal<string | null>(null);
  summary = signal<any>(null);

  get total()   { return this.summary()?.kpis?.total_machines ?? 0; }
  get running() { return this.summary()?.kpis?.running ?? 0; }
  get stopped() { return this.summary()?.kpis?.stopped ?? 0; }
  get setup()   { return Math.max(0, this.total - this.running - this.stopped); }
  get trs()     { return this.summary()?.kpis?.trs_avg_last_hour ?? 0; }

  pieType: ChartType = 'doughnut';
  pieData: ChartData<'doughnut'> = {
    labels: ['Running', 'Stopped', 'Setup'],
    datasets: [{ data: [0, 0, 0], backgroundColor: ['#1DB954', '#E03131', '#FFB020'] }]
  };
  pieOptions: ChartOptions<'doughnut'> = {
    cutout: '70%',
    plugins: { legend: { display: false } },
    animation: { animateRotate: true, duration: 600 }
  };

  constructor(private api: ApiService) {}
  ngOnInit() { this.refresh(); }

  refresh() {
    this.loading.set(true); this.error.set(null);
    this.api.getDashboardSummary().subscribe({
      next: (data) => {
        this.summary.set(data);
        this.pieData = {
          ...this.pieData,
          datasets: [{ ...this.pieData.datasets[0], data: [this.running, this.stopped, this.setup] }]
        };
        this.loading.set(false);
      },
      error: (err) => { console.error(err); this.error.set('Erreur chargement dashboard'); this.loading.set(false); }
    });
  }
}
