#!/usr/bin/env python3
"""Run with Python 3.9+ and Tkinter. No pip dependencies required."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from embrace_core import Course, STRUCTURES, eqd2, fmt, status
from embrace_export import export_workbook

BLUE = '#c7edf2'
COLORS = {'neutral': 'white', 'pass': '#73bf6e', 'warn': '#f5cc52', 'fail': '#e0574d'}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.course = Course()
        self.title('EMBRACE-2 EQD2 Excel Autogenerator')
        self.geometry('1200x980')
        self.minsize(1000, 720)
        self.configure(bg='#080809')
        self.cells, self.totals, self.inputs = {}, {}, {}
        self.status_text = tk.StringVar(value='Choose 3, 4, or 5 fractions, then load DVHs or edit physical values.')
        heading = tk.Frame(self, bg='#080809')
        heading.pack(fill='x', padx=12, pady=12)
        tk.Label(heading, text='EMBRACE-2  EQD2 Excel Autogenerator', bg='#080809', fg='white', font=('Arial', 22, 'bold')).pack(side='left')
        tk.Label(heading, text='UFHPTI', bg='#080809', fg='#fa4a00', font=('Arial', 12, 'bold')).pack(side='right')
        controls = ttk.Frame(self, padding=10)
        controls.pack(fill='x', padx=12)
        self.patient = ttk.Label(controls)
        self.patient.pack(side='left', fill='x', expand=True)
        self.count = tk.StringVar(value='4 Fx')
        count = ttk.Combobox(controls, textvariable=self.count, values=['3 Fx', '4 Fx', '5 Fx'], width=5, state='readonly')
        count.pack(side='left', padx=5)
        count.bind('<<ComboboxSelected>>', self.change_count)
        self.buttons = []
        for fx in range(5):
            button = ttk.Button(controls, text=f'Load F{fx+1}', command=lambda i=fx: self.load(i))
            button.pack(side='left', padx=3)
            self.buttons.append(button)
        self.plans = self.label('', size=10)
        self.files = self.label('', size=9)
        self.label('PRIOR RT / EBRT FRACTIONATION', bold=True)
        prior = tk.Frame(self, bg='white')
        prior.pack(fill='x', padx=12)
        for col, name in enumerate(('Parameter', 'Value', 'EQD2 [Gy] (α/β = 10)', 'EQD2 [Gy] (α/β = 3)')):
            self.cell(prior, 0, col, name, '#b3e0e8', bold=True)
            prior.columnconfigure(col, weight=1)
        self.prior_vars = [tk.StringVar(), tk.StringVar()]
        for row, text in enumerate(('Dose per fraction [Gy]', 'Fractions without central shield', 'Total dose [Gy]'), 1):
            self.cell(prior, row, 0, text, 'white')
            if row < 3:
                entry = tk.Entry(prior, textvariable=self.prior_vars[row-1], bg=BLUE, fg='black', justify='center', relief='flat')
                entry.grid(row=row, column=1, sticky='nsew', padx=1, pady=1)
                entry.bind('<Return>', self.edit_prior)
                entry.bind('<FocusOut>', self.edit_prior)
        self.prior_display = {}
        for row, col in ((2,2), (2,3), (3,1), (3,2), (3,3)):
            self.prior_display[row,col] = self.cell(prior, row, col, '', 'white')
        body = tk.PanedWindow(self, orient='vertical', bg='#080809', sashwidth=8)
        body.pack(fill='both', expand=True, padx=12, pady=6)
        for title, definitions, target in [('TARGETS', STRUCTURES[:3], True), ('ORGANS AT RISK', STRUCTURES[3:], False)]:
            panel = tk.Frame(body, bg='#080809')
            body.add(panel, minsize=160, stretch='always')
            tk.Label(panel, text=title, bg='#080809', fg='white', font=('Arial', 14, 'bold'), anchor='w').pack(fill='x', pady=5)
            outer = tk.Frame(panel)
            outer.pack(fill='both', expand=True)
            canvas = tk.Canvas(outer, bg='white', highlightthickness=0)
            scroll = ttk.Scrollbar(outer, orient='vertical', command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y')
            canvas.pack(side='left', fill='both', expand=True)
            grid = tk.Frame(canvas, bg='#d3d8dc')
            win = canvas.create_window((0,0), window=grid, anchor='nw')
            grid.bind('<Configure>', lambda e,c=canvas: c.configure(scrollregion=c.bbox('all')))
            canvas.bind('<Configure>', lambda e,c=canvas,w=win: c.itemconfigure(w, width=e.width))
            headers = ['Structure / Dose Parameter', 'F1', 'F2', 'F3', 'F4', 'F5', 'TOTAL BT + EBT', 'Planning Goal' if target else 'Soft Constraints', 'Tolerance' if target else 'Hard Constraints']
            for col, header in enumerate(headers):
                self.cell(grid, 0, col, header, '#b3e0e8', bold=True)
                grid.columnconfigure(col, weight=3 if col == 0 else 1, minsize=180 if col == 0 else 66)
            row = 1
            for title, key, metrics in definitions:
                section = tk.Label(grid, text=title, bg='#b3e0e8', fg='black', anchor='w', font=('Arial', 11, 'bold'), padx=8)
                section.grid(row=row, column=0, columnspan=9, sticky='nsew', pady=(8,1))
                row += 1
                for metric in metrics:
                    full_key = f'{key}_{metric.key}'
                    self.cell(grid, row, 0, '    '+metric.label, BLUE)
                    for fx in range(5):
                        var = tk.StringVar()
                        entry = tk.Entry(grid, textvariable=var, bg=BLUE, fg='black', disabledbackground='#e0e0e0', disabledforeground='#737373', justify='center', relief='flat', width=7)
                        entry.grid(row=row, column=fx+1, sticky='nsew', padx=1, pady=1)
                        entry.bind('<Return>', lambda e,i=fx,k=full_key: self.edit(i,k))
                        entry.bind('<FocusOut>', lambda e,i=fx,k=full_key: self.edit(i,k))
                        self.inputs[full_key,fx] = var,entry
                    row += 1
                    if metric.ab:
                        self.cell(grid, row, 0, '    '+metric.label.replace('[Gy]', f'EQD2{metric.ab} [Gy]'), 'white')
                        for fx in range(5):
                            self.cells[full_key,fx] = self.cell(grid,row,fx+1,'','white')
                        self.totals[full_key] = self.cell(grid,row,6,'','white',bold=True)
                        self.cell(grid,row,7,metric.goal,'white')
                        self.cell(grid,row,8,metric.hard,'white')
                        row += 1
            def wheel(event, c=canvas):
                c.yview_scroll(-1 if event.delta > 0 or event.num == 4 else 1, 'units')
                return 'break'
            def bind_wheel(widget):
                widget.bind('<MouseWheel>', wheel)
                widget.bind('<Button-4>', wheel)
                widget.bind('<Button-5>', wheel)
                for child in widget.winfo_children():
                    bind_wheel(child)
            bind_wheel(outer)
        footer = ttk.Frame(self, padding=10)
        footer.pack(fill='x', padx=12, pady=(0,8))
        ttk.Label(footer, textvariable=self.status_text, wraplength=700).pack(side='left', fill='x', expand=True)
        ttk.Button(footer, text='Clear All', command=self.clear).pack(side='left', padx=8)
        ttk.Button(footer, text='EXPORT CURRENT DISPLAY TO EXCEL', command=self.export).pack(side='right')
        self.refresh()

    def label(self, text, size=12, bold=False):
        label = tk.Label(self, text=text, bg='#080809', fg='white', anchor='w', justify='left', wraplength=1160, font=('Arial',size,'bold' if bold else 'normal'))
        label.pack(fill='x', padx=12, pady=4)
        return label

    @staticmethod
    def cell(parent, row, col, text, bg, bold=False):
        label = tk.Label(parent, text=text, bg=bg, fg='black', anchor='w' if col == 0 else 'center', font=('Arial',10,'bold' if bold else 'normal'), padx=5, pady=3)
        label.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)
        return label

    def refresh(self):
        c = self.course
        self.patient.configure(text=f'Patient: {c.patient or "—"}   |   Patient ID: {c.patient_id or "—"}')
        self.plans.configure(text='    |    '.join(f'Fx{i+1} Plan: {c.plans[i] or "—"}' for i in range(c.count)))
        self.files.configure(text='    |    '.join(f'Fx{i+1}: {c.files[i] or "—"}' for i in range(c.count)))
        self.prior_vars[0].set(fmt(c.dose_per_fx))
        self.prior_vars[1].set(fmt(c.prior_fractions))
        for (row,col), label in self.prior_display.items():
            label.configure(text=fmt(c.dose_per_fx*c.prior_fractions if col == 1 else c.baseline(10 if col == 2 else 3)))
        for fx, button in enumerate(self.buttons):
            button.configure(state='normal' if fx < c.count else 'disabled')
        for (key,fx), (var,entry) in self.inputs.items():
            var.set(fmt(c.values[fx].get(key)))
            entry.configure(state='normal' if fx < c.count else 'disabled')
        for _, key, metrics in STRUCTURES:
            for metric in metrics:
                if not metric.ab:
                    continue
                k = f'{key}_{metric.key}'
                for fx in range(5):
                    value = c.values[fx].get(k)
                    self.cells[k,fx].configure(text=fmt(eqd2(value,metric.ab)) if value is not None and fx < c.count else '', bg='white' if fx < c.count else '#e0e0e0')
                total = c.total(k)
                self.totals[k].configure(text=fmt(total), bg=COLORS[status(total,metric)])

    def edit(self, fx, key):
        if fx >= self.course.count:
            return
        try:
            self.course.edit(fx,key,self.inputs[key,fx][0].get())
        except ValueError as error:
            self.status_text.set(str(error))
        self.refresh()

    def edit_prior(self, event=None):
        try:
            self.course.set_prior(*(v.get() for v in self.prior_vars))
        except ValueError as error:
            self.status_text.set(str(error))
        self.refresh()

    def commit_inputs(self):
        """Commit pending text even when a toolbar click does not move focus."""
        for (key, fx), (var, _) in self.inputs.items():
            if fx < self.course.count:
                try:
                    self.course.edit(fx, key, var.get())
                except ValueError as error:
                    self.status_text.set(str(error))
        try:
            self.course.set_prior(*(v.get() for v in self.prior_vars))
        except ValueError as error:
            self.status_text.set(str(error))
        self.refresh()

    def change_count(self, event=None):
        self.commit_inputs()
        self.course.set_count(int(self.count.get()[0]))
        self.refresh()
        self.status_text.set(f'{self.course.count}-fraction brachytherapy course selected.')

    def load(self, fx):
        self.commit_inputs()
        path = filedialog.askopenfilename(title=f'Load Fx{fx+1} DVH TXT', filetypes=[('DVH text files','*.txt'),('All files','*')])
        if not path:
            return
        try:
            parsed = self.course.load(fx,path)
            self.refresh()
            message = f'Loaded Fx{fx+1}; carried forward to later fractions that have not been explicitly loaded.'
            if parsed.ignored:
                message += ' Ignored: '+', '.join(parsed.ignored)
            self.status_text.set(message)
        except (ValueError, OSError) as error:
            messagebox.showerror('DVH Import Error', str(error), parent=self)

    def clear(self):
        if messagebox.askyesno('Clear Dashboard', 'Clear all brachytherapy values and reset prior RT?', default='no', parent=self):
            self.course = Course(count=self.course.count)
            self.refresh()
            self.status_text.set('Dashboard cleared.')

    def export(self):
        self.commit_inputs()
        here = Path(__file__).resolve().parent
        name = 'EQD2_with_tolerances_090126.xlsx'
        template = next((p for p in (here/name, here.parent/'Matlab'/name, Path.cwd()/name) if p.exists()), None)
        if template is None:
            template = filedialog.askopenfilename(title='Choose EQD2 template', filetypes=[('Excel workbook','*.xlsx')])
        if not template:
            return
        output = filedialog.asksaveasfilename(title='Export EMBRACE-2 EQD2 Workbook', initialfile='EMBRACE2_Current_Display.xlsx', defaultextension='.xlsx', filetypes=[('Excel workbook','*.xlsx')])
        if not output:
            return
        try:
            sheets = export_workbook(self.course,template,output)
            self.status_text.set(f'Exported {Path(output).name}. Open in Excel to recalculate formulas.')
            messagebox.showinfo('Export Complete', 'Updated sheets:\n'+'\n'.join(sheets)+'\n\nSaved to:\n'+output, parent=self)
        except Exception as error:
            messagebox.showerror('Excel Export Error', str(error), parent=self)


def packaged_smoke_test(report_path):
    """Exercise the frozen GUI and resource lookup without any patient data."""
    import json
    import tempfile
    app = App()
    try:
        app.update()
        app.inputs['ctvhr_D90', 0][0].set('7')
        app.count.set('5 Fx')
        app.change_count()
        assert app.totals['ctvhr_D90'].cget('text') == '54.17'
        assert str(app.buttons[4].cget('state')) == 'normal'
        app.count.set('3 Fx')
        app.change_count()
        assert str(app.buttons[4].cget('state')) == 'disabled'
        template = Path(__file__).resolve().parent/'EQD2_with_tolerances_090126.xlsx'
        assert template.is_file(), 'Bundled template is missing'
        with tempfile.TemporaryDirectory() as folder:
            sheets = export_workbook(app.course, template, Path(folder)/'smoke.xlsx')
            assert len(sheets) == 2
        Path(report_path).write_text(json.dumps({'status': 'passed', 'checks': ['GUI', 'EQD2 total', 'fraction controls', 'bundled template export']}))
    finally:
        app.destroy()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        packaged_smoke_test(sys.argv[2])
    else:
        App().mainloop()
