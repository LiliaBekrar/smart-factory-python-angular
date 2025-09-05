// src/app/pages/admin/admin.ts
import { Component, OnInit, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ApiService, User } from '../../services/api';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.html',
  styleUrls: ['./admin.scss']
})
export class AdminComponent implements OnInit {
  users = signal<User[]>([]);
  email=''; password=''; role:'admin'|'chef'|'operator'='operator';
  error: string|null = null;

  constructor(private api: ApiService){}

  ngOnInit(){ this.reload(); }

  reload(){ this.api.getUsers().subscribe({ next: u => this.users.set(u) }); }
  add(){
    this.api.createUser({email:this.email, password:this.password, role:this.role}).subscribe({
      next: () => { this.email=''; this.password=''; this.role='operator'; this.reload(); },
      error: () => this.error='Création impossible'
    });
  }
  changeRole(u:User, role:User['role']){ this.api.updateUser(u.id, {role}).subscribe(()=>this.reload()); }
  resetPwd(u:User){ const p = prompt('Nouveau mot de passe pour '+u.email); if(p){ this.api.updateUser(u.id,{password:p}).subscribe(()=>{}) } }
  remove(u:User){ if(confirm('Supprimer '+u.email+' ?')) this.api.deleteUser(u.id).subscribe(()=>this.reload()); }
}
