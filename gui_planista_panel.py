# WM-VERSION: 0.1
# Plik: gui_planista_panel.py
# version: 1.1
# Planista osadzony w glownym obszarze WM.
# 1.1: edycja rzazu i korekt polproduktow; format dlugosci mm (m).

from __future__ import annotations
import os, tempfile, tkinter as tk, webbrowser
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk
import zlecenia_logika as ZL
from gui_planista import _display_date, _iso_date, _open_date_calendar, _work_order_html

def _fmt_qty(value):
    try: n=float(value or 0)
    except Exception: return str(value or '')
    return str(int(n)) if n.is_integer() else f'{n:.3f}'.rstrip('0').rstrip('.')

def _fmt_amount(value, unit=''):
    txt=_fmt_qty(value); u=str(unit or '').strip()
    if u.lower()=='mm':
        try: return f'{txt} mm ({float(value or 0)/1000:g} m)'
        except Exception: pass
    return f'{txt} {u}'.strip()

class PlanistaPanel(ttk.Frame):
    def __init__(self,parent,*,root=None,login=None,rola=None):
        super().__init__(parent,padding=10); self.root=root or parent.winfo_toplevel(); self.login=str(login or ''); self.rola=str(rola or ''); self._orders={}; self._build(); self.refresh()
    def _build(self):
        top=ttk.Frame(self); top.pack(fill='x',pady=(0,10)); ttk.Label(top,text='PLANISTA',style='WM.H1.TLabel').pack(side='left'); ttk.Label(top,text='Termin realizacji zlecenia. Zlecenie określa co i ile wykonać.').pack(side='left',padx=18); ttk.Button(top,text='Odśwież',command=self.refresh).pack(side='right')
        cols=('id','produkt','ilosc','wykonano','pozostalo','termin','status'); self.tree=ttk.Treeview(self,columns=cols,show='headings',height=18)
        labels={'id':'Zlecenie','produkt':'Produkt','ilosc':'Ilość','wykonano':'Wykonano','pozostalo':'Pozostało','termin':'Termin','status':'Status'}; widths={'id':110,'produkt':250,'ilosc':80,'wykonano':90,'pozostalo':90,'termin':120,'status':120}
        for c in cols: self.tree.heading(c,text=labels[c]); self.tree.column(c,width=widths[c],anchor='w')
        self.tree.pack(fill='both',expand=True); self.tree.bind('<Double-1>',lambda _e:self.edit_term())
        b=ttk.Frame(self); b.pack(fill='x',pady=(8,0)); ttk.Button(b,text='Ustaw / zmień termin',command=self.edit_term).pack(side='left'); ttk.Button(b,text='Rzaz / półprodukty…',command=self.edit_production).pack(side='left',padx=6); ttk.Button(b,text='Wykonano…',command=self.report_done).pack(side='left'); ttk.Button(b,text='Pokaż zapotrzebowanie',command=self.show_requirements).pack(side='left',padx=6); ttk.Button(b,text='Drukuj małe zlecenie',command=self.print_work_order).pack(side='left')
    def _selected(self):
        s=self.tree.selection(); return self._orders.get(s[0]) if s else None
    def refresh(self):
        self.tree.delete(*self.tree.get_children()); self._orders={}
        for o in ZL.list_zlecenia():
            oid=str(o.get('id') or '')
            if not oid: continue
            q=float(o.get('ilosc',0) or 0); d=float(o.get('wykonano',0) or 0); self._orders[oid]=o
            self.tree.insert('', 'end', iid=oid, values=(oid,o.get('produkt',''),_fmt_qty(q),_fmt_qty(d),_fmt_qty(max(0,q-min(q,d))),_display_date(o.get('termin','')),o.get('status','')))
    def edit_term(self):
        o=self._selected()
        if not o: messagebox.showinfo('Planista','Wybierz zlecenie.',parent=self); return
        d=tk.Toplevel(self.root); d.title('Termin zlecenia'); d.transient(self.root); d.grab_set(); f=ttk.Frame(d,padding=12); f.pack(fill='both',expand=True); ttk.Label(f,text=f"Zlecenie: {o.get('id')} | Produkt: {o.get('produkt')}").grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,8)); ttk.Label(f,text='Termin:').grid(row=1,column=0,sticky='w'); v=tk.StringVar(value=_display_date(o.get('termin')) or date.today().strftime('%d-%m-%y')); e=tk.Entry(f,textvariable=v,width=16,state='readonly',readonlybackground='#2e7d32',fg='white',relief='solid',bd=1,justify='center'); e.grid(row=1,column=1,sticky='w',padx=(8,0)); ttk.Button(f,text='📅 Kalendarz',command=lambda:_open_date_calendar(d,v)).grid(row=1,column=2,sticky='w',padx=(8,0))
        def save():
            try: ZL.update_zlecenie(o['id'],termin=_iso_date(v.get()),kto=self.login or 'system')
            except Exception as x: messagebox.showerror('Planista',str(x),parent=d); return
            d.destroy(); self.refresh()
        ttk.Button(f,text='Zapisz',command=save).grid(row=2,column=2,sticky='e',pady=(10,0))
    def edit_production(self):
        o=self._selected()
        if not o: messagebox.showinfo('Planista','Wybierz zlecenie.',parent=self); return
        d=tk.Toplevel(self.root); d.title('Rzaz i ilości półproduktów'); d.transient(self.root); d.grab_set(); f=ttk.Frame(d,padding=12); f.pack(fill='both',expand=True)
        ttk.Label(f,text=f"Zlecenie {o.get('id')} — {o.get('produkt')}",font=('Arial',11,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,8)); ttk.Label(f,text='Rzaz na sztukę [mm]:').grid(row=1,column=0,sticky='w'); cut=tk.StringVar(value=_fmt_qty(o.get('rzaz_mm',2))); ttk.Entry(f,textvariable=cut,width=10).grid(row=1,column=1,sticky='w')
        ttk.Label(f,text='Półprodukt').grid(row=2,column=0,sticky='w',pady=(10,2)); ttk.Label(f,text='Wyliczono').grid(row=2,column=1,sticky='w'); ttk.Label(f,text='Do zlecenia').grid(row=2,column=2,sticky='w')
        vars={}
        for r,(code,rec) in enumerate((o.get('plan_polprodukty') or {}).items(),start=3):
            if not isinstance(rec,dict): continue
            ttk.Label(f,text=str(rec.get('nazwa') or code)).grid(row=r,column=0,sticky='w',padx=(0,16)); ttk.Label(f,text=_fmt_qty(rec.get('wyliczone',rec.get('potrzeba',0)))).grid(row=r,column=1,sticky='w'); v=tk.StringVar(value=_fmt_qty(rec.get('potrzeba',0))); vars[code]=v; ttk.Entry(f,textvariable=v,width=12).grid(row=r,column=2,sticky='w',pady=1)
        def save():
            try:
                cv=float(cut.get().replace(',','.')); ov={k:float(v.get().replace(',','.')) for k,v in vars.items()};
                if cv<0 or any(x<0 for x in ov.values()): raise ValueError('Rzaz i ilości nie mogą być ujemne.')
                ZL.update_zlecenie(o['id'],rzaz_mm=cv,korekty_polproduktow=ov,kto=self.login or 'system')
            except Exception as x: messagebox.showerror('Planista',str(x),parent=d); return
            d.destroy(); self.refresh()
        ttk.Button(f,text='Zapisz i przelicz',command=save).grid(row=999,column=2,sticky='e',pady=(12,0))
    def report_done(self):
        o=self._selected()
        if not o: messagebox.showinfo('Planista','Wybierz zlecenie.',parent=self); return
        d=tk.Toplevel(self.root); d.title('Rozlicz wykonanie'); d.transient(self.root); d.grab_set(); f=ttk.Frame(d,padding=12); f.pack(fill='both',expand=True); cur=float(o.get('wykonano',0) or 0); ttk.Label(f,text=f'Dotychczas wykonano: {_fmt_qty(cur)}').grid(row=0,column=0,columnspan=2,sticky='w'); ttk.Label(f,text='Nowa łączna ilość wykonana:').grid(row=1,column=0,sticky='w',pady=(8,0)); v=tk.StringVar(value=_fmt_qty(cur)); ttk.Entry(f,textvariable=v,width=16).grid(row=1,column=1,padx=(8,0),pady=(8,0))
        def save():
            try: ZL.report_wykonano(o['id'],float(v.get().replace(',','.')),kto=self.login or 'system')
            except Exception as x: messagebox.showerror('Rozliczenie',str(x),parent=d); return
            d.destroy(); self.refresh()
        ttk.Button(f,text='Zapisz',command=save).grid(row=2,column=1,sticky='e',pady=(10,0))
    def show_requirements(self):
        o=self._selected()
        if not o: messagebox.showinfo('Planista','Wybierz zlecenie.',parent=self); return
        lines=[]
        for code,r in (o.get('plan_polprodukty') or {}).items():
            if isinstance(r,dict): lines.append(f"{r.get('nazwa') or code}: potrzeba {_fmt_qty(r.get('potrzeba',0))} | z magazynu {_fmt_qty(r.get('z_magazynu',0))} | do wykonania {_fmt_qty(r.get('do_wykonania',0))}")
        raw=o.get('zapotrzebowanie_surowce') or {}
        if raw: lines += ['', 'SUROWIEC:']+[f"{k}: {_fmt_amount(v.get('ilosc',0),v.get('jednostka',''))}" for k,v in raw.items() if isinstance(v,dict)]
        if o.get('braki'): lines += ['', 'BRAKI SUROWCA:']+[f"{r.get('nazwa') or r.get('kod')}: brakuje {_fmt_amount(r.get('brakuje',0),r.get('jednostka',''))}" for r in o['braki']]
        messagebox.showinfo('Zapotrzebowanie','\n'.join(lines) if lines else 'Brak danych.',parent=self)
    def print_work_order(self):
        o=self._selected()
        if not o: messagebox.showinfo('Planista','Wybierz zlecenie.',parent=self); return
        try:
            p=Path(tempfile.gettempdir())/'WarsztatMenager'/'wydruki'; p.mkdir(parents=True,exist_ok=True); fn=p/f"zlecenie_{o.get('id','')}.html"; fn.write_text(_work_order_html(o),encoding='utf-8'); os.startfile(str(fn)) if os.name=='nt' else webbrowser.open(fn.as_uri())
        except Exception as x: messagebox.showerror('Wydruk',f'Nie udało się przygotować wydruku:\n{x}',parent=self)

def panel_planista(root,frame,login=None,rola=None):
    p=PlanistaPanel(frame,root=root,login=login,rola=rola); p.pack(fill='both',expand=True); return p
