"""Side-by-side plan iteration comparison against the existing course constraints."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from embrace_core import PlanComparison, STRUCTURES, fmt, status, positive_dose, best_metric_slots

from embrace_import import import_with_volumes
from embrace_theme import BG, SURFACE, ALT, HEADER, INK, MUTED, BLUE, INPUT_INK, COLORS


FRAME = '#202326'


class ComparisonTab(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=FRAME)
        self.app=app
        self.model=PlanComparison()
        self.results={}
        self.volumes={}
        self.physical={}
        self.headings=[]
        self.best_cells={}
        top=tk.Frame(self,bg=FRAME)
        top.pack(fill='x',padx=12,pady=(12,10))
        tk.Label(top,text=app.course.title+'  Plan Comparison',bg=FRAME,fg='white',font=('Arial',22,'bold')).pack(side='left')
        self.patient=tk.Label(top,bg=FRAME,fg='white',font=('Arial',10))
        self.patient.pack(side='right')
        control=tk.Frame(self,bg=BG,padx=8,pady=6)
        control.pack(fill='x',padx=12,pady=3)
        tk.Label(control,text='Repeat each plan for',bg=BG,fg=INK,font=('Arial',10)).pack(side='left')
        self.count=tk.StringVar(value=app.count.get())
        count=ttk.Combobox(control,textvariable=self.count,values=['3 Fx','4 Fx','5 Fx'],state='readonly',width=5)
        count.pack(side='left',padx=6)
        count.bind('<<ComboboxSelected>>',self.commit_prescription)
        self.prescription_gy=7.0
        self.prescription_var=tk.StringVar(value='7.0')
        self.prescription_displayed='7.0'
        rx=tk.Entry(control,textvariable=self.prescription_var,bg=BLUE,fg=INPUT_INK,
                    width=5,justify='center',relief='flat',borderwidth=0,highlightthickness=1,
                    highlightbackground=BLUE,highlightcolor='#327ca5',font=('Arial',10))
        rx.pack(side='left',padx=(8,3))
        rx.bind('<Return>',self.commit_prescription)
        rx.bind('<FocusOut>',self.commit_prescription)
        tk.Label(control,text='Gy / Fx',bg=BG,fg=INK,font=('Arial',10)).pack(side='left')
        self.summary=tk.Label(control,bg=BG,fg=INK,font=('Arial',10))
        self.summary.pack(side='left',padx=10)
        ttk.Button(control,text='Clear comparison',command=self.clear_all).pack(side='right')
        self.instructions=tk.Label(self,text='One TXT per plan. Each dose distribution is repeated for the selected fraction count, then prior RT is added.',bg=FRAME,fg='white',font=('Arial',10),anchor='w')
        if app.course.mode=='Cylinder': self.instructions.configure(text='One TXT per plan. Each dose distribution is repeated for the selected fraction count; BT only.')
        self.instructions.pack(fill='x',padx=12,pady=3)
        cards=tk.Frame(self,bg=FRAME)
        cards.pack(fill='x',padx=12,pady=4)
        self.names=[]
        for slot in range(4):
            frame=tk.Frame(cards,bg='white',padx=6,pady=5,highlightthickness=1,highlightbackground='#d8dde2')
            frame.grid(row=0,column=slot,sticky='nsew',padx=(0,5))
            cards.columnconfigure(slot,weight=1,uniform='plans')
            buttons=tk.Frame(frame,bg='white')
            buttons.pack(fill='x')
            ttk.Button(buttons,text=f'Load plan {slot+1}',command=lambda i=slot:self.load(i)).pack(side='left')
            ttk.Button(buttons,text='Clear',width=5,command=lambda i=slot:self.clear(i)).pack(side='right')
            name=tk.Label(frame,text='No DVH loaded',bg='white',fg=INK,font=('Arial',10),justify='left',anchor='w',wraplength=235,height=3)
            name.pack(fill='x')
            self.names.append(name)
        frame=tk.Frame(self,bg=FRAME)
        frame.pack(fill='both',expand=True,padx=12,pady=4)
        tk.Label(frame,text='PLAN DOSE / EQD2',bg=FRAME,fg='white',font=('Arial',12,'bold'),anchor='w').pack(fill='x',pady=(3,3))
        self.header=tk.Frame(frame,bg=HEADER)
        self.header.pack(fill='x')
        self.head_grid=tk.Frame(self.header,bg=HEADER)
        self.head_grid.pack(side='left',fill='x',expand=True)
        outer=tk.Frame(frame,bg='white')
        outer.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(outer,bg='white',highlightthickness=0,yscrollincrement=22)
        scrollbar=ttk.Scrollbar(outer,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        tk.Frame(self.header,bg=HEADER,width=scrollbar.winfo_reqwidth()).pack(side='right',fill='y')
        self.grid_frame=tk.Frame(self.canvas,bg='#d3d8dc')
        win=self.canvas.create_window((0,0),window=self.grid_frame,anchor='nw')
        def resize(event):
            self.canvas.itemconfigure(win,width=event.width)
            proportions=[240,130,130,130,130,100,110,185]
            widths=[int(event.width*w/sum(proportions)) for w in proportions]
            widths[0]+=event.width-sum(widths)
            for grid in (self.grid_frame,self.head_grid):
                for col,width in enumerate(widths):
                    grid.columnconfigure(col,minsize=width,weight=0)
        self.canvas.bind('<Configure>',resize)
        self.grid_frame.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        for col,text in enumerate(['Structure / metric','Plan 1','Plan 2','Plan 3','Plan 4','Goal / soft','Tolerance / hard','Best vs goal']):
            self.headings.append(self.cell(self.head_grid,0,col,text,HEADER,True))
        row=0
        for title,key,metrics in self.app.course.structures:
            header=tk.Label(self.grid_frame,text=title,bg=HEADER,fg=INK,font=('Arial',10,'bold'),anchor='w',padx=7,pady=0)
            header.grid(row=row,column=0,columnspan=8,sticky='nsew',pady=(8 if row else 0,2))
            row+=1
            for metric in metrics:
                k=f'{key}_{metric.key}'
                self.cell(self.grid_frame,row,0,'  '+metric.label,'white')
                for slot in range(4):
                    label=self.cell(self.grid_frame,row,slot+1,'',BLUE if metric.ab else 'white')
                    if metric.ab:
                        self.physical[k,slot]=label
                    else:
                        self.volumes[k,slot]=label
                for col in (5,6,7):
                    self.cell(self.grid_frame,row,col,'','white')
                row+=1
                if metric.ab:
                    self.cell(self.grid_frame,row,0,f'  Total {metric.label.replace("[Gy]", "EQD2 [Gy]")}', '#fafbfc')
                    for slot in range(4):
                        self.results[k,slot]=self.cell(self.grid_frame,row,slot+1,'','white',True)
                    self.cell(self.grid_frame,row,5,metric.goal,'#fafbfc')
                    self.cell(self.grid_frame,row,6,metric.hard,'#fafbfc')
                    self.best_cells[k]=self.cell(self.grid_frame,row,7,'—','white')
                    row+=1
        def bind_wheel(widget):
            def scroll(event):
                self.canvas.yview_scroll(-1 if event.delta>0 or event.num==4 else 1,'units')
                return 'break'
            for event in ('<MouseWheel>','<Button-4>','<Button-5>'):
                widget.bind(event,scroll)
            for child in widget.winfo_children():
                bind_wheel(child)
        bind_wheel(outer)
        footer=tk.Frame(self,bg=BG)
        footer.pack(fill='x',padx=12,pady=(3,8))
        tk.Label(footer,text='Best vs goal: per metric only; meeting the goal ties. No overall plan ranking.',bg=BG,fg='#505b67',font=('Arial',10)).pack(side='left')
        ttk.Button(footer,text='Export comparison PDF',command=self.export_report).pack(side='right')

    @staticmethod
    def cell(parent,row,col,text,bg,bold=False):
        label=tk.Label(parent,text=text,bg=bg,fg=INK,font=('Arial',10,'bold' if bold else 'normal'),anchor='w' if col==0 else 'center',padx=5,pady=0,width=1)
        label.grid(row=row,column=col,sticky='nsew',padx=(0,1),pady=(0,1))
        return label

    def commit_prescription(self,event=None):
        try:
            if self.prescription_var.get()!=self.prescription_displayed:
                self.prescription_gy=positive_dose(self.prescription_var.get())
            self.prescription_var.set(fmt(self.prescription_gy))
            self.prescription_displayed=self.prescription_var.get()
            self.refresh()
            return True
        except ValueError as error:
            self.app.status_text.set(str(error))
            messagebox.showerror('Prescription',str(error),parent=self)
            return False

    def settings(self):
        course=deepcopy(self.app.course)
        course.count=int(self.count.get()[0])
        course.prescription_gy=self.prescription_gy
        return course

    def refresh(self):
        c=self.settings()
        self.summary.configure(text=f'Rx BT EQD2₁₀: {fmt(c.prescription_eqd2())} Gy | Prior RT: {fmt(c.dose_per_fx)} x {c.prior_fractions} Gy')
        if c.mode=='Cylinder': self.summary.configure(text=f'Rx BT EQD2₁₀: {fmt(c.prescription_eqd2())} Gy')
        first=next((p for p in self.model.plans if p),None)
        self.patient.configure(text=f'Patient: {first.patient or "—"} | ID: {first.patient_id or "—"}' if first else '')
        for slot,parsed in enumerate(self.model.plans):
            self.names[slot].configure(text=self.model.files[slot] if parsed else 'No DVH loaded')
            self.headings[slot+1].configure(text=f'Plan {slot+1}: {self.model.files[slot]}' if parsed else f'Plan {slot+1}',wraplength=130)
            scenario=self.model.scenario(slot,c)
            for _,key,metrics in self.app.course.structures:
                for metric in metrics:
                    k=f'{key}_{metric.key}'
                    value=scenario.values[0].get(k) if scenario else None
                    label=self.physical[k,slot] if metric.ab else self.volumes[k,slot]
                    label.configure(text=fmt(value))
                    if metric.ab:
                        total=scenario.total(k) if scenario else None
                        result=status(total,metric)
                        self.results[k,slot].configure(text=fmt(total),bg='white' if result=='neutral' else COLORS[result],fg=INPUT_INK)


        active={slot:self.model.scenario(slot,c) for slot,plan in enumerate(self.model.plans) if plan}
        for _,key,metrics in self.app.course.structures:
            for metric in metrics:
                if not metric.ab:
                    continue
                k=f'{key}_{metric.key}'
                winners=best_metric_slots({slot:scenario.total(k) for slot,scenario in active.items()},metric)
                label='No defined goal' if not (metric.goal or metric.hard) else 'Need 2 complete plans'
                if winners is not None:
                    label=('Tie: ' if len(winners)>1 else '')+', '.join(f'Plan {slot+1}' for slot in winners)
                self.best_cells[k].configure(text=label)


    def load(self,slot):
        if not self.commit_prescription() or not self.app.commit_inputs():
            return
        path=filedialog.askopenfilename(title=f'Load plan {slot+1} DVH',filetypes=[('DVH text files','*.txt'),('All files','*')])
        if not path:
            return
        try:
            parsed=import_with_volumes(self,lambda volumes:self.model.load(slot,path,self.settings(),volumes))
            if parsed is None:
                return
            self.refresh()
        except (ValueError,OSError) as error:
            messagebox.showerror('Plan comparison import',str(error),parent=self)

    def clear(self,slot):
        self.model.clear(slot)
        self.refresh()

    def clear_all(self):
        if messagebox.askyesno('Clear comparison','Clear all four comparison plans?',default='no',parent=self):
            self.model=PlanComparison()
            self.refresh()

    def export_report(self):
        if not self.commit_prescription() or not self.app.commit_inputs():
            return
        from embrace_pdf import export_comparison_pdf
        path=filedialog.asksaveasfilename(title='Export plan comparison',initialfile='EMBRACE2_Plan_Comparison.pdf',defaultextension='.pdf',filetypes=[('PDF report','*.pdf')])
        if path:
            try:
                export_comparison_pdf(self.model,self.settings(),path)
            except Exception as error:
                messagebox.showerror('PDF Export Error',str(error),parent=self)
