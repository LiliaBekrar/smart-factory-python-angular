// src/app/app.config.ts
import { ApplicationConfig, LOCALE_ID } from '@angular/core';
import { provideRouter } from '@angular/router';
import { routes } from './app.routes';
import { provideHttpClient, withInterceptors } from '@angular/common/http';
import { authInterceptor } from './services/auth.interceptor';


import { registerLocaleData } from '@angular/common';
import localeFr from '@angular/common/locales/fr';

// 👇 Charts (ng2-charts + Chart.js registerables)
import { provideCharts, withDefaultRegisterables } from 'ng2-charts';

registerLocaleData(localeFr); // enregistre les formats FR (dates, nombres, etc.)

export const appConfig: ApplicationConfig = {
  providers: [
    provideRouter(routes),
    provideHttpClient(withInterceptors([authInterceptor])),
    { provide: LOCALE_ID, useValue: 'fr-FR' }, // force la locale FR

    // 👇 nécessaire pour <canvas baseChart> (Chart.js)
    provideCharts(withDefaultRegisterables()),
  ],
};
