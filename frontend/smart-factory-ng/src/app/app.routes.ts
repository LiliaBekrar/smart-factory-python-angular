import { Routes } from '@angular/router';
import { Dashboard } from './pages/dashboard/dashboard';
import { Machines } from './pages/machines/machines';

export const routes: Routes = [
  { path: 'dashboard', component: Dashboard },
  { path: 'machines',  component: Machines },
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  { path: '**', redirectTo: 'dashboard' },
];
