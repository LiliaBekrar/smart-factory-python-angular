import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard';
import { MachinesComponent } from './pages/machines/machines';

export const routes: Routes = [
  { path: '', component: DashboardComponent },
  { path: 'machines', component: MachinesComponent },
  // { path: 'activity', loadComponent: () => import('./pages/activity/activity').then(m => m.ActivityComponent) },
];
