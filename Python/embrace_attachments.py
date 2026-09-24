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


def preview(parent,data,accept):
    from PIL import Image, ImageTk
    dialog=tk.Toplevel(parent); dialog.title('Review Oncentra screenshot')
    image=Image.open(io.BytesIO(data)); image.thumbnail((950,650))
    photo=ImageTk.PhotoImage(image)
    label=tk.Label(dialog,image=photo); label.image=photo; label.pack(padx=10,pady=10)
    ttk.Label(dialog,text='Confirm this image belongs to the current patient and selected fraction.').pack(padx=10,pady=4)
    def use(): accept(data); dialog.destroy()
    ttk.Button(dialog,text='Use screenshot',command=use).pack(side='right',padx=10,pady=10)
    ttk.Button(dialog,text='Cancel',command=dialog.destroy).pack(side='right',pady=10)
    dialog.transient(parent)
    dialog.grab_set()


def capture_monitor(parent,accept):
    try:
        import mss
        with mss.mss() as capture:
            monitors=list(capture.monitors[1:])
        if not monitors: raise RuntimeError('No monitors detected. Attach a saved screenshot instead.')
    except Exception as error:
        messagebox.showerror('Screen capture',f'{error}\nYou can attach a saved screenshot instead.',parent=parent); return
    dialog=tk.Toplevel(parent); dialog.title('Capture Oncentra monitor')
    dialog.transient(parent); dialog.grab_set()
    ttk.Label(dialog,text='Choose the monitor showing Oncentra. Capture starts after a 3-second delay.').pack(padx=12,pady=12)
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
