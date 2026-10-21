#!/usr/bin/env python3
"""EMBRACE-2 desktop dashboard. Install Python/requirements.txt for PDF export."""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from embrace_core import Course, STRUCTURES, eqd2, fmt, status
from embrace_export import export_workbook
from embrace_import import import_with_volumes
from embrace_pdf import export_pdf
from embrace_comparison import ComparisonTab

from embrace_theme import BG, SURFACE, ALT, HEADER, INK, MUTED, BLUE, INPUT_INK, INACTIVE, COLORS, FONT, TITLE_FONT, apply_theme


FRAME = '#202326'


class MetricTable(tk.Frame):
    """An independently scrolling table with a stationary aligned column header."""
    def __init__(self, parent, app, title, definitions, target):
        super().__init__(parent,bg=FRAME)
        self.app = app
        tk.Label(self,text=title,bg=FRAME,fg='white',font=(FONT,12,'bold'),anchor='w').pack(fill='x',pady=(3,3))
        self.header = tk.Frame(self,bg=HEADER)
        self.header.pack(fill='x')
        outer = tk.Frame(self,bg='white')
        outer.pack(fill='both',expand=True)
        self.canvas = tk.Canvas(outer,bg='white',highlightthickness=0,yscrollincrement=22)
        self.scroll = ttk.Scrollbar(outer,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.scroll.pack(side='right',fill='y')
        self.canvas.pack(side='left',fill='both',expand=True)
        self.header.configure(padx=0)
        self.head_grid = tk.Frame(self.header,bg=HEADER)
        self.head_grid.pack(side='left',fill='x',expand=True)
        self.gutter = tk.Frame(self.header,bg=HEADER,width=self.scroll.winfo_reqwidth())
        self.gutter.pack(side='right',fill='y')
        self.grid_frame = tk.Frame(self.canvas,bg='#d3d8dc')
        self.window = self.canvas.create_window((0,0),window=self.grid_frame,anchor='nw')
        self.grid_frame.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<Configure>',self.resize)
        headings = ['Structure / dose parameter','Fx 1','Fx 2','Fx 3','Fx 4','Fx 5','BT + EBRT\nEQD2 [Gy]',
                    'Planning\ngoal' if target else 'Soft\nconstraint','Tolerance' if target else 'Hard\nconstraint']
        if app.course.mode=='Cylinder':
            headings[6]='Total BT\nEQD2 [Gy]'
            headings[7:]=['','']
        self.headings=[]
        for col,text in enumerate(headings):
            label=self.cell(self.head_grid,0,col,text,HEADER,bold=True)
            label.configure(height=2)
            self.headings.append(label)
        row=0
        for title,key,metrics in definitions:
            section=tk.Label(self.grid_frame,text=title,bg=HEADER,fg=INK,anchor='w',font=(FONT,10,'bold'),padx=7,pady=0)
            section.grid(row=row,column=0,columnspan=9,sticky='nsew',pady=(8 if row else 0,2))
            row+=1
            for metric in metrics:
                k=f'{key}_{metric.key}'
                self.cell(self.grid_frame,row,0,'  '+metric.label,'white')
                for fx in range(5):
                    if metric.key == 'volume':
                        app.volumes[k,fx]=self.cell(self.grid_frame,row,fx+1,'','white')
                    else:
                        var=tk.StringVar()
                        entry=tk.Entry(self.grid_frame,textvariable=var,bg=BLUE,fg=INK,
                                       disabledbackground='#eef0f2',disabledforeground='#7b858f',
                                       justify='center',relief='flat',borderwidth=0,width=1,font=(FONT,10),
                                       highlightthickness=1,highlightbackground=BLUE,highlightcolor='#327ca5')
                        entry.grid(row=row,column=fx+1,sticky='nsew',padx=1,pady=0)
                        entry.bind('<Return>',app.edit_pending)
                        entry.bind('<FocusOut>',app.edit_pending)
                        app.inputs[k,fx]=var,entry
                for col in (6,7,8):
                    self.cell(self.grid_frame,row,col,'','white')
                row+=1
                if metric.ab:
                    label=metric.label.replace('[Gy]',f'EQD2{metric.ab} [Gy]')
                    self.cell(self.grid_frame,row,0,'  '+label,'#fafbfc')
                    for fx in range(5):
                        app.cells[k,fx]=self.cell(self.grid_frame,row,fx+1,'','#fafbfc')
                    app.totals[k]=self.cell(self.grid_frame,row,6,'','white',bold=True)
                    self.cell(self.grid_frame,row,7,metric.goal,'#fafbfc')
                    self.cell(self.grid_frame,row,8,metric.hard,'#fafbfc')
                    row+=1
        self.cylinder=app.course.mode=='Cylinder'
        if self.cylinder:
            for grid in (self.head_grid,self.grid_frame):
                for child in grid.winfo_children():
                    if int(child.grid_info().get('column',0))>=7: child.grid_remove()
        self.bind_wheel(outer)

    @staticmethod
    def cell(parent,row,col,text,bg,bold=False):
        label=tk.Label(parent,text=text,bg=bg,fg=INK,anchor='w' if col == 0 else 'center',
                       font=(FONT,10,'bold' if bold else 'normal'),padx=5,pady=0,width=1)
        label.grid(row=row,column=col,sticky='nsew',padx=(0,1),pady=(0,1))
        return label

    def resize(self,event):
        # Identical pixel widths ensure header/body alignment at any window size.
        self.canvas.itemconfigure(self.window,width=event.width)
        proportions=[225,70,70,70,70,70,135,105,105]
        if self.cylinder: proportions=[225,70,70,70,70,70,135,0,0]
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
        from embrace_icon import apply_icon
        apply_icon(self)
        self.course=Course()
        self._committing=False
        self.title('EMBRACE-2 EQD2 Excel Autogenerator')
        # Fit the screen's height; cap width so table columns never stretch too wide.
        height=min(980,self.winfo_screenheight()-90)
        self.geometry(f'1200x{height}+{max(0,(self.winfo_screenwidth()-1200)//2)}+0')
        self.minsize(1020,min(680,height))
        self.maxsize(1400,self.winfo_screenheight())
        self.configure(bg=BG)
        apply_theme(self)
        self.mode_courses={'GYN':self.course}
        self.mode_comparisons={}
        # Sits in the tab strip's empty right side so it costs no vertical space.
        chooser=self.chooser=tk.Frame(self,bg=BG);chooser.place(relx=1,x=-12,y=2,anchor='ne')
        tk.Label(chooser,text='Treatment type',bg=BG,fg=INK).pack(side='left',padx=5)
        self.mode_var=tk.StringVar(value='GYN')
        box=ttk.Combobox(chooser,textvariable=self.mode_var,values=['GYN','Cylinder'],state='readonly',width=12)
        box.pack(side='left');box.bind('<<ComboboxSelected>>',self.change_mode)
        self.build_pages()

    def change_mode(self,event=None):
        mode=self.mode_var.get()
        if mode==self.course.mode: return
        if not self.commit_inputs(): self.mode_var.set(self.course.mode);return
        self.mode_courses[self.course.mode]=self.course
        self.mode_comparisons[self.course.mode]=(self.comparison.model,self.comparison.count.get(),self.comparison.prescription_gy)
        self.notebook.unbind('<<NotebookTabChanged>>')
        self.notebook.destroy()
        del self.comparison
        self.course=self.mode_courses.setdefault(mode,Course.for_mode(mode))
        self.build_pages()
        if mode in self.mode_comparisons:
            model,count,rx=self.mode_comparisons[mode]
            self.comparison.model=model;self.comparison.count.set(count);self.comparison.prescription_gy=rx
            self.comparison.prescription_var.set(fmt(rx));self.comparison.prescription_displayed=fmt(rx)
            self.comparison.refresh()

    def build_pages(self):
        self.title(self.course.title+" Excel Autogenerator")
        self.notebook=ttk.Notebook(self)
        self.notebook.pack(fill='both',expand=True)
        self.dashboard=tk.Frame(self.notebook,bg=FRAME)
        self.notebook.add(self.dashboard,text='Course dashboard')
        self.cells,self.totals,self.inputs,self.volumes={},{},{},{}
        self.displayed={}
        self.status_text=tk.StringVar(value='Blue cells: enter physical dose. Volumes come from the DVH.')
        # Course setup occupies the top third; the constraint tables get the rest.
        self.top=tk.Frame(self.dashboard,bg=FRAME)
        top=tk.Frame(self.top,bg=FRAME)
        top.pack(fill='x',padx=12,pady=(8,4))
        tk.Label(top,text=self.course.title+'  Excel Autogenerator',bg=FRAME,fg='white',font=(TITLE_FONT,18,'bold')).pack(side='left')
        tk.Label(top,text='UFHPTI',bg=FRAME,fg='#fa4a00',font=(FONT,12,'bold')).pack(side='right')
        self.patient=tk.Label(top,bg=FRAME,fg='white',font=(FONT,10),anchor='e')
        self.patient.pack(side='right',padx=16)
        controls=tk.Frame(self.top,bg=BG,padx=8,pady=4)
        controls.pack(fill='x',padx=12,pady=2)
        self.count=tk.StringVar(value=f'{self.course.count} Fx')
        count=ttk.Combobox(controls,textvariable=self.count,values=['3 Fx','4 Fx','5 Fx'],width=5,state='readonly')
        count.pack(side='left',padx=(0,8))
        count.bind('<<ComboboxSelected>>',self.change_count)
        self.buttons=[]
        for fx in range(5):
            button=ttk.Button(controls,text=f'Load F{fx+1}',command=lambda i=fx:self.load(i),width=8)
            button.pack(side='left',padx=2)
            self.buttons.append(button)
        self.rx_frame=controls
        tk.Label(self.rx_frame,text='Prescription',bg=BG,fg=INK,font=(FONT,10)).pack(side='left',padx=(16,6))
        self.prescription_var=tk.StringVar(value='7.0')
        prescription=tk.Entry(self.rx_frame,textvariable=self.prescription_var,bg=BLUE,fg=INPUT_INK,
                              justify='center',relief='flat',borderwidth=0,highlightthickness=1,
                              highlightbackground='black',highlightcolor='black',font=(FONT,10),width=6)
        prescription.pack(side='left')
        prescription.bind('<Return>',self.edit_pending)
        prescription.bind('<FocusOut>',self.edit_pending)
        tk.Label(self.rx_frame,text='Gy / Fx  ×',bg=BG,fg=INK,font=(FONT,10)).pack(side='left',padx=(5,12))
        self.rx_summary=tk.Label(self.rx_frame,bg=BG,fg=INK,font=(FONT,10))
        self.rx_summary.pack(side='left')
        modality_frame=tk.Frame(self.top,bg=BG,padx=4,pady=2)
        modality_frame.pack(fill='x',padx=12,pady=(2,0))
        tk.Label(modality_frame,text='Localization (MR / CT)',bg=BG,fg=INK).pack(side='left',padx=(0,8))
        self.modality_vars=[]
        self.modality_boxes=[]
        for fx in range(5):
            tk.Label(modality_frame,text=f'Fx {fx+1}',bg=BG,fg=INK).pack(side='left',padx=(8,3))
            var=tk.StringVar()
            box=ttk.Combobox(modality_frame,textvariable=var,values=['','MRI','CT','MRI + CT'],state='readonly',width=9)
            box.pack(side='left')
            box.bind('<<ComboboxSelected>>',lambda e,i=fx:self.set_modality(i))
            self.modality_vars.append(var); self.modality_boxes.append(box)
        attachments=tk.Frame(self.top,bg=BG,padx=4,pady=2)
        attachments.pack(fill='x',padx=12,pady=(0,2))
        tk.Label(attachments,text='PDF fraction',bg=BG,fg=INK).pack(side='left')
        self.image_fx=tk.StringVar(value='Fx 1')
        self.image_fx_box=ttk.Combobox(attachments,textvariable=self.image_fx,state='readonly',width=5)
        self.image_fx_box.pack(side='left',padx=5)
        ttk.Button(attachments,text='Attach screenshot',command=lambda:self.add_screenshot(False)).pack(side='left',padx=3)
        ttk.Button(attachments,text='Snip screen',command=lambda:self.add_screenshot(True)).pack(side='left',padx=3)
        ttk.Button(attachments,text='Remove image',command=self.remove_screenshot).pack(side='left',padx=3)
        self.image_status=tk.Label(attachments,text='',bg=BG,fg=INK)
        self.image_status.pack(side='left',padx=6)
        self.show_files=tk.BooleanVar(value=True)
        self.files=tk.Label(self.top,text='',bg=FRAME,fg='white',anchor='w',justify='left',wraplength=1160,font=(FONT,9))
        self.files.pack(fill='x',padx=12,pady=2)
        self.prior_frame=tk.Frame(self.top,bg='#d3d8dc')
        self.prior_frame.pack(fill='x',padx=12,pady=(4,4))
        # One header row and one value row; the section name spans both.
        section=tk.Label(self.prior_frame,text='PRIOR RT /\nEBRT',bg=HEADER,fg=INK,font=(FONT,10,'bold'),anchor='w',justify='left',padx=5)
        section.grid(row=0,column=0,rowspan=2,sticky='nsew',padx=(0,1),pady=(0,1))
        for col,title in enumerate(('Dose per fraction [Gy]','Fractions without central shield','Total dose [Gy]','EQD2 [Gy] (α/β = 10)','EQD2 [Gy] (α/β = 3)'),1):
            MetricTable.cell(self.prior_frame,0,col,title,HEADER,True).configure(anchor='center')
            self.prior_frame.columnconfigure(col,weight=2)
        self.prior_frame.columnconfigure(0,weight=1)
        self.prior_vars=[tk.StringVar(),tk.StringVar()]
        self.prior_display={}
        for col,var in enumerate(self.prior_vars,1):
            entry=tk.Entry(self.prior_frame,textvariable=var,bg=BLUE,fg=INK,justify='center',relief='flat',borderwidth=0,highlightthickness=0,font=(FONT,10),width=6)
            entry.grid(row=1,column=col,sticky='nsew',padx=(0,1),pady=(0,1))
            entry.bind('<Return>',self.edit_pending)
            entry.bind('<FocusOut>',self.edit_pending)
        # Keys keep refresh()'s (row,col) meaning: col 1 total dose, 2 and 3 EQD2.
        for key,col in (((2,1),3),((2,2),4),((2,3),5)):
            self.prior_display[key]=MetricTable.cell(self.prior_frame,1,col,'','white')
        if self.course.mode=='Cylinder':
            self.prior_frame.pack_forget()
        body=tk.PanedWindow(self.dashboard,orient='vertical',bg=FRAME,sashwidth=8,bd=0)
        self.tables=[]
        for title,definitions,target in [(title,definitions,title=='TARGETS') for title,definitions in self.course.sections]:
            table=MetricTable(body,self,title,definitions,target)
            body.add(table,minsize=230 if target else 160,stretch='always')
            self.tables.append(table)
        footer=tk.Frame(self.dashboard,bg=BG)
        # Equal-unit rows split the space 1:3; setup never shrinks below its content.
        self.top.grid(row=0,column=0,sticky='nsew')
        body.grid(row=1,column=0,sticky='nsew',padx=12,pady=(0,3))
        footer.grid(row=2,column=0,sticky='ew',padx=12,pady=(2,6))
        self.dashboard.columnconfigure(0,weight=1)
        self.dashboard.rowconfigure(0,weight=1,uniform='split')
        self.dashboard.rowconfigure(1,weight=3,uniform='split')
        self.chooser.lift()
        self.top.update_idletasks()
        self.dashboard.rowconfigure(0,minsize=self.top.winfo_reqheight())
        ttk.Button(footer,text='Export Excel',command=self.export,width=14).pack(side='right',padx=(10,8),pady=5)
        ttk.Button(footer,text='Export PDF',command=self.export_report,width=14).pack(side='right',padx=(10,0),pady=5)
        ttk.Button(footer,text='Clear all',command=self.clear,width=10).pack(side='right',padx=(10,0),pady=5)
        status_label=tk.Label(footer,textvariable=self.status_text,bg=BG,fg='#505b67',font=(FONT,10),anchor='w',justify='left',wraplength=300,height=2)
        # Fixed two-line height: status changes never resize the tables above.
        status_label.pack(side='left',fill='x',expand=True,padx=8,pady=5)
        status_label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(120,e.width-4)))
        self.comparison=ComparisonTab(self.notebook,self)
        self.notebook.add(self.comparison,text='Plan comparison')
        self.notebook.bind('<<NotebookTabChanged>>',lambda e:self.commit_inputs())
        self.refresh()
        split=.42 if self.course.mode=='Cylinder' else .58
        # Place the divider once the pane has its real size (and again if the window resizes).
        body.bind('<Configure>',lambda e:body.sash_place(0,0,int(e.height*split)) if e.height>1 else None)

    def toggle_files(self):
        if self.show_files.get():
            self.files.pack(fill='x',padx=12,pady=2,before=self.prior_frame)
        else:
            self.files.pack_forget()

    def refresh(self):
        c=self.course
        for fx,box in enumerate(self.modality_boxes):
            self.modality_vars[fx].set(c.modalities[fx])
            box.configure(state='readonly' if fx<c.count else 'disabled')
        self.image_fx_box.configure(values=[f'Fx {i+1}' for i in range(c.count)])
        if int(self.image_fx.get().split()[-1])>c.count: self.image_fx.set('Fx 1')
        attached=[str(i+1) for i,v in enumerate(c.screenshots[:c.count]) if v]
        self.image_status.configure(text='Attached: Fx '+', '.join(attached) if attached else 'No screenshots attached')
        self.prescription_var.set(fmt(c.prescription_gy))
        self.prescription_displayed=self.prescription_var.get()
        self.rx_summary.configure(text=f'{c.count} x {fmt(c.prescription_gy)} Gy = {fmt(c.count*c.prescription_gy)} Gy  |  Prescription BT EQD2₁₀: {fmt(c.prescription_eqd2())} Gy')
        self.patient.configure(text=f'Patient: {c.patient or "—"}   |   ID: {c.patient_id or "—"}')
        self.files.configure(text='    |    '.join(f'Fx {i+1}: {c.plans[i] or "—"} · {c.files[i] or "No file loaded"}' for i in range(c.count)))
        self.prior_vars[0].set(fmt(c.dose_per_fx))
        self.prior_vars[1].set(str(c.prior_fractions))
        self.prior_displayed=[v.get() for v in self.prior_vars]
        for (row,col),label in self.prior_display.items():
            value=(c.dose_per_fx*c.prior_fractions if col==1 else c.baseline(10 if col==2 else 3)) if row>=2 else None
            label.configure(text=fmt(value))
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
                table.headings[fx+1].configure(fg=INK if fx < c.count else '#929ba4',bg=BLUE if fx<c.count else INACTIVE)
        for _,key,metrics in c.structures:
            for metric in metrics:
                if not metric.ab:
                    continue
                k=f'{key}_{metric.key}'
                for fx in range(5):
                    value=c.values[fx].get(k)
                    self.cells[k,fx].configure(text=fmt(eqd2(value,metric.ab)) if value is not None and fx<c.count else '',bg='#fafbfc' if fx<c.count else INACTIVE,fg=INPUT_INK if fx<c.count else MUTED)
                total=c.total(k)
                result='neutral' if c.mode=='Cylinder' else status(total,metric)
                self.totals[k].configure(text=fmt(total),bg='white' if result=='neutral' else COLORS[result],fg=INPUT_INK)

        if hasattr(self,'comparison'):
            self.comparison.refresh()

    def commit_inputs(self):
        """Apply changed text only; rounded display values never replace stored data."""
        if self._committing:
            return True
        self._committing=True
        try:
            updated=deepcopy(self.course)
            if self.prescription_var.get()!=self.prescription_displayed:
                updated.set_prescription(self.prescription_var.get())
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
            parsed=import_with_volumes(self,lambda volumes:candidate.load(fx,path,volumes))
            if parsed is None:
                return
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
            self.course=Course.for_mode(self.course.mode)
            self.count.set(f'{self.course.count} Fx')
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
        output=filedialog.asksaveasfilename(title='Export Excel',initialfile=('PORTEC4' if self.course.mode=='Cylinder' else 'EMBRACE2')+'_Current_Display.xlsx',defaultextension='.xlsx',filetypes=[('Excel workbook','*.xlsx')])
        if not output:
            return
        try:
            export_workbook(self.course,template,output)
            self.status_text.set(f'Exported {Path(output).name}. Open in Excel to recalculate formulas.')
        except Exception as error:
            messagebox.showerror('Excel Export Error',str(error),parent=self)

    def set_modality(self,fx):
        self.course.modalities[fx]=self.modality_vars[fx].get()

    def add_screenshot(self,capture):
        if not self.commit_inputs(): return
        from embrace_attachments import choose_image,capture_monitor
        fx=int(self.image_fx.get().split()[-1])-1
        def accept(data):
            self.course.screenshots[fx]=data
            self.refresh()
        (capture_monitor if capture else choose_image)(self,accept)

    def remove_screenshot(self):
        if not self.commit_inputs(): return
        self.course.screenshots[int(self.image_fx.get().split()[-1])-1]=None
        self.refresh()

    def export_report(self):
        if not self.commit_inputs():
            return
        missing=[]
        fraction=int(self.image_fx.get().split()[-1])-1
        for fx in (fraction,):
            absent=[]
            if not self.course.modalities[fx]: absent.append('localization (MR/CT)')
            if not self.course.dvhs[fx] or not self.course.dvhs[fx].curves: absent.append('DVH curves (reload TXT)')
            if not self.course.screenshots[fx]: absent.append('Oncentra screenshot (Snip screen or Attach screenshot)')
            if absent: missing.append(f'Fx {fx+1}: '+', '.join(absent))
        if missing and not messagebox.askyesno('Missing report details','The following items are missing:\n\n'+'\n'.join(missing)+'\n\nExport without these items? Choose No to add them first.',default='no',parent=self):
            return
        output=filedialog.asksaveasfilename(title='Export report and companion '+('PORTEC-4' if self.course.mode=='Cylinder' else 'EMBRACE')+' worksheet PDF',initialfile=('PORTEC4' if self.course.mode=='Cylinder' else 'EMBRACE2')+'_EQD2_Report.pdf',defaultextension='.pdf',filetypes=[('PDF report','*.pdf')])
        if not output:
            return
        worksheet=Path(output).with_name(Path(output).stem+('_PORTEC4_Worksheet.pdf' if self.course.mode=='Cylinder' else '_EMBRACE_Worksheet.pdf'))
        if worksheet.exists() and not messagebox.askyesno('Replace worksheet PDF?',f'{worksheet.name} already exists. Replace it?',parent=self):
            return
        try:
            export_pdf(self.course,output,fraction=fraction)
            export_pdf(self.course,worksheet,fraction=fraction,worksheet_only=True)
            self.status_text.set(f'Exported {Path(output).name} and {worksheet.name}.')
        except Exception as error:
            messagebox.showerror('PDF Export Error',str(error),parent=self)


def packaged_smoke_test(report_path):
    """Exercise the frozen GUI and resource lookup without any patient data."""
    import json
    import tempfile
    app=App()
    try:
        app.update()
        assert app.course.count==4 and app.course.prescription_gy==7.0
        app.inputs['ctvhr_D90',0][0].set('100%')
        app.commit_inputs()
        app.prescription_var.set('8.0')
        app.commit_inputs()
        assert app.course.values[0]['ctvhr_D90']==8.0
        app.prescription_var.set('7.0')
        app.commit_inputs()
        assert app.course.values[0]['ctvhr_D90']==7.0
        assert app.files.winfo_ismapped()
        assert all(w.winfo_ismapped() for w in app.volumes.values())
        for key,total in app.totals.items():
            dose=app.inputs[key,0][1]
            eqd=app.cells[key,0]
            assert eqd.winfo_ismapped()
            assert dose.cget('bg')==BLUE and eqd.cget('bg')=='#fafbfc'
            assert int(eqd.grid_info()['row'])==int(dose.grid_info()['row'])+1
            assert total.grid_info()['row']==eqd.grid_info()['row']
            labels=eqd.master.grid_slaves(row=int(eqd.grid_info()['row']),column=0)
            assert labels[0].cget('bg')=='#fafbfc'
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
        saved=deepcopy(app.course)
        app.mode_var.set('Cylinder');app.change_mode();app.update()
        assert app.course.count==3 and app.course.baseline(10)==0
        assert not app.prior_frame.winfo_ismapped()
        assert 'gtvres_D98' not in app.totals and 'ctvir_D98' not in app.totals
        app.inputs['ctvhr_D90',0][0].set('7');app.edit_pending();app.update()
        assert app.totals['ctvhr_D90'].cget('bg')=='white'
        assert app.tables[0].headings[6].cget('text')=='Total BT\nEQD2 [Gy]'
        assert not app.comparison.headings[5].winfo_ismapped()
        app.mode_var.set('GYN');app.change_mode();app.update()
        assert app.course.values==saved.values and app.course.count==saved.count
        assert app.prior_frame.winfo_ismapped()
        Path(report_path).write_text(json.dumps({'status':'passed','checks':['GUI','precision preservation','fixed headers','ESTRO dose/EQD2 row order','fraction controls','bundled Excel export','PDF export','four-plan comparison','comparison PDF','cylinder mode']}))
    finally:
        app.destroy()


if __name__=='__main__':
    import sys
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        packaged_smoke_test(sys.argv[2])
    else:
        App().mainloop()
