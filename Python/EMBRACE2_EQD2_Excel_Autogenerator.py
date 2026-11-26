#!/usr/bin/env python3
"""EMBRACE-2 desktop dashboard. Install Python/requirements.txt for PDF export."""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
from embrace_core import Course, STRUCTURES, eqd2, fmt, status
from embrace_export import export_workbook
from embrace_import import import_with_volumes
from embrace_pdf import export_pdf
from embrace_comparison import ComparisonTab

from embrace_theme import BG, SURFACE, ALT, HEADER, INK, MUTED, BLUE, INPUT_INK, INACTIVE, COLORS, FONT, TITLE_FONT, TEXT_SIZE, apply_theme


FRAME = '#202326'


class MetricTable(tk.Frame):
    """An independently scrolling table with a stationary aligned column header."""
    def __init__(self, parent, app, title, definitions, target):
        super().__init__(parent,bg=FRAME)
        self.app = app
        tk.Label(self,text=title,bg=FRAME,fg='white',font=(FONT,TEXT_SIZE,'bold'),anchor='nw',pady=0,borderwidth=0).pack(fill='x',pady=0)
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
        if target is None:
            headings[7:]=['Goal / soft\nconstraint','Tolerance / hard\nconstraint']
        if app.course.mode=='Cylinder':
            headings[6]='Total BT\nEQD2 [Gy]'
            headings[7:]=['','']
        self.headings=[]
        for col,text in enumerate(headings):
            label=self.cell(self.head_grid,0,col,text,HEADER,bold=True)
            label.configure(height=0,font=(FONT,TEXT_SIZE,'bold'))
            self.headings.append(label)
        self.cell(self.grid_frame,0,0,'MR / CT',BG).configure(anchor='center',justify='center')
        for fx in range(5):
            var=tk.StringVar()
            box=ttk.Combobox(self.grid_frame,textvariable=var,values=['','MRI','CT','MRI + CT'],state='readonly',width=1,justify='center')
            box.grid(row=0,column=fx+1,sticky='ew',padx=(0,1),pady=(0,1))
            box.bind('<<ComboboxSelected>>',lambda e,i=fx:app.set_modality(i))
            app.modality_vars.append(var);app.modality_boxes.append(box)
        for col in (6,7,8):self.cell(self.grid_frame,0,col,'',BG)
        self.cell(self.grid_frame,1,0,'Fx date',BG).configure(anchor='center',justify='center')
        for fx in range(5):
            var=tk.StringVar()
            entry=tk.Entry(self.grid_frame,textvariable=var,bg=BLUE,fg=INK,
                disabledbackground=INACTIVE,justify='center',relief='flat',borderwidth=0,
                highlightthickness=0,width=1,font=(FONT,TEXT_SIZE))
            entry.grid(row=1,column=fx+1,sticky='nsew',padx=(0,1),pady=(0,1))
            entry.bind('<Return>',app.edit_pending);entry.bind('<FocusOut>',app.edit_pending)
            app.fx_date_vars.append(var);app.fx_date_entries.append(entry)
        for col in (6,7,8):self.cell(self.grid_frame,1,col,'',BG)
        row=2
        def point_section(title,bg=HEADER):
            nonlocal row
            heading=self.cell(self.grid_frame,row,0,title,bg,True)
            heading.grid_configure(pady=(8,2))
            for fx in range(5):
                review=ttk.Button(self.grid_frame,text=f'Review Fx {fx+1}\npoint matches',width=1,style='Compact.Load.TButton',command=lambda i=fx:app.review_loaded_points(i))
                review.grid(row=row,column=fx+1,sticky='nsew',padx=1,pady=(8,2))
                app.point_review_buttons.append(review)
                carried=self.cell(self.grid_frame,row,fx+1,'',bg)
                carried.configure(font=(FONT,TEXT_SIZE),justify='center')
                carried.grid_configure(pady=(8,2))
                carried.grid_remove()
                app.point_carry_labels.append(carried)
            for col in (6,7,8):
                self.cell(self.grid_frame,row,col,'',bg).grid_configure(pady=(8,2))
            row+=1
        def add_points(keys):
            nonlocal row
            from embrace_points import POINTS
            for key,label,_,ab in POINTS:
                if key not in keys:continue
                point_label=self.cell(self.grid_frame,row,0,label+' [Gy]','white')
                point_label.configure(padx=36,height=1);point_label.compact_point_row=True
                for fx in range(5):
                    var=tk.StringVar()
                    entry=tk.Entry(self.grid_frame,textvariable=var,bg=BLUE,fg=INK,disabledbackground=INACTIVE,
                                   justify='center',relief='flat',borderwidth=0,highlightthickness=0,width=1,font=(FONT,TEXT_SIZE))
                    entry.grid(row=row,column=fx+1,sticky='nsew',padx=1,pady=0)
                    entry.bind('<Return>',app.edit_pending);entry.bind('<FocusOut>',app.edit_pending)
                    app.point_inputs[key,fx]=var,entry
                for col in (6,7,8):self.cell(self.grid_frame,row,col,'','white')
                row+=1
                point_label=self.cell(self.grid_frame,row,0,f'EQD2{ab} [Gy]','#fafbfc')
                point_label.configure(padx=36,height=1);point_label.compact_point_row=True
                for fx in range(5):app.point_cells[key,fx]=self.cell(self.grid_frame,row,fx+1,'','#fafbfc')
                app.point_totals[key]=self.cell(self.grid_frame,row,6,'','white',bold=True)
                for col in (7,8):self.cell(self.grid_frame,row,col,'','#fafbfc')
                row+=1
        for title,key,metrics in definitions:
            if key==definitions[0][1]:
                section=self.cell(self.grid_frame,row,0,title,HEADER,True)
                section.grid_configure(pady=(8,2))
                for fx in range(5):
                    button=ttk.Button(self.grid_frame,text=f'Review Fx{fx+1}\nROI matches',width=1,
                        style='Structure.Load.TButton',command=lambda i=fx:app.review_structure_matches(i))
                    button.grid(row=row,column=fx+1,sticky='nsew',padx=1,pady=(8,2))
                    app.structure_review_buttons.append(button)
                    label=self.cell(self.grid_frame,row,fx+1,'',HEADER)
                    label.configure(font=(FONT,TEXT_SIZE),justify='center')
                    label.grid_configure(pady=(8,2));label.grid_remove()
                    app.structure_carry_labels.append(label)
                for col in (6,7,8):self.cell(self.grid_frame,row,col,'',HEADER).grid_configure(pady=(8,2))
            else:
                section=tk.Label(self.grid_frame,text=title,bg=HEADER,fg=INK,anchor='w',font=(FONT,TEXT_SIZE,'bold'),padx=7,pady=0)
                section.grid(row=row,column=0,columnspan=9,sticky='nsew',pady=(8 if row else 0,2))
            row+=1
            for metric in metrics:
                k=f'{key}_{metric.key}'
                self.cell(self.grid_frame,row,0,metric.label,'white').configure(padx=36)
                for fx in range(5):
                    if metric.key == 'volume':
                        app.volumes[k,fx]=self.cell(self.grid_frame,row,fx+1,'','white')
                    else:
                        var=tk.StringVar()
                        entry=tk.Entry(self.grid_frame,textvariable=var,bg=BLUE,fg=INK,
                                       disabledbackground='#eef0f2',disabledforeground='#7b858f',
                                       justify='center',relief='flat',borderwidth=0,width=1,font=(FONT,TEXT_SIZE),
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
                    self.cell(self.grid_frame,row,0,label,'#fafbfc').configure(padx=36)
                    for fx in range(5):
                        app.cells[k,fx]=self.cell(self.grid_frame,row,fx+1,'','#fafbfc')
                    app.totals[k]=self.cell(self.grid_frame,row,6,'','white',bold=True)
                    self.cell(self.grid_frame,row,7,metric.goal,'#fafbfc')
                    self.cell(self.grid_frame,row,8,metric.hard,'#fafbfc')
                    row+=1
        if app.course.mode=='GYN':
            point_section('REFERENCE POINTS')
            self.cell(self.grid_frame,row,0,'Point source date (RD)','#fafbfc')
            for fx in range(5):app.point_dates[fx]=self.cell(self.grid_frame,row,fx+1,'','#fafbfc')
            for col in (6,7,8):self.cell(self.grid_frame,row,col,'','#fafbfc')
            row+=1
            from embrace_points import REFERENCE_KEYS
            add_points(REFERENCE_KEYS)
        self.cylinder=app.course.mode=='Cylinder'
        if self.cylinder:
            for grid in (self.head_grid,self.grid_frame):
                for child in grid.winfo_children():
                    if int(child.grid_info().get('column',0))>=7: child.grid_remove()
        self.bind_wheel(outer)

    @staticmethod
    def cell(parent,row,col,text,bg,bold=False):
        label=tk.Label(parent,text=text,bg=bg,fg=INK,anchor='w' if col == 0 else 'center',
                       font=(FONT,TEXT_SIZE,'bold' if bold else 'normal'),padx=5,pady=0,width=1)
        parent.rowconfigure(row,minsize=getattr(parent.winfo_toplevel(),'table_row_height',0))
        label.grid(row=row,column=col,sticky='nsew',padx=(0,1),pady=(0,1))
        return label

    def resize(self,event):
        # Identical pixel widths ensure header/body alignment at any window size.
        self.canvas.itemconfigure(self.window,width=event.width)
        proportions=[185,118,118,118,118,118,115,95,95]
        if self.cylinder: proportions=[185,118,118,118,118,118,115,0,0]
        widths=[int(event.width*w/sum(proportions)) for w in proportions]
        widths[0]+=event.width-sum(widths)
        for grid in (self.head_grid,self.grid_frame,self.app.fraction_grid,self.app.prior_frame):
            for col,width in enumerate(widths):
                grid.columnconfigure(col,minsize=width,weight=0)
        # Wrap controls at the shared text size rather than shrinking their fonts.
        button_font=tkfont.Font(self,font=(FONT,TEXT_SIZE,'bold'))
        def wrap(text,width):
            lines=[];line=''
            for word in text.split():
                candidate=f'{line} {word}'.strip()
                if line and button_font.measure(candidate)>width:
                    lines.append(line);line=word
                else:line=candidate
            return '\n'.join(lines+[line])
        for fx in range(5):
            available=max(40,widths[fx+1]-14)
            for button,text in ((self.app.buttons[fx],f'Load Fx{fx+1} DVH.txt'),
                                (self.app.dicom_buttons[fx],f'Load Fx{fx+1} DCMs')):
                button.configure(text=wrap(text,available))
            self.app.structure_review_buttons[fx].configure(text=f'Review Fx{fx+1}\nROI matches')
            if self.app.point_review_buttons:
                self.app.point_review_buttons[fx].configure(text=wrap(f'Review Fx {fx+1} point matches',available))
        for label in self.app.point_carry_labels+self.app.structure_carry_labels:
            col=int(label.grid_info().get('column',1)) if label.winfo_manager() else 1
            label.configure(wraplength=max(40,widths[col]-10))
        for label in self.app.prior_frame.winfo_children():
            if isinstance(label,tk.Label):
                col=int(label.grid_info()['column'])
                label.configure(wraplength=max(40,widths[col]-2*int(label.cget('padx'))-4),justify='left' if col==0 else 'center')
        for label in self.grid_frame.grid_slaves(column=0):
            if isinstance(label,tk.Label) and int(label.grid_info().get('columnspan',1))==1:
                if getattr(label,'compact_point_row',False):
                    label.configure(wraplength=0,height=1)
                else:
                    label.configure(wraplength=max(80,widths[0]-2*int(label.cget('padx'))-4),height=0)
        self.headings[0].configure(text='Structure / dose\nparameter',anchor='center',justify='center')
        for col,label in enumerate(self.headings):
            label.configure(wraplength=max(40,widths[col]-12),height=0)

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
        self.dvh_folder=None
        self.title('EMBRACE-2 EQD2 Excel Autogenerator')
        # Fit the screen's height; cap width so table columns never stretch too wide.
        height=min(980,self.winfo_screenheight()-90)
        self.geometry(f'1200x{height}+{max(0,(self.winfo_screenwidth()-1200)//2)}+0')
        self.minsize(1020,min(680,height))
        self.maxsize(1400,self.winfo_screenheight())
        self.configure(bg=BG)
        apply_theme(self)
        row_probe=ttk.Combobox(self,width=1,state='readonly')
        self.table_row_height=row_probe.winfo_reqheight()+1
        row_probe.destroy()
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
        self.point_inputs,self.point_cells,self.point_totals,self.point_dates={},{},{},{}
        self.point_displayed={}
        self.displayed={}
        self.status_text=tk.StringVar(value='')
        # Drag the divider to allocate space; setup itself stays stationary.
        content=self.dashboard_split=tk.PanedWindow(self.dashboard,orient='vertical',
            bg=FRAME,borderwidth=0,sashwidth=2,sashrelief='flat',showhandle=False,sashcursor='sb_v_double_arrow')
        setup=tk.Frame(content,bg=FRAME)
        setup.pack_propagate(False)
        self.top=tk.Frame(setup,bg=FRAME)
        self.top.pack(fill='x')
        file_content=tk.Frame(setup,bg=FRAME)
        file_content.pack(fill='both',expand=True)

        top=tk.Frame(self.top,bg=FRAME)
        top.pack(fill='x',padx=12,pady=(2,2))
        tk.Label(top,text=self.course.title+'  Course Dashboard',bg=FRAME,fg='white',font=(TITLE_FONT,14,'bold')).pack(side='left')
        tk.Label(top,text='UFHPTI',bg=FRAME,fg='#fa4a00',font=(FONT,12,'bold')).pack(side='right')
        self.patient=tk.Label(top,bg=FRAME,fg='white',font=(FONT,TEXT_SIZE),anchor='e')
        self.patient.pack(side='right',padx=16)
        controls=tk.Frame(self.top,bg=BG,padx=6,pady=2)
        controls.pack(fill='x',padx=12,pady=2)
        self.count=tk.StringVar(value=f'{self.course.count} Fx')
        count=ttk.Combobox(controls,textvariable=self.count,style='Editable.TCombobox',values=['3 Fx','4 Fx','5 Fx'],width=5,state='readonly')
        count.pack(side='left',padx=(4,6))
        count.bind('<<ComboboxSelected>>',self.change_count)
        self.rx_frame=controls
        tk.Label(self.rx_frame,text='×',bg=BG,fg=MUTED,font=(FONT,TEXT_SIZE)).pack(side='left',padx=(0,6))
        self.prescription_var=tk.StringVar(value='7.0')
        prescription=tk.Entry(self.rx_frame,textvariable=self.prescription_var,bg=BLUE,fg=INPUT_INK,
                              justify='center',relief='flat',borderwidth=0,highlightthickness=1,
                              highlightbackground=BLUE,highlightcolor='#327ca5',font=(FONT,TEXT_SIZE),width=6)
        prescription.pack(side='left')
        prescription.bind('<Return>',self.edit_pending)
        prescription.bind('<FocusOut>',self.edit_pending)
        tk.Label(self.rx_frame,text='Gy/Fx',bg=BG,fg=INK,font=(FONT,TEXT_SIZE)).pack(side='left',padx=(6,12))
        self.rx_summary=tk.Label(self.rx_frame,bg=BG,fg=INK,font=(FONT,TEXT_SIZE))
        self.rx_summary.pack(side='left')
        cards=tk.Frame(file_content,bg='#d3d8dc')
        tk.Frame(cards,bg=FRAME).grid(row=0,column=6,columnspan=3,rowspan=8,sticky='nsew')
        self.fraction_grid=cards
        cards.pack(fill='x',padx=12,pady=0)
        self.buttons=[];self.file_labels=[];self.dvh_date_labels=[];self.source_dates=[];self.rp_date_labels=[];self.dicom_buttons=[];self.ct_date_labels=[];self.point_review_buttons=[];self.point_carry_labels=[];self.structure_review_buttons=[];self.structure_carry_labels=[]
        self.fraction_titles=[]
        self.modality_vars=[];self.modality_boxes=[];self.fx_date_vars=[];self.fx_date_entries=[];self.fx_date_displayed=[]
        # All fractions share one grid: wrapped names expand the same row
        # across every fraction, instead of shifting individual card contents.
        row_labels=('Fraction','DVH File ⓘ','DVH Name','DVH Date','Plan DICOM ⓘ','RP Name','RP Date','CT Date')
        for row,text in enumerate(row_labels):
            label=MetricTable.cell(cards,row,0,text,HEADER if row==0 else BG,row==0)
            label.configure(font=(FONT,TEXT_SIZE,'bold') if row==0 else (FONT,TEXT_SIZE),anchor='e',justify='right',padx=10,pady=0)
            if row==1:
                self.bind_upload_help(label,'DVH File','Go to DVH. Select Absolute Dose and Absolute Volume. Dump to file. Upload DVH txt here.')
            elif row==4:
                self.bind_upload_help(label,'Plan DICOM','Select RP, RD, and/or CT files.')
        for fx in range(5):
            col=fx+1
            title=MetricTable.cell(cards,0,col,f'Fx {fx+1}',HEADER,True)
            title.configure(font=(FONT,TEXT_SIZE,'bold'),pady=0)
            self.fraction_titles.append(title)
            button=ttk.Button(cards,text=f'Load Fx{fx+1} DVH.txt',width=1,style='File.Load.TButton',command=lambda i=fx:self.load(i))
            button.grid(row=1,column=col,sticky='nsew',padx=(0,1),pady=(0,1))
            self.buttons.append(button)
            name=MetricTable.cell(cards,2,col,'—',SURFACE)
            self.file_labels.append(name)
            dvh_date=MetricTable.cell(cards,3,col,'—',SURFACE)
            self.dvh_date_labels.append(dvh_date)
            dicom=ttk.Button(cards,text=f'Load Fx{fx+1} DCMs',width=1,style='File.Load.TButton',command=lambda i=fx:self.load_dicoms(i))
            dicom.grid(row=4,column=col,sticky='nsew',padx=(0,1),pady=(0,1))
            self.dicom_buttons.append(dicom)
            source=MetricTable.cell(cards,5,col,'—',SURFACE)
            self.source_dates.append(source)
            rp_date=MetricTable.cell(cards,6,col,'—',SURFACE)
            self.rp_date_labels.append(rp_date)
            ct=MetricTable.cell(cards,7,col,'—',SURFACE)
            self.ct_date_labels.append(ct)
            for label in (name,dvh_date,source,rp_date,ct):
                label.configure(font=(FONT,TEXT_SIZE),anchor='center',justify='center',padx=5,pady=0)
                label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(40,e.width-8)))
        attachments=tk.Frame(controls,bg=BG,padx=0,pady=0)
        attachments.pack(side='left',before=count)
        tk.Frame(controls,bg='#d3d8dc',width=1,height=22).pack(side='left',before=count,padx=12)
        tk.Label(controls,text='BT Rx:',bg=BG,fg=INK,font=(FONT,TEXT_SIZE)).pack(side='left',before=count,padx=(0,4))
        tk.Label(attachments,text='PDF fraction',bg=BG,fg='#003f5c',font=(FONT,TEXT_SIZE,'bold')).pack(side='left')
        self.image_fx=tk.StringVar(value='Fx 1')
        self.image_fx_box=ttk.Combobox(attachments,textvariable=self.image_fx,state='readonly',width=5,style='Report.TCombobox',font=(FONT,TEXT_SIZE,'bold'),justify='center')
        self.image_fx_box.pack(side='left',padx=5)
        ttk.Button(attachments,text='Snip Screen',style='Primary.TButton',command=lambda:self.add_screenshot(True)).pack(side='left',padx=3)
        image_menu=ttk.Menubutton(attachments,text='Screenshots')
        menu=tk.Menu(image_menu,tearoff=False)
        menu.add_command(label='Add file…',command=lambda:self.add_screenshot(False))
        menu.add_command(label='Snip screen…',command=lambda:self.add_screenshot(True))
        menu.add_separator();menu.add_command(label='Manage images…',command=self.remove_screenshot)
        image_menu.configure(menu=menu);image_menu.pack(side='left',padx=3)
        self.image_status=tk.Label(attachments,text='',bg=BG,fg=MUTED,font=(FONT,TEXT_SIZE))
        self.image_status.pack(side='left',padx=6)
        self.show_files=tk.BooleanVar(value=True)
        bt_heading=tk.Label(self.top,text='BRACHYTHERAPY',bg=FRAME,fg='white',font=(FONT,TEXT_SIZE,'bold'),anchor='w')
        bt_heading.pack(fill='x',padx=14,pady=(4,1),before=controls)
        self.prior_frame=tk.Frame(self.top,bg='#d3d8dc')
        self.prior_frame.pack(fill='x',padx=12,pady=(0,2),before=bt_heading)
        ebrt_heading=tk.Label(self.top,text='EXTERNAL BEAM THERAPY',bg=FRAME,fg='white',font=(FONT,TEXT_SIZE,'bold'),anchor='w')
        ebrt_heading.pack(fill='x',padx=14,pady=(1,1),before=self.prior_frame)
        for col,(title,weight) in enumerate((('Parameter',4),('Value',1),('Tumour EQD2₁₀ [Gy]',2),('OAR EQD2₃ [Gy]',2))):
            MetricTable.cell(self.prior_frame,0,col,title,HEADER,True)
            self.prior_frame.columnconfigure(col,weight=0)
        self.prior_vars=[tk.StringVar(),tk.StringVar()]
        self.prior_display={}
        for row,(text,var) in enumerate(zip(('Dose per fraction [Gy]','Fractions without central shield'),self.prior_vars),1):
            MetricTable.cell(self.prior_frame,row,0,text,'white').configure(padx=12)
            entry=tk.Entry(self.prior_frame,textvariable=var,bg=BLUE,fg=INPUT_INK,justify='center',relief='flat',borderwidth=0,highlightthickness=0,font=(FONT,TEXT_SIZE),width=6)
            entry.grid(row=row,column=1,sticky='nsew',padx=(0,1),pady=(0,1))
            entry.bind('<Return>',self.edit_pending);entry.bind('<FocusOut>',self.edit_pending)
            for col in (2,3):MetricTable.cell(self.prior_frame,row,col,'','white')
        MetricTable.cell(self.prior_frame,3,0,'Total dose [Gy]','white',True).configure(padx=12)
        for col in (1,2,3):self.prior_display[3,col]=MetricTable.cell(self.prior_frame,3,col,'','white',True)
        # Continue the worksheet grid across the spare width without stretching EBRT.
        for col in range(4,9):
            self.prior_frame.columnconfigure(col,weight=0)
            for row in range(4):
                MetricTable.cell(self.prior_frame,row,col,'','white')
        for widget in self.prior_frame.winfo_children():
            current=str(widget.cget('font'))
            widget.configure(font=(FONT,TEXT_SIZE,'bold' if 'bold' in current else 'normal'))
        if self.course.mode=='Cylinder':
            self.prior_frame.pack_forget();ebrt_heading.pack_forget()
        worksheet=tk.Frame(content,bg=FRAME)
        resize_grip=self.resize_grip=tk.Canvas(worksheet,height=7,highlightthickness=0,
            bg=FRAME,cursor='sb_v_double_arrow')
        resize_grip.pack(fill='x')
        def draw_resize_grip(event):
            resize_grip.delete('all')
            center=event.width/2
            resize_grip.create_line(center-12,3,center+12,3,fill='#8a969f',width=2)
        resize_grip.bind('<Configure>',draw_resize_grip)
        body=MetricTable(worksheet,self,'PORTEC-4 EQD2' if self.course.mode=='Cylinder' else 'EMBRACE-2 DOSE/EQD2',self.course.structures,None)
        self.tables=[body]
        footer=self.footer=tk.Frame(self.dashboard,bg=BG)
        # Reserve the footer before allocating space to setup and worksheet.
        # Child requested sizes must never push export actions off screen.
        footer.pack(side='bottom',fill='x',padx=12,pady=(2,6))
        content.pack(side='top',fill='both',expand=True)
        content.add(setup,minsize=120,stretch='never')
        content.add(worksheet,minsize=130,stretch='always')
        body.pack(fill='both',expand=True,padx=12,pady=(0,3))
        self.chooser.lift()
        divider_adjusted=False
        drag_offset=0
        def start_resize(event):
            nonlocal divider_adjusted,drag_offset
            divider_adjusted=True
            drag_offset=event.y_root-content.winfo_rooty()-content.sash_coord(0)[1]
        def drag_resize(event):
            y=event.y_root-content.winfo_rooty()-drag_offset
            content.sash_place(0,0,max(120,min(y,content.winfo_height()-137)))
        def sash_pressed(event):
            nonlocal divider_adjusted
            if content.identify(event.x,event.y):divider_adjusted=True
        resize_grip.bind('<ButtonPress-1>',start_resize)
        resize_grip.bind('<B1-Motion>',drag_resize)
        resize_grip.bind('<Enter>',lambda e:resize_grip.configure(bg='#35434c'))
        resize_grip.bind('<Leave>',lambda e:resize_grip.configure(bg=FRAME))
        content.bind('<ButtonPress-1>',sash_pressed,add='+')
        def position_divider(event=None):
            if divider_adjusted or not content.winfo_exists() or content.winfo_height()<260:return
            # Expand through CT Date by default, while retaining worksheet access
            # on small displays. Once dragged, preserve the user's allocation.
            height=max(120,min(self.top.winfo_reqheight()+file_content.winfo_reqheight()+2,
                               content.winfo_height()-137))
            if abs(content.sash_coord(0)[1]-height)>1:content.sash_place(0,0,height)
        content.bind('<Configure>',position_divider)
        self.top.bind('<Configure>',position_divider,add='+')
        file_content.bind('<Configure>',position_divider,add='+')
        self.after_idle(position_divider)
        ttk.Button(footer,text='Export Excel',command=self.export,width=14).pack(side='right',padx=(10,8),pady=5)
        ttk.Button(footer,text='Export PDF',command=self.export_report,width=14).pack(side='right',padx=(10,0),pady=5)
        ttk.Button(footer,text='Clear all',command=self.clear,width=10).pack(side='right',padx=(10,0),pady=5)
        status_label=tk.Label(footer,textvariable=self.status_text,bg=BG,fg='#505b67',font=(FONT,TEXT_SIZE),anchor='w',justify='left',wraplength=300,height=2)
        # Fixed two-line height: status changes never resize the tables above.
        status_label.pack(side='left',fill='x',expand=True,padx=8,pady=5)
        status_label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(120,e.width-4)))
        self.comparison=ComparisonTab(self.notebook,self)
        self.notebook.add(self.comparison,text='Plan comparison')
        from embrace_preview import PDFPreviewTab
        self.preview=PDFPreviewTab(self.notebook,self)
        self.notebook.add(self.preview,text='PDF preview')
        self.notebook.bind('<<NotebookTabChanged>>',self.tab_changed)
        self.refresh()

    def bind_upload_help(self, label, title, instructions):
        """Expose upload guidance on hover, click, and keyboard focus."""
        tooltip=None
        def hide(event=None):
            nonlocal tooltip
            if tooltip is not None:
                tooltip.destroy();tooltip=None
        def show(event=None):
            nonlocal tooltip
            if tooltip is not None:return
            tooltip=tk.Toplevel(self)
            tooltip.overrideredirect(True)
            tk.Label(tooltip,text=instructions,bg=SURFACE,fg=INK,font=(FONT,TEXT_SIZE),
                     justify='left',wraplength=320,padx=10,pady=8,
                     relief='solid',borderwidth=1).pack()
            tooltip.update_idletasks()
            x=min(label.winfo_rootx(),self.winfo_screenwidth()-tooltip.winfo_reqwidth()-8)
            y=min(label.winfo_rooty()+label.winfo_height(),self.winfo_screenheight()-tooltip.winfo_reqheight()-8)
            tooltip.geometry(f'+{max(0,x)}+{max(0,y)}')
        def details(event=None):
            hide()
            messagebox.showinfo(title,instructions,parent=self)
            return 'break'
        label.configure(cursor='hand2',takefocus=True)
        label.bind('<Enter>',show);label.bind('<Leave>',hide)
        label.bind('<FocusIn>',show);label.bind('<FocusOut>',hide)
        label.bind('<Button-1>',details)
        label.bind('<Return>',details);label.bind('<space>',details)
        label.bind('<Destroy>',hide)

    def tab_changed(self,event=None):
        if self.notebook.select()==str(self.preview):self.preview.refresh_document()
        else:self.commit_inputs()

    def toggle_files(self):
        for label in self.file_labels:
            if self.show_files.get():label.grid()
            else:label.grid_remove()

    def refresh(self):
        c=self.course
        self.fx_date_displayed=list(c.fx_dates)
        for fx,var in enumerate(self.fx_date_vars):
            var.set(c.fx_dates[fx] if fx<c.count else '')
            self.fx_date_entries[fx].configure(state='normal' if fx<c.count else 'disabled')
        for fx,box in enumerate(self.modality_boxes):
            self.modality_vars[fx].set(c.modalities[fx] if fx<c.count else '')
            box.configure(state='readonly' if fx<c.count else 'disabled')
        self.image_fx_box.configure(values=[f'Fx {i+1}' for i in range(c.count)])
        if int(self.image_fx.get().split()[-1])>c.count: self.image_fx.set('Fx 1')
        attached=[f'Fx {i+1}: {len(c.screenshot_images(i))}' for i in range(c.count) if c.screenshot_images(i)]
        self.image_status.configure(text='Images — '+', '.join(attached) if attached else '')
        self.prescription_var.set(fmt(c.prescription_gy))
        self.prescription_displayed=self.prescription_var.get()
        self.rx_summary.configure(text=f'→  Total {fmt(c.count*c.prescription_gy)} Gy   ·   EQD2₁₀ {fmt(c.prescription_eqd2())} Gy')
        self.patient.configure(text=f'Patient: {c.patient or "—"}   |   ID: {c.patient_id or "—"}')
        for fx,label in enumerate(self.file_labels):
            date=c.dvhs[fx].source_date if c.dvhs[fx] else ''
            text=c.files[fx] or '—'
            self.dvh_date_labels[fx].configure(text=(date or '—') if fx<c.count else '—',bg=SURFACE if fx<c.count else INACTIVE,fg=INK if fx<c.count else MUTED)
            label.configure(text=text if fx<c.count else '—',height=0 if c.files[fx] and fx<c.count else 1,bg=SURFACE if fx<c.count else INACTIVE,fg=INK if fx<c.count else MUTED)
            rp_text=c.rp_names[fx] or '—'
            self.source_dates[fx].configure(text=rp_text if fx<c.count else '—',bg=SURFACE if fx<c.count else INACTIVE,fg=INK if fx<c.count else MUTED)
            self.rp_date_labels[fx].configure(text=(c.rp_dates[fx] or '—') if fx<c.count else '—',bg=SURFACE if fx<c.count else INACTIVE,fg=INK if fx<c.count else MUTED)
        for fx,button in enumerate(self.structure_review_buttons):
            carried=fx<c.count and c.dvhs[fx] is None and ' (carried from Fx' in c.files[fx]
            label=self.structure_carry_labels[fx]
            if carried:
                button.grid_remove()
                label.configure(text=c.files[fx].rsplit(' (',1)[-1].rstrip(')').replace('carried','Carried',1))
                label.grid()
            else:
                label.grid_remove();button.grid()
            button.configure(state='normal' if fx<c.count and c.dvhs[fx] is not None else 'disabled')
        for fx,button in enumerate(self.point_review_buttons):
            source=c.point_sources[fx]
            carried=fx<c.count and source is not None and source!=fx and not c.point_explicit[fx]
            label=self.point_carry_labels[fx]
            if carried:
                button.grid_remove()
                label.configure(text=f'Carried from Fx{source+1}')
                label.grid()
            else:
                label.grid_remove()
                button.grid()
            button.configure(state='normal' if fx<c.count and c.mode=='GYN' and c.point_records[fx] else 'disabled')
        for fx,title in enumerate(self.fraction_titles):
            title.configure(bg=HEADER if fx<c.count else INACTIVE,fg=INK if fx<c.count else MUTED)
        for fx,button in enumerate(self.dicom_buttons):
            button.configure(state='normal' if fx<c.count else 'disabled')
            self.ct_date_labels[fx].configure(text=(c.ct_dates[fx] or '—') if fx<c.count else '—',bg=SURFACE if fx<c.count else INACTIVE,fg=INK if fx<c.count else MUTED)
        self.prior_vars[0].set(fmt(c.dose_per_fx))
        self.prior_vars[1].set(str(c.prior_fractions))
        self.prior_displayed=[v.get() for v in self.prior_vars]
        for (_,col),label in self.prior_display.items():
            value=c.dose_per_fx*c.prior_fractions if col==1 else c.baseline(10 if col==2 else 3)
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

        from embrace_points import POINTS
        for key,_,_,ab in POINTS:
            if (key,0) not in self.point_inputs:continue
            values=[]
            for fx in range(5):
                var,entry=self.point_inputs[key,fx]
                value=c.point_doses[fx].get(key)
                var.set(fmt(value));self.point_displayed[key,fx]=var.get()
                entry.configure(state='normal' if fx<c.count else 'disabled')
                biological=eqd2(value,ab) if value is not None and fx<c.count else None
                self.point_cells[key,fx].configure(text=fmt(biological),bg='#fafbfc' if fx<c.count else INACTIVE)
                if biological is not None:values.append(biological)
            self.point_totals[key].configure(text=fmt(sum(values)+c.baseline(ab)) if values else '')
        for fx,label in self.point_dates.items():
            label.configure(text=(c.point_source_dates[fx] or '—') if fx<c.count else '',bg='#fafbfc' if fx<c.count else INACTIVE)
        if hasattr(self,'comparison'):
            self.comparison.refresh()

    def commit_inputs(self):
        """Apply changed text only; rounded display values never replace stored data."""
        if self._committing:
            return True
        self._committing=True
        try:
            updated=deepcopy(self.course)
            for fx,var in enumerate(self.fx_date_vars):
                if fx<updated.count and var.get()!=self.fx_date_displayed[fx]:
                    updated.set_fx_date(fx,var.get())
            if self.prescription_var.get()!=self.prescription_displayed:
                updated.set_prescription(self.prescription_var.get())
            for (key,fx),(var,_) in self.inputs.items():
                if fx<updated.count and var.get()!=self.displayed[key,fx]:
                    updated.edit(fx,key,var.get())
            point_doses=deepcopy(updated.point_doses)
            changed=False
            for (key,fx),(var,_) in self.point_inputs.items():
                if fx<updated.count and var.get()!=self.point_displayed[key,fx]:
                    point_doses[fx][key]=var.get();changed=True
            if changed:updated.set_report_details(updated.ct_dates,point_doses)
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

    def choose_dvh_file(self,title):
        options={}
        if self.dvh_folder and Path(self.dvh_folder).is_dir():
            options['initialdir']=self.dvh_folder
        path=filedialog.askopenfilename(parent=self,title=title,
            filetypes=[('DVH text files','*.txt'),('All files','*')],**options)
        if path:
            self.dvh_folder=str(Path(path).parent)
        return path

    def load(self,fx):
        if not self.commit_inputs():
            return
        path=self.choose_dvh_file(f'Load Fx {fx+1} DVH TXT')
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

    def load_dicoms(self,fx):
        if not self.commit_inputs():return
        if fx>=self.course.count:return
        options={'initialdir':self.dvh_folder} if self.dvh_folder else {}
        paths=filedialog.askopenfilenames(parent=self,title=f'Fx {fx+1}: select RP, RD and CT files',filetypes=[('DICOM files','*.dcm'),('All files','*')],**options)
        if not paths:return
        try:
            from embrace_dicom import read_fraction_dicoms
            result=read_fraction_dicoms(paths,self.course.patient_id)
            if result is None:return
            candidate=deepcopy(self.course)
            candidate.patient_id=candidate.patient_id or result['patient_id']
            for plan in self.comparison.model.plans:
                if plan and plan.patient_id and plan.patient_id.casefold()!=candidate.patient_id.casefold():
                    raise ValueError('DICOM patient does not match the loaded comparison plans.')
            if result['ct_date'] is not None:candidate.ct_dates[fx]=result['ct_date']
            if result['rp_name'] is not None:
                candidate.rp_names[fx]=result['rp_name'];candidate.rp_dates[fx]=result['rp_date']
            points=result['points']
            if points is not None and candidate.mode=='GYN':
                candidate.set_points(fx,points,result['date'])
            self.course=candidate;self.dvh_folder=str(Path(paths[0]).parent);self.refresh()
            matched=sum(bool(p['target']) for p in points or [])
            self.status_text.set(f'Fx {fx+1}: DICOM loaded. '+(f'{matched} point doses matched. ' if points is not None else '')+' '.join(result['warnings']))
            if points and candidate.mode=='GYN' and any(not p['target'] for p in points):self.review_loaded_points(fx)
        except Exception as error:messagebox.showerror('DICOM import',str(error),parent=self)

    def review_structure_matches(self, fx):
        if not self.commit_inputs():return
        if fx>=self.course.count or self.course.dvhs[fx] is None:return
        parsed=self.course.dvhs[fx]
        dialog=tk.Toplevel(self);dialog.title(f'Fx {fx+1}: review structure matches')
        dialog.transient(self);dialog.grab_set()
        tk.Label(dialog,text='Review exported structures and their worksheet matches. Each destination can be used once.',
                 wraplength=650,justify='left').pack(fill='x',padx=12,pady=10)
        area=tk.Frame(dialog);area.pack(fill='both',expand=True,padx=12)
        canvas=tk.Canvas(area,highlightthickness=0,width=640,height=360)
        scroll=ttk.Scrollbar(area,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        rows=tk.Frame(canvas);window=canvas.create_window((0,0),window=rows,anchor='nw')
        rows.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        rows.columnconfigure(0,weight=1);rows.columnconfigure(1,weight=1)
        for col,title in enumerate(('Exported structure','Worksheet structure')):
            tk.Label(rows,text=title,font=(FONT,TEXT_SIZE,'bold')).grid(row=0,column=col,padx=8,pady=4)
        choices={'Unassigned':None,**{title:key for title,key,_ in self.course.structures}}
        inverse={key:title for title,key in choices.items()}
        selections=[];boxes=[]
        for row,(name,target) in enumerate(parsed.structure_matches.items(),1):
            label=tk.Label(rows,text=name,anchor='w',justify='left',wraplength=290)
            label.grid(row=row,column=0,sticky='ew',padx=8,pady=3)
            var=tk.StringVar(value=inverse.get(target,'Unassigned'))
            box=ttk.Combobox(rows,textvariable=var,state='readonly',width=26,justify='right')
            box.grid(row=row,column=1,sticky='ew',padx=8,pady=3)
            selections.append((name,var));boxes.append(box)
        def update_choices(*_):
            selected=[var.get() for _,var in selections]
            for i,box in enumerate(boxes):
                taken={v for j,v in enumerate(selected) if i!=j and v!='Unassigned'}
                box.configure(values=[label for label in choices if label not in taken])
        for _,var in selections:var.trace_add('write',update_choices)
        update_choices()
        def apply():
            try:
                matches={name:choices[var.get()] for name,var in selections}
                candidate=deepcopy(self.course)
                result=import_with_volumes(dialog,lambda volumes:candidate.rematch_structures(fx,matches,volumes))
                if result is None:return
                self.course=candidate;self.refresh()
                self.status_text.set(f'Fx {fx+1}: structure matches updated.')
                dialog.destroy()
            except (ValueError,OSError) as error:
                messagebox.showerror('Structure matches',str(error),parent=dialog)
        buttons=tk.Frame(dialog);buttons.pack(fill='x',padx=12,pady=10)
        ttk.Button(buttons,text='Close',command=dialog.destroy).pack(side='left')
        ttk.Button(buttons,text='Apply matches',command=apply).pack(side='right')

    def review_loaded_points(self,fx):
        if not self.commit_inputs():return
        if fx>=self.course.count or not self.course.point_records[fx]:return
        from embrace_points import POINTS
        dialog=tk.Toplevel(self);dialog.title(f'Fx {fx+1}: review imported points');dialog.transient(self);dialog.grab_set()
        tk.Label(dialog,text='Matched doses are already filled. Assign any remaining points, or leave them unassigned.').grid(row=0,column=0,columnspan=4,padx=12,pady=8)
        choices={'Unassigned':None,**{label:key for key,label,_,_ in POINTS}}
        inverse={value:key for key,value in choices.items()};selections=[];match_boxes=[]
        records=deepcopy(self.course.point_records[fx])
        for col,title in enumerate(('Point Set Name','Point Name','Dose [Gy]','Worksheet point')):
            tk.Label(dialog,text=title,font=(FONT,TEXT_SIZE,'bold')).grid(row=1,column=col,padx=8)
        for row,point in enumerate(records,2):
            for col,value in enumerate((point['group'],point['name'],fmt(point['dose']))):
                tk.Label(dialog,text=value).grid(row=row,column=col,padx=8,pady=3)
            var=tk.StringVar(value=inverse[point['target']]);selections.append(var)
            box=ttk.Combobox(dialog,textvariable=var,values=list(choices),state='readonly',width=30)
            box.grid(row=row,column=3,padx=8);match_boxes.append(box)
        def update_choices(*_):
            selected=[var.get() for var in selections]
            for index,box in enumerate(match_boxes):
                taken={value for i,value in enumerate(selected) if i!=index and value!='Unassigned'}
                box.configure(values=[label for label in choices if label not in taken])
        for var in selections:var.trace_add('write',update_choices)
        update_choices()
        def apply():
            targets=[choices[v.get()] for v in selections];used=[v for v in targets if v]
            if len(used)!=len(set(used)):
                messagebox.showerror('Duplicate point','Choose a different worksheet destination for each point.',parent=dialog);return
            for point,target in zip(records,targets):point['target']=target
            self.course.set_points(fx,records,self.course.point_source_dates[fx])
            self.refresh();dialog.destroy()
        ttk.Button(dialog,text='Apply matches',command=apply).grid(row=len(records)+2,column=3,padx=8,pady=10)
        ttk.Button(dialog,text='Close',command=dialog.destroy).grid(row=len(records)+2,column=0,padx=8,pady=10)

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

    def file_help(self):
        messagebox.showinfo('Which files do I load?',
            'START HERE — same worksheet workflow\n'
            'Use Load Fx 1 TXT, Load Fx 2 TXT, etc. to load each fraction’s Oncentra DVH text export (.txt).\n\n'
            'OPTIONAL POINT DOSES\n'
            'Use Load DICOM under the matching fraction on the dashboard.\n'
            'RD…dcm = calculated point doses (required for point import).\n'
            'RP…dcm = matching plan / point-set names (recommended).\n'
            'Select RP, RD and CT files together. Matched points fill automatically; ambiguous points open for review.\n\n'
            'IMAGES AND DATES\n'
            'Attach screenshot or Snip screen adds an image to the selected PDF fraction.\n'
            'Use Load DICOM under the matching Fx to select RP, RD and CT files together. CT dates and matched point doses fill automatically. RS files are not required.\n\n'
            'PLAN COMPARISON\n'
            'Load one DVH TXT file per candidate plan. RD/RP files are not needed there.',parent=self)

    def add_screenshot(self,capture):
        if not self.commit_inputs(): return
        from embrace_attachments import choose_image,capture_monitor
        fx=int(self.image_fx.get().split()[-1])-1
        def accept(data):
            self.course.screenshots[fx]=self.course.screenshot_images(fx)+[data]
            self.refresh()
            if self.notebook.select()==str(self.preview):
                self.preview.refresh_document()
        (capture_monitor if capture else choose_image)(self,accept)

    def remove_screenshot(self):
        if not self.commit_inputs(): return
        fx=int(self.image_fx.get().split()[-1])-1
        images=self.course.screenshot_images(fx)
        dialog=tk.Toplevel(self);dialog.title(f'Fx {fx+1} screenshots')
        dialog.transient(self)
        from PIL import Image,ImageTk
        import io
        listing=tk.Listbox(dialog,height=6,exportselection=False)
        listing.pack(fill='x',padx=12,pady=8)
        preview=tk.Label(dialog);preview.pack(padx=12,pady=8)
        def show(event=None):
            selected=listing.curselection()
            if not selected:preview.configure(image='');preview.image=None;return
            with Image.open(io.BytesIO(images[selected[0]])) as image:
                image.thumbnail((600,350));photo=ImageTk.PhotoImage(image)
            preview.configure(image=photo);preview.image=photo
        def populate():
            listing.delete(0,'end')
            for i in range(len(images)):listing.insert('end',f'Image {i+1}')
            if images:listing.selection_set(0)
            show()
        def remove():
            selected=listing.curselection()
            if selected:
                images.pop(selected[0]);self.course.screenshots[fx]=images or None
                populate();self.refresh()
        listing.bind('<<ListboxSelect>>',show)
        ttk.Button(dialog,text='Remove selected image',command=remove).pack(side='left',padx=12,pady=8)
        ttk.Button(dialog,text='Done',command=dialog.destroy).pack(side='right',padx=12,pady=8)
        populate()

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
        original_geometry=app.geometry()
        for width,height in ((1020,680),(1200,800)):
            app.geometry(f'{width}x{height}')
            app.update()
            for button in app.footer.winfo_children():
                if isinstance(button,ttk.Button):
                    x=button.winfo_rootx()-app.winfo_rootx()
                    y=button.winfo_rooty()-app.winfo_rooty()
                    assert button.winfo_ismapped()
                    assert 0<=x and x+button.winfo_width()<=app.winfo_width()
                    assert 0<=y and y+button.winfo_height()<=app.winfo_height()
        app.geometry(original_geometry)
        app.update()
        app.inputs['ctvhr_D90',0][0].set('100%')
        app.commit_inputs()
        app.prescription_var.set('8.0')
        app.commit_inputs()
        assert app.course.values[0]['ctvhr_D90']==8.0
        app.prescription_var.set('7.0')
        app.commit_inputs()
        assert app.course.values[0]['ctvhr_D90']==7.0
        assert len(app.notebook.tabs())==3
        app.preview.refresh_document()
        assert app.preview.document is not None and app.preview.photo is not None
        app.preview.move(1)
        assert app.preview.page_index==min(1,len(app.preview.document)-1)
        assert all(label.winfo_ismapped() for label in app.file_labels)
        for button,label in zip(app.buttons,app.file_labels):
            assert button.master==label.master
            assert button.winfo_rooty()<label.winfo_rooty()
        assert len(app.tables)==1
        for widgets in (app.buttons,app.file_labels,app.dvh_date_labels,app.dicom_buttons,app.source_dates,app.rp_date_labels,app.ct_date_labels):
            assert len({(w.winfo_rooty(),w.winfo_height()) for w in widgets})==1
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
        Path(report_path).write_text(json.dumps({'status':'passed','checks':['GUI','footer visible at multiple window sizes','precision preservation','fixed headers','ESTRO dose/EQD2 row order','fraction controls','bundled Excel export','PDF export','four-plan comparison','comparison PDF','cylinder mode']}))
    finally:
        app.destroy()


if __name__=='__main__':
    import sys
    if len(sys.argv)==3 and sys.argv[1]=='--smoke-test':
        packaged_smoke_test(sys.argv[2])
    else:
        App().mainloop()
