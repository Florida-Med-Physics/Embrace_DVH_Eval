"""Continuous, automatically fitted preview of the actual exported course PDF."""
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk
import pypdfium2 as pdfium
from embrace_pdf import export_pdf
from embrace_theme import BG, INK, FONT, TITLE_FONT

FRAME='#202326'


class PDFPreviewTab(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=FRAME)
        self.app=app
        self.document=None
        self.page_index=0
        self.photo=None
        self.photos=[]
        self.page_offsets=[]
        self.resize_job=None
        tk.Label(self,text='PDF PREVIEW',bg=FRAME,fg='white',font=(TITLE_FONT,18,'bold'),anchor='w').pack(fill='x',padx=12,pady=(12,10))
        bar=tk.Frame(self,bg=BG,padx=8,pady=5);bar.pack(fill='x',padx=12,pady=(0,6))
        ttk.Button(bar,text='Export PDF',command=app.export_report).pack(side='right')
        self.status=tk.StringVar(value='Load a fraction TXT to preview its report.')
        tk.Label(self,textvariable=self.status,bg=FRAME,fg='white',font=(FONT,9),anchor='w',justify='left',wraplength=1000).pack(fill='x',padx=12,pady=(0,5))
        body=tk.Frame(self,bg=FRAME);body.pack(fill='both',expand=True,padx=12,pady=(0,10))
        self.canvas=tk.Canvas(body,bg=FRAME,highlightthickness=0,takefocus=True)
        vertical=ttk.Scrollbar(body,orient='vertical',command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vertical.set)
        vertical.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.canvas.bind('<Configure>',self.on_resize)
        self.canvas.bind('<MouseWheel>',lambda e:self.canvas.yview_scroll(-1 if e.delta>0 else 1,'units'))
        self.canvas.bind('<Button-4>',lambda e:self.canvas.yview_scroll(-1,'units'))
        self.canvas.bind('<Button-5>',lambda e:self.canvas.yview_scroll(1,'units'))
        self.canvas.bind('<Prior>',lambda e:self.canvas.yview_scroll(-1,'pages'))
        self.canvas.bind('<Next>',lambda e:self.canvas.yview_scroll(1,'pages'))
        self.canvas.bind('<Button-1>',lambda e:self.canvas.focus_set())

    def clear(self):
        self.canvas.delete('all');self.photo=None;self.photos=[];self.page_offsets=[]
        if self.document is not None:self.document.close();self.document=None
        self.page_index=0

    def refresh_document(self):
        if not self.app.commit_inputs():
            self.clear();self.status.set('Correct the invalid worksheet entry to preview the report.');return
        self.clear()
        course=self.app.course
        fraction=int(self.app.image_fx.get().split()[-1])-1
        worksheet=False
        if not any(v is not None for values in course.values[:course.count] for v in values.values()):
            self.status.set('Load a fraction TXT or enter worksheet doses to preview the PDF.');return
        try:
            with tempfile.TemporaryDirectory(prefix='embrace-preview-') as folder:
                path=Path(folder)/'preview.pdf'
                export_pdf(course,path,fraction=fraction,worksheet_only=worksheet)
                self.document=pdfium.PdfDocument(path.read_bytes())
            absent=[]
            if not worksheet:
                if not course.screenshots[fraction]:absent.append('screenshot')
                if not course.dvhs[fraction] or not course.dvhs[fraction].curves:absent.append('DVH curves')
            detail='Course worksheet' if worksheet else f'Fx {fraction+1} report and course worksheet'
            self.status.set(f'{detail} · {len(self.document)} page'+('s' if len(self.document)!=1 else '')+(' · Missing: '+', '.join(absent) if absent else ''))
            self.render_page()
        except Exception as error:
            self.clear();self.status.set(f'Preview unavailable: {error}')

    def move(self,delta):
        """Scroll to a page; retained for keyboard/programmatic navigation."""
        if self.document is None or not self.page_offsets:return
        self.page_index=max(0,min(len(self.document)-1,self.page_index+delta))
        height=float(self.canvas.cget('scrollregion').split()[-1])
        self.canvas.yview_moveto(self.page_offsets[self.page_index]/height)

    def on_resize(self,event):
        if self.resize_job is not None:self.after_cancel(self.resize_job)
        self.resize_job=self.after(180,self.resize_render)

    def resize_render(self):
        self.resize_job=None
        if self.document is not None:self.render_page(preserve_scroll=True)

    def render_page(self,preserve_scroll=False):
        if self.document is None:return
        position=self.canvas.yview()[0] if preserve_scroll else 0
        self.canvas.delete('all');self.photos=[];self.page_offsets=[]
        width=max(1,self.canvas.winfo_width())
        y=8
        for index in range(len(self.document)):
            page=self.document[index];bitmap=None
            try:
                scale=max(.1,min(3,(width-16)/page.get_width()))
                bitmap=page.render(scale=scale)
                photo=ImageTk.PhotoImage(bitmap.to_pil(),master=self)
            finally:
                if bitmap is not None:bitmap.close()
                page.close()
            self.photos.append(photo);self.page_offsets.append(y)
            self.canvas.create_image(max(0,(width-photo.width())//2),y,image=photo,anchor='nw')
            y+=photo.height()+16
        self.photo=self.photos[0]
        self.canvas.configure(scrollregion=(0,0,width,y))
        self.canvas.yview_moveto(position)

    def destroy(self):
        if self.resize_job is not None:self.after_cancel(self.resize_job);self.resize_job=None
        self.clear();super().destroy()
