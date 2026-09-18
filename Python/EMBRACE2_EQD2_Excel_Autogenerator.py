#!/usr/bin/env python3
"""EMBRACE-2 desktop dashboard. Install Python/requirements.txt for PDF export."""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from embrace_core import Course, STRUCTURES, eqd2, fmt, status
from embrace_export import export_workbook
from embrace_pdf import export_pdf
from embrace_comparison import ComparisonTab

from embrace_theme import BG, SURFACE, ALT, HEADER, INK, MUTED, BLUE, INPUT_INK, INACTIVE, COLORS, apply_theme


class MetricTable(tk.Frame):
    """An independently scrolling table with a stationary aligned column header."""
    def __init__(self, parent, app, title, definitions, target):
        super().__init__(parent,bg=BG)
        self.app = app
        self.detail_widgets=[]
        tk.Label(self,text=title,bg=BG,fg=INK,font=('Arial',12,'bold'),anchor='w').pack(fill='x',pady=(3,3))
        self.header = tk.Frame(self,bg=HEADER)
        self.header.pack(fill='x')
        outer = tk.Frame(self,bg=SURFACE)
        outer.pack(fill='both',expand=True)
        self.canvas = tk.Canvas(outer,bg=SURFACE,highlightthickness=0,yscrollincrement=22)
        self.scroll = ttk.Scrollbar(outer,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.header.configure(padx=0)
        self.head_grid = tk.Frame(self.header,bg=HEADER)
        self.head_grid.pack(side='left',fill='x',expand=True)
        self.gutter = tk.Frame(self.header,bg=HEADER,width=self.scroll.winfo_reqwidth())
        self.gutter.pack(side='right',fill='y')
        self.grid_frame = tk.Frame(self.canvas,bg=SURFACE)
        self.window = self.canvas.create_window((0,0),window=self.grid_frame,anchor='nw')
        self.grid_frame.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',self.resize)
        headings = ['Structure / dose parameter','Fx 1','Fx 2','Fx 3','Fx 4','Fx 5','BT + EBRT\nEQD2 [Gy]',
                    'Planning\ngoal' if target else 'Soft\nconstraint','Tolerance' if target else 'Hard\nconstraint']
        self.headings=[]
        for col,text in enumerate(headings):
            label=self.cell(self.head_grid,0,col,text,HEADER,bold=True)
            label.configure(height=2)
            self.headings.append(label)
        row=0
        for title,key,metrics in definitions:
            section=tk.Label(self.grid_frame,text=title,bg=HEADER,fg=INK,anchor='w',font=('Arial',11,'bold'),padx=7,pady=1)
            section.grid(row=row,column=0,columnspan=9,sticky='nsew')
            row+=1
            for metric in metrics:
                k=f'{key}_{metric.key}'
                self.cell(self.grid_frame,row,0,'  '+metric.label,SURFACE)
                for fx in range(5):
                    if metric.key == 'volume':
                        app.volumes[k,fx]=self.cell(self.grid_frame,row,fx+1,'',SURFACE)
                    else:
                        var=tk.StringVar()
                        entry=tk.Entry(self.grid_frame,textvariable=var,bg=BLUE,fg=INPUT_INK,
                                       disabledbackground=INACTIVE,disabledforeground='#7b858f',
                                       justify='center',relief='flat',borderwidth=0,width=1,font=('Arial',11),
                                       highlightthickness=1,highlightbackground=BLUE,highlightcolor='#327ca5')
                        entry.grid(row=row,column=fx+1,sticky='nsew',padx=1,pady=0)
                        entry.bind('<Return>',app.edit_pending)
                        entry.bind('<FocusOut>',app.edit_pending)
                        app.inputs[k,fx]=var,entry
                for col in (6,7,8):
                    self.cell(self.grid_frame,row,col,'',SURFACE)
                if not metric.ab:
                    self.detail_widgets.extend(self.grid_frame.grid_slaves(row=row))
                row+=1
                if metric.ab:
                    label=metric.label.replace('[Gy]',f'EQD2{metric.ab} [Gy]')
                    self.cell(self.grid_frame,row,0,'  '+label,ALT)
                    for fx in range(5):
                        app.cells[k,fx]=self.cell(self.grid_frame,row,fx+1,'',ALT)
                    app.totals[k]=self.cell(self.grid_frame,row,6,'',ALT,bold=True)
                    self.cell(self.grid_frame,row,7,metric.goal,ALT)
                    self.cell(self.grid_frame,row,8,metric.hard,ALT)
                    row+=1
        self.bind_wheel(outer)

    def set_details(self,visible):
        for widget in self.detail_widgets:
            widget.grid() if visible else widget.grid_remove()

    @staticmethod
    def cell(parent,row,col,text,bg,bold=False):
        label=tk.Label(parent,text=text,bg=bg,fg=INK,anchor='w' if col == 0 else 'center',
                       font=('Arial',11,'bold' if bold else 'normal'),padx=5,pady=0,width=1)
        label.grid(row=row,column=col,sticky='nsew',padx=0,pady=0)
        return label

    def resize(self,event):
        # Identical pixel widths ensure header/body alignment at any window size.
        self.canvas.itemconfigure(self.window,width=event.width)
        proportions=[225,70,70,70,70,70,135,105,105]
        widths=[int(event.width*w/sum(proportions)) for w in proportions]
        widths[0]+=event.width-sum(widths)
        for grid in (self.head_grid,self.grid_frame):
            for col,width in enumerate(widths):
                grid.columnconfigure(col,minsize=width,weight=0)

    def bind_wheel(self,widget):
        def wheel(event):
            delta = -1 if event.num == 4 or event.delta > 0 else 1
            self.canvas.yview_scroll(delta,'units')
            return 'break'
        widget.bind('<MouseWheel>',wheel)
        widget.bind('<Button-4>',wheel)
        widget.bind('<Button-5>',wheel)
        for child in widget.winfo_children():
            self.bind_wheel(child)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.course=Course()
        self._committing=False
        self.title('EMBRACE-2 EQD2')
        self.geometry('1160x850')
        self.minsize(1020,680)
        self.configure(bg=BG)
        apply_theme(self)
        self.notebook=ttk.Notebook(self)
        self.notebook.pack(fill='both',expand=True)
        self.dashboard=tk.Frame(self.notebook,bg=BG)
        self.notebook.add(self.dashboard,text='Course dashboard')
        self.cells,self.totals,self.inputs,self.volumes={},{},{},{}
        self.displayed={}
        self.status_text=tk.StringVar(value='Blue cells: enter physical dose. Volumes come from the DVH.')
        top=tk.Frame(self.dashboard,bg=BG)
        top.pack(fill='x',padx=12,pady=(5,1))
        tk.Label(top,text='EMBRACE-2  |  EQD2',bg=BG,fg=INK,font=('Arial',19,'bold')).pack(side='left')
        self.patient=tk.Label(top,bg=BG,fg=INK,font=('Arial',11),anchor='e')
        self.patient.pack(side='right',fill='x',expand=True,padx=(20,0))
        controls=tk.Frame(self.dashboard,bg=BG)
        controls.pack(fill='x',padx=12,pady=3)
        tk.Label(controls,text='Brachytherapy',bg=BG,fg=INK,font=('Arial',11,'bold')).pack(side='left',padx=(0,8))
        self.count=tk.StringVar(value='4 Fx')
        count=ttk.Combobox(controls,textvariable=self.count,values=['3 Fx','4 Fx','5 Fx'],width=5,state='readonly')
        count.pack(side='left',padx=(0,8))
        count.bind('<<ComboboxSelected>>',self.change_count)
        self.buttons=[]
        for fx in range(5):
            button=ttk.Button(controls,text=f'Load Fx {fx+1}',command=lambda i=fx:self.load(i),width=11)
            button.pack(side='left',padx=2)
            self.buttons.append(button)
        self.rx_frame=tk.Frame(self.dashboard,bg=BG)
        # Reserved for the pending prescription controls; no blank row is packed.
        self.plans=self.label('',10)
        details=tk.Frame(self.dashboard,bg=BG)
        details.pack(fill='x',padx=12)
        self.show_details=tk.BooleanVar(value=True)
        ttk.Checkbutton(details,text='Show volumes',variable=self.show_details,command=self.toggle_details).pack(side='left',padx=(0,12))
        self.show_files=tk.BooleanVar(value=False)
        ttk.Checkbutton(details,text='Show source files',variable=self.show_files,command=self.toggle_files).pack(side='left')
        tk.Label(details,text='Green: goal   Yellow: tolerance   Red: outside tolerance',bg=BG,fg=MUTED,font=('Arial',10)).pack(side='right')
        self.files=tk.Label(self.dashboard,text='',bg=BG,fg=MUTED,anchor='w',justify='left',wraplength=1100,font=('Arial',9))
        self.prior_frame=tk.Frame(self.dashboard,bg=HEADER,padx=8,pady=5)
        self.prior_frame.pack(fill='x',padx=12,pady=(5,3))
        tk.Label(self.prior_frame,text='PRIOR RT / EBRT',bg=HEADER,fg=INK,font=('Arial',11,'bold')).pack(side='left',padx=(0,12))
        self.prior_vars=[tk.StringVar(),tk.StringVar()]
        for i,text in enumerate(('Gy / Fx','fractions')):
            entry=tk.Entry(self.prior_frame,textvariable=self.prior_vars[i],bg=BLUE,fg=INPUT_INK,justify='center',relief='flat',font=('Arial',11),width=6)
            entry.pack(side='left',ipady=2)
            entry.bind('<Return>',self.edit_pending)
            entry.bind('<FocusOut>',self.edit_pending)
            tk.Label(self.prior_frame,text=text,bg=HEADER,fg=INK,font=('Arial',10)).pack(side='left',padx=(4,10))
        self.prior_summary=tk.Label(self.prior_frame,text='',bg=HEADER,fg=INK,font=('Arial',10),anchor='e')
        self.prior_summary.pack(side='right',fill='x',expand=True)
        body=tk.PanedWindow(self.dashboard,orient='vertical',bg=BG,sashwidth=6,bd=0)
        body.pack(fill='both',expand=True,padx=12,pady=(0,3))
        self.tables=[]
        for title,definitions,target in [('TARGETS',STRUCTURES[:3],True),('ORGANS AT RISK',STRUCTURES[3:],False)]:
            table=MetricTable(body,self,title,definitions,target)
            body.add(table,minsize=150,stretch='always')
            self.tables.append(table)
            table.set_details(self.show_details.get())
        footer=tk.Frame(self.dashboard,bg=BG)
        footer.pack(fill='x',padx=12,pady=(3,8))
        ttk.Button(footer,text='Export Excel',command=self.export).pack(side='right',padx=(6,0))
        ttk.Button(footer,text='Export PDF',command=self.export_report).pack(side='right',padx=(6,0))
        ttk.Button(footer,text='Clear all',command=self.clear).pack(side='right',padx=(6,0))
        tk.Label(footer,textvariable=self.status_text,bg=BG,fg=MUTED,font=('Arial',10),anchor='w',justify='left',wraplength=720).pack(side='left',fill='x',expand=True)
        self.comparison=ComparisonTab(self.notebook,self)
        self.notebook.add(self.comparison,text='Plan comparison')
        self.notebook.bind('<<NotebookTabChanged>>',lambda e:self.commit_inputs())
        self.refresh()
        self.after(100,lambda:body.sash_place(0,0,int(body.winfo_height()*.44)))

    def label(self,text,size=11):
        label=tk.Label(self.dashboard,text=text,bg=BG,fg=INK,anchor='w',justify='left',wraplength=1100,font=('Arial',size))
        label.pack(fill='x',padx=12,pady=2)
        return label

    def toggle_details(self):
        for table in self.tables:
            table.set_details(self.show_details.get())

    def toggle_files(self):
        if self.show_files.get():
            self.files.pack(fill='x',padx=12,pady=2,before=self.prior_frame)
        else:
            self.files.pack_forget()

    def refresh(self):
        c=self.course
        self.patient.configure(text=f'Patient: {c.patient or "—"}   |   ID: {c.patient_id or "—"}')
        self.plans.configure(text='    |    '.join(f'Fx {i+1}: {c.plans[i] or "—"}' for i in range(c.count)))
        self.files.configure(text='\n'.join(f'Fx {i+1}: {c.files[i] or "No file loaded"}' for i in range(c.count)))
        self.prior_vars[0].set(fmt(c.dose_per_fx))
        self.prior_vars[1].set(str(c.prior_fractions))
        self.prior_displayed=[v.get() for v in self.prior_vars]
        self.prior_summary.configure(text=f'Total {fmt(c.dose_per_fx*c.prior_fractions)} Gy   |   EQD2₁₀ {fmt(c.baseline(10))}   |   EQD2₃ {fmt(c.baseline(3))} Gy')
        for fx,button in enumerate(self.buttons):
            button.configure(state='normal' if fx < c.count else 'disabled')
        for (key,fx),(var,entry) in self.inputs.items():
            var.set(fmt(c.values[fx].get(key)))
            self.displayed[key,fx]=var.get()
            entry.configure(state='normal' if fx < c.count else 'disabled',highlightbackground=BLUE if fx<c.count else INACTIVE)
        for (key,fx),label in self.volumes.items():
            label.configure(text=fmt(c.values[fx].get(key)),bg=SURFACE if fx < c.count else INACTIVE,fg=MUTED)
        for table in self.tables:
            for fx in range(5):
                table.headings[fx+1].configure(fg=INK if fx < c.count else '#929ba4')
        for _,key,metrics in STRUCTURES:
            for metric in metrics:
                if not metric.ab:
                    continue
                k=f'{key}_{metric.key}'
                for fx in range(5):
                    value=c.values[fx].get(k)
                    self.cells[k,fx].configure(text=fmt(eqd2(value,metric.ab)) if value is not None and fx<c.count else '',bg=ALT if fx<c.count else INACTIVE)
                total=c.total(k)
                result=status(total,metric)
                self.totals[k].configure(text=fmt(total),bg=COLORS[result],fg=INK if result=='neutral' else INPUT_INK)

        if hasattr(self,'comparison'):
            self.comparison.refresh()

    def commit_inputs(self):
        """Apply changed text only; rounded display values never replace stored data."""
        if self._committing:
            return True
        self._committing=True
        try:
            updated=deepcopy(self.course)
            for (key,fx),(var,_) in self.inputs.items():
                if fx<updated.count and var.get()!=self.displayed[key,fx]:
                    updated.edit(fx,key,var.get())
            prior=[v.get() for v in self.prior_vars]
            if prior != self.prior_displayed:
                dose=prior[0] if prior[0]!=self.prior_displayed[0] else updated.dose_per_fx
                count=prior[1] if prior[1]!=self.prior_displayed[1] else updated.prior_fractions
                updated.set_prior(dose,count)
            self.course=updated
            self.refresh()
            return True
        except ValueError as error:
            self.status_text.set(f'Input not saved: {error}')
            return False
        finally:
            self._committing=False

    def edit_pending(self,event=None):
        self.commit_inputs()

    def change_count(self,event=None):
        selected=int(self.count.get()[0])
        if not self.commit_inputs():
            self.count.set(f'{self.course.count} Fx')
            return
        self.course.set_count(selected)
        self.refresh()
        self.status_text.set(f'{self.course.count}-fraction course selected.')

    def load(self,fx):
        if not self.commit_inputs():
            return
        path=filedialog.askopenfilename(title=f'Load Fx {fx+1} DVH TXT',filetypes=[('DVH text files','*.txt'),('All files','*')])
        if not path:
            return
        try:
            candidate=deepcopy(self.course)
            parsed=candidate.load(fx,path)
            for plan in self.comparison.model.plans:
                if plan:
                    for label,current,new in [('Patient',plan.patient,parsed.patient),('Patient ID',plan.patient_id,parsed.patient_id)]:
                        if current and new and current.casefold()!=new.casefold():
                            raise ValueError(f'{label} does not match the loaded comparison plans. Clear the comparison before changing patients.')
            self.course=candidate
            self.refresh()
            self.status_text.set(f'Loaded Fx {fx+1}; carried into later fractions without their own import.'+(' Ignored: '+', '.join(parsed.ignored) if parsed.ignored else ''))
        except (ValueError,OSError) as error:
            messagebox.showerror('DVH Import Error',str(error),parent=self)

    def clear(self):
        if messagebox.askyesno('Clear Dashboard','Clear all brachytherapy values and reset prior RT?',default='no',parent=self):
            self.course=Course(count=self.course.count)
            self.refresh()
            self.status_text.set('Dashboard cleared.')

    def export(self):
        if not self.commit_inputs():
            return
        here=Path(__file__).resolve().parent
        name='EQD2_with_tolerances_090126.xlsx'
        template=next((p for p in (here/name,here.parent/'Matlab'/name,Path.cwd()/name) if p.exists()),None)
        if template is None:
            template=filedialog.askopenfilename(title='Choose EQD2 template',filetypes=[('Excel workbook','*.xlsx')])
        if not template:
            return
        output=filedialog.asksaveasfilename(title='Export Excel',initialfile='EMBRACE2_Current_Display.xlsx',defaultextension='.xlsx',filetypes=[('Excel workbook','*.xlsx')])
        if not output:
            return
        try:
            export_workbook(self.course,template,output)
            self.status_text.set(f'Exported {Path(output).name}. Open in Excel to recalculate formulas.')
        except Exception as error:
            messagebox.showerror('Excel Export Error',str(error),parent=self)

    def export_report(self):
        if not self.commit_inputs():
            return
        output=filedialog.asksaveasfilename(title='Export PDF report',initialfile='EMBRACE2_EQD2_Report.pdf',defaultextension='.pdf',filetypes=[('PDF report','*.pdf')])
        if not output:
            return
        try:
            export_pdf(self.course,output)
            self.status_text.set(f'Exported {Path(output).name}.')
        except Exception as error:
            messagebox.showerror('PDF Export Error',str(error),parent=self)


def packaged_smoke_test(report_path):
    """Exercise the frozen GUI and resource lookup without any patient data."""
    import json
    import tempfile
    app=App()
    try:
        app.update()
        assert all(w.winfo_ismapped() for table in app.tables for w in table.detail_widgets)
        for show_volumes in (False,True):
            app.show_details.set(show_volumes)
            app.toggle_details()
            app.update()
            for key, total in app.totals.items():
                dose=app.inputs[key,0][1]
                eqd=app.cells[key,0]
                assert eqd.winfo_ismapped()
                assert int(eqd.grid_info()['row'])==int(dose.grid_info()['row'])+1
                assert total.grid_info()['row']==eqd.grid_info()['row']
        app.inputs['ctvhr_D90',0][0].set('7.13')
        app.count.set('5 Fx')
        app.change_count()
        before=app.course.values[0]['ctvhr_D90']
        app.commit_inputs()
        assert app.course.values[0]['ctvhr_D90']==before==7.13
        assert app.totals['ctvhr_D90'].cget('text')==fmt(44.25+eqd2(7.13,10))
        assert str(app.buttons[4].cget('state'))=='normal'
        app.count.set('3 Fx')
        app.change_count()
        assert str(app.buttons[4].cget('state'))=='disabled'
        assert ('ctvhr_volume',0) not in app.inputs
        for table in app.tables:
            y=table.header.winfo_rooty()
            table.canvas.yview_moveto(1)
            app.update()
            assert table.header.winfo_rooty()==y
        template=Path(__file__).resolve().parent/'EQD2_with_tolerances_090126.xlsx'
        assert template.is_file(),'Bundled template is missing'
        with tempfile.TemporaryDirectory() as folder:
            sheets=export_workbook(app.course,template,Path(folder)/'smoke.xlsx')
            assert len(sheets)==2
            pdf=Path(folder)/'smoke.pdf'
            export_pdf(app.course,pdf)
            assert pdf.read_bytes().startswith(b'%PDF-')
            sample=Path(folder)/'synthetic.txt'
            sample.write_text('Patient: Synthetic QA\nPatient Id: TEST-001\nPlan: QA\nAbsolute Dose - [Gy]\nCumulative mode\nROI: CTV_HR\n1 0 10\n2 5 9\n3 10 0\n')
            for slot in range(4):
                app.comparison.model.load(slot,sample,app.course)
            app.comparison.count.set('3 Fx')
            app.comparison.refresh()
            app.notebook.select(app.comparison)
            app.update()
            assert app.comparison.results['ctvhr_D90',0].cget('text')=='63.0'
            from embrace_pdf import export_comparison_pdf
            export_comparison_pdf(app.comparison.model,app.comparison.settings(),Path(folder)/'comparison.pdf')
        Path(report_path).write_text(json.dumps({'status':'passed','checks':['GUI','precision preservation','fixed headers','ESTRO dose/EQD2 row order','fraction controls','bundled Excel export','PDF export','four-plan comparison','comparison PDF']}))
    finally:
        app.destroy()


if __name__=='__main__':
    import sys
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        packaged_smoke_test(sys.argv[2])
    else:
        App().mainloop()
