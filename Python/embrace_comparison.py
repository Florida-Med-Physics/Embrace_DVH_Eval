"""Side-by-side plan iteration comparison against the existing course constraints."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from embrace_core import PlanComparison, STRUCTURES, fmt, status

from embrace_theme import BG, SURFACE, ALT, HEADER, INK, MUTED, INPUT_INK, COLORS


class ComparisonTab(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=BG)
        self.app=app
        self.model=PlanComparison()
        self.results={}
        self.volumes={}
        self.physical={}
        self.headings=[]
        top=tk.Frame(self,bg=BG)
        top.pack(fill='x',padx=12,pady=(10,3))
        tk.Label(top,text='PLAN COMPARISON',bg=BG,fg=INK,font=('Arial',17,'bold')).pack(side='left')
        self.patient=tk.Label(top,bg=BG,fg=INK,font=('Arial',11))
        self.patient.pack(side='right')
        control=tk.Frame(self,bg=BG)
        control.pack(fill='x',padx=12,pady=3)
        tk.Label(control,text='Repeat each plan for',bg=BG,fg=INK,font=('Arial',11)).pack(side='left')
        self.count=tk.StringVar(value=app.count.get())
        count=ttk.Combobox(control,textvariable=self.count,values=['3 Fx','4 Fx','5 Fx'],state='readonly',width=5)
        count.pack(side='left',padx=6)
        count.bind('<<ComboboxSelected>>',lambda event:self.refresh())
        self.summary=tk.Label(control,bg=BG,fg=INK,font=('Arial',10))
        self.summary.pack(side='left',padx=10)
        ttk.Button(control,text='Clear comparison',command=self.clear_all).pack(side='right')
        self.instructions=tk.Label(self,text='One TXT per plan. Each dose distribution is repeated for the selected fraction count, then prior RT is added.',bg=BG,fg=MUTED,font=('Arial',10),anchor='w')
        self.instructions.pack(fill='x',padx=12,pady=1)
        cards=tk.Frame(self,bg=BG)
        cards.pack(fill='x',padx=12,pady=4)
        self.names=[]
        for slot in range(4):
            frame=tk.Frame(cards,bg=SURFACE,padx=6,pady=5,highlightthickness=1,highlightbackground=HEADER)
            frame.grid(row=0,column=slot,sticky='nsew',padx=(0,5))
            cards.columnconfigure(slot,weight=1,uniform='plans')
            buttons=tk.Frame(frame,bg=SURFACE)
            buttons.pack(fill='x')
            ttk.Button(buttons,text=f'Load plan {slot+1}',command=lambda i=slot:self.load(i)).pack(side='left')
            ttk.Button(buttons,text='Clear',width=5,command=lambda i=slot:self.clear(i)).pack(side='right')
            name=tk.Label(frame,text='No DVH loaded',bg=SURFACE,fg=INK,font=('Arial',10),justify='left',anchor='w',wraplength=235)
            name.pack(fill='x')
            self.names.append(name)
        frame=tk.Frame(self,bg=BG)
        frame.pack(fill='both',expand=True,padx=12,pady=4)
        self.header=tk.Frame(frame,bg=HEADER)
        self.header.pack(fill='x')
        self.head_grid=tk.Frame(self.header,bg=HEADER)
        self.head_grid.pack(side='left',fill='x',expand=True)
        outer=tk.Frame(frame,bg=SURFACE)
        outer.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(outer,bg=SURFACE,highlightthickness=0,yscrollincrement=22)
        scrollbar=ttk.Scrollbar(outer,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        tk.Frame(self.header,bg=HEADER,width=scrollbar.winfo_reqwidth()).pack(side='right',fill='y')
        self.grid_frame=tk.Frame(self.canvas,bg=SURFACE)
        win=self.canvas.create_window((0,0),window=self.grid_frame,anchor='nw')
        def resize(event):
            self.canvas.itemconfigure(win,width=event.width)
            proportions=[260,145,145,145,145,115,115]
            widths=[int(event.width*w/sum(proportions)) for w in proportions]
            widths[0]+=event.width-sum(widths)
            for grid in (self.grid_frame,self.head_grid):
                for col,width in enumerate(widths):
                    grid.columnconfigure(col,minsize=width,weight=0)
        self.canvas.bind('<Configure>',resize)
        self.grid_frame.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        for col,text in enumerate(['Structure / metric','Plan 1','Plan 2','Plan 3','Plan 4','Goal / soft','Tolerance / hard']):
            self.headings.append(self.cell(self.head_grid,0,col,text,HEADER,True))
        row=0
        for title,key,metrics in STRUCTURES:
            header=tk.Label(self.grid_frame,text=title,bg=HEADER,fg=INK,font=('Arial',11,'bold'),anchor='w',padx=7,pady=2)
            header.grid(row=row,column=0,columnspan=7,sticky='nsew')
            row+=1
            for metric in metrics:
                k=f'{key}_{metric.key}'
                self.cell(self.grid_frame,row,0,'  '+metric.label,SURFACE)
                for slot in range(4):
                    label=self.cell(self.grid_frame,row,slot+1,'',SURFACE)
                    if metric.ab:
                        self.physical[k,slot]=label
                    else:
                        self.volumes[k,slot]=label
                row+=1
                if metric.ab:
                    self.cell(self.grid_frame,row,0,f'  Total {metric.label.replace("[Gy]", "EQD2 [Gy]")}', SURFACE)
                    for slot in range(4):
                        self.results[k,slot]=self.cell(self.grid_frame,row,slot+1,'','white',True)
                    self.cell(self.grid_frame,row,5,metric.goal,SURFACE)
                    self.cell(self.grid_frame,row,6,metric.hard,SURFACE)
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
        tk.Label(footer,text='Physical dose rows: one fraction. Total EQD2 rows: all fractions + prior RT.',bg=BG,fg=MUTED,font=('Arial',10)).pack(side='left')
        ttk.Button(footer,text='Export comparison PDF',command=self.export_report).pack(side='right')

    @staticmethod
    def cell(parent,row,col,text,bg,bold=False):
        label=tk.Label(parent,text=text,bg=bg,fg=INPUT_INK if bg=='white' else INK,font=('Arial',11,'bold' if bold else 'normal'),anchor='w' if col==0 else 'center',padx=5,pady=0,width=1)
        label.grid(row=row,column=col,sticky='nsew')
        return label

    def settings(self):
        course=deepcopy(self.app.course)
        course.count=int(self.count.get()[0])
        return course

    def refresh(self):
        c=self.settings()
        self.summary.configure(text=f'Prior RT: {fmt(c.dose_per_fx)} Gy x {c.prior_fractions}   |   EQD2: {fmt(c.baseline(10))} / {fmt(c.baseline(3))} Gy (10 / 3)')
        first=next((p for p in self.model.plans if p),None)
        self.patient.configure(text=f'Patient: {first.patient or "—"} | ID: {first.patient_id or "—"}' if first else '')
        for slot,parsed in enumerate(self.model.plans):
            self.names[slot].configure(text=f'{parsed.plan or "Unnamed plan"}\n{self.model.files[slot]}' if parsed else 'No DVH loaded')
            scenario=self.model.scenario(slot,c)
            for _,key,metrics in STRUCTURES:
                for metric in metrics:
                    k=f'{key}_{metric.key}'
                    value=parsed.metrics.get(k) if parsed else None
                    label=self.physical[k,slot] if metric.ab else self.volumes[k,slot]
                    label.configure(text=fmt(value))
                    if metric.ab:
                        total=scenario.total(k) if scenario else None
                        result=status(total,metric)
                        self.results[k,slot].configure(text=fmt(total),bg='white' if result=='neutral' else COLORS[result],fg=INPUT_INK)

    def load(self,slot):
        if not self.app.commit_inputs():
            return
        path=filedialog.askopenfilename(title=f'Load plan {slot+1} DVH',filetypes=[('DVH text files','*.txt'),('All files','*')])
        if not path:
            return
        try:
            self.model.load(slot,path,self.app.course)
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
        if not self.app.commit_inputs():
            return
        from embrace_pdf import export_comparison_pdf
        path=filedialog.asksaveasfilename(title='Export plan comparison',initialfile='EMBRACE2_Plan_Comparison.pdf',defaultextension='.pdf',filetypes=[('PDF report','*.pdf')])
        if path:
            try:
                export_comparison_pdf(self.model,self.settings(),path)
            except Exception as error:
                messagebox.showerror('PDF Export Error',str(error),parent=self)
