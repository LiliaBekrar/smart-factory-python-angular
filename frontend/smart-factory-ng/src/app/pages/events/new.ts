// src/app/pages/events/new.ts
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService, Machine, EventCreate } from '../../services/api'; // <= importe EventCreate
import { Router } from '@angular/router';

@Component({
  selector: 'app-event-new',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './new.html',
  styleUrls: ['./new.scss'],
})
export class EventNewComponent implements OnInit {
  machines = signal<Machine[]>([]);
  loading = signal(false);
  error   = signal<string|null>(null);
  success = signal(false);

  // modèle "souple" pour le formulaire (peut contenir null)
  payload: {
    machine_id: number | null;
    work_order_id?: number | null;
    event_type: 'good'|'scrap'|'stop';
    qty: number;
    notes?: string | null;
    happened_at?: string | null;
  } = {
    machine_id: null,
    event_type: 'good',
    qty: 1,
    notes: null,
    work_order_id: null,
    happened_at: null,
  };

  constructor(private api: ApiService, private router: Router) {}

  ngOnInit() {
    this.api.getMachines().subscribe({
      next: (list) => this.machines.set(list),
      error: () => this.error.set('Impossible de charger les machines'),
    });
  }

  onTypeChange() {
    if (this.payload.event_type === 'stop') this.payload.qty = 0;
    else if (this.payload.qty === 0) this.payload.qty = 1;
  }

  reset() {
    this.payload = { machine_id: null, event_type: 'good', qty: 1, notes: null, work_order_id: null, happened_at: null };
    this.error.set(null);
    this.success.set(false);
  }

  submit() {
    if (this.payload.machine_id == null) {  // <= vérif non-null
      this.error.set('Sélectionne une machine.');
      return;
    }

    this.loading.set(true); this.error.set(null); this.success.set(false);

    // ✅ On construit un payload conforme à EventCreate
    const finalPayload: EventCreate = {
      machine_id: this.payload.machine_id!,                // <= garanti non-null par la vérif
      work_order_id: this.payload.work_order_id ?? null,
      event_type: this.payload.event_type,
      qty: Number(this.payload.qty),                       // <= s’assure que c’est bien un number
      notes: this.payload.notes ?? null,
      happened_at: this.payload.happened_at ?? null,
    };

    this.api.createEvent(finalPayload).subscribe({
      next: () => {
        this.loading.set(false);
        this.success.set(true);
        setTimeout(() => this.router.navigate(['/activity']), 600);
      },
      error: (err) => {
        this.loading.set(false);
        console.error(err);
        this.error.set('Erreur lors de la création de l’événement.');
      },
    });
  }
}
