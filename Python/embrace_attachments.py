"""User-selected report images, retained in memory until the course is cleared."""
import io
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def choose_image(parent, accept):
    path=filedialog.askopenfilename(parent=parent,title='Attach Oncentra screenshot',filetypes=[('Images','*.png *.jpg *.jpeg *.bmp'),('All files','*')])
    if not path: return
    try:
        from PIL import Image
        with Image.open(path) as image:
            data=io.BytesIO(); image.convert('RGB').save(data,format='PNG')
        preview(parent,data.getvalue(),accept)
    except Exception as error:
        messagebox.showerror('Screenshot',str(error),parent=parent)


def crop_image(data, box, display_size):
    """Map a preview selection back to original image pixels and encode JPEG."""
    from PIL import Image
    with Image.open(io.BytesIO(data)) as image:
        sx,sy=image.width/display_size[0],image.height/display_size[1]
        x0,y0,x1,y1=box
        bounds=(max(0,round(min(x0,x1)*sx)),max(0,round(min(y0,y1)*sy)),
                min(image.width,round(max(x0,x1)*sx)),min(image.height,round(max(y0,y1)*sy)))
        if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:
            raise ValueError('Drag a rectangle around the isodose image first.')
        result=io.BytesIO()
        image.crop(bounds).convert('RGB').save(result,format='JPEG',quality=95,subsampling=0)
        return result.getvalue()


def preview(parent,data,accept):
    from PIL import Image, ImageTk
    from pathlib import Path
    dialog=tk.Toplevel(parent); dialog.title('Snip isodose image')
    image=Image.open(io.BytesIO(data)); image.thumbnail((950,600))
    photo=ImageTk.PhotoImage(image)
    ttk.Label(dialog,text='Drag to select just the isodose image. Confirm the patient and fraction before saving.').pack(padx=10,pady=8)
    canvas=tk.Canvas(dialog,width=image.width,height=image.height,highlightthickness=0,cursor='crosshair')
    canvas.pack(padx=10,pady=5); canvas.create_image(0,0,image=photo,anchor='nw');canvas.image=photo
    selection=[0,0,image.width,image.height]
    rect=canvas.create_rectangle(*selection,outline='#e57000',width=2)
    def start(event):
        selection[:]=[event.x,event.y,event.x,event.y];canvas.coords(rect,*selection)
    def drag(event):
        selection[2:]=[max(0,min(event.x,image.width)),max(0,min(event.y,image.height))]
        canvas.coords(rect,*selection)
    canvas.bind('<ButtonPress-1>',start);canvas.bind('<B1-Motion>',drag)
    def use():
        try:
            cropped=crop_image(data,selection,image.size)
            path=filedialog.asksaveasfilename(parent=dialog,title='Save isodose screenshot',initialfile='Isodose.jpg',defaultextension='.jpg',filetypes=[('JPEG image','*.jpg')])
            if not path: return
            Path(path).write_bytes(cropped)
            accept(cropped);dialog.destroy()
        except Exception as error:
            messagebox.showerror('Screenshot',str(error),parent=dialog)
    ttk.Button(dialog,text='Save Isodose.jpg and add to PDF',command=use).pack(side='right',padx=10,pady=10)
    ttk.Button(dialog,text='Cancel',command=dialog.destroy).pack(side='right',pady=10)
    dialog.transient(parent);dialog.grab_set()


def capture_monitor(parent,accept):
    try:
        import mss
        with mss.mss() as capture:
            monitors=list(capture.monitors[1:])
        if not monitors: raise RuntimeError('No monitors detected. Attach a saved screenshot instead.')
    except Exception as error:
        messagebox.showerror('Screen capture',f'{error}\nYou can attach a saved screenshot instead.',parent=parent); return
    dialog=tk.Toplevel(parent); dialog.title('Snip Oncentra screen')
    dialog.transient(parent); dialog.grab_set()
    ttk.Label(dialog,text='Choose the monitor showing Oncentra. After a 3-second delay, drag a rectangle to snip the image.').pack(padx=12,pady=12)
    selected=tk.StringVar(value='1')
    for i,monitor in enumerate(monitors,1):
        ttk.Radiobutton(dialog,text=f'Monitor {i}: {monitor["width"]} x {monitor["height"]} at ({monitor["left"]}, {monitor["top"]})',variable=selected,value=str(i)).pack(anchor='w',padx=12)
    def start():
        monitor=monitors[int(selected.get())-1]; dialog.destroy(); parent.withdraw()
        def take():
            data=None
            try:
                from PIL import Image
                with mss.mss() as capture:
                    shot=capture.grab(monitor)
                image=Image.frombytes('RGB',shot.size,shot.rgb)
                buf=io.BytesIO(); image.save(buf,format='PNG'); data=buf.getvalue()
            except Exception as error:
                messagebox.showerror('Screen capture',f'{error}\nAttach a saved image if screen recording is unavailable.',parent=parent)
            finally: parent.deiconify()
            if data: preview(parent,data,accept)
        parent.after(3000,take)
    ttk.Button(dialog,text='Capture selected monitor',command=start).pack(padx=12,pady=12)
