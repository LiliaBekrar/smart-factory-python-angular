import { Routes } from '@angular/router';
import { DashboardComponent } from './pages/dashboard/dashboard';
import { MachinesComponent } from './pages/machines/machines';
import { ActivityComponent } from './pages/activity/activity';
import { MachineDetailComponent } from './pages/machines/detail';
import { LoginComponent } from './pages/login/login';
import { AdminComponent } from './pages/admin/admin';
import { EventNewComponent } from './pages/events/new';
// import { adminGuard } from './guards/admin.guard';

export const routes: Routes = [
  { path: '', component: DashboardComponent, title: 'Dashboard', pathMatch: 'full' },
  { path: 'machines', component: MachinesComponent, title: 'Parc Machines' },
  { path: 'machines/:id', component: MachineDetailComponent, title: 'Machine' },
  { path: 'activity', component: ActivityComponent, title: 'Activité' },
  { path: 'events/new', component: EventNewComponent, title: 'Nouvel événement' },

  // protégé
  { path: 'admin', component: AdminComponent, title: 'Administration'},

  { path: 'login', component: LoginComponent, title: 'Connexion' },
  { path: '**', redirectTo: '' },
];
