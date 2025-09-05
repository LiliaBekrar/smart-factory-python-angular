import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard';
import { MachinesComponent } from './pages/machines/machines';
import { ActivityComponent } from './pages/activity/activity';
import { MachineDetailComponent } from './pages/machines/detail';

export const routes: Routes = [
  { path: '', component: DashboardComponent, title: 'Dashboard', pathMatch: 'full' },
  { path: 'machines', component: MachinesComponent, title: 'Parc Machines' },
  { path: 'machines/:id', component: MachineDetailComponent, title: 'Machine' }, // 👈 détail
  { path: 'activity', component: ActivityComponent, title: 'Activité' },          // 👈 activité
  { path: '**', redirectTo: '' },
];
