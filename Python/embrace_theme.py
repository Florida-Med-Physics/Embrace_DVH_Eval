"""Shared light interface palette; blue is reserved for editable numeric fields."""
from tkinter import ttk

BG='#f4f5f7'
SURFACE='#ffffff'
ALT='#fafafa'
HEADER='#e6e9ed'
INK='#17212b'
MUTED='#505b67'
BLUE='#d9eff7'
INPUT_INK='#17212b'
INACTIVE='#eef0f2'
COLORS={'neutral':SURFACE,'pass':'#cde7d2','warn':'#ffedb5','fail':'#f3c5c1'}


def apply_theme(root):
    style=ttk.Style(root)
    style.theme_use('clam')
    style.configure('.',background=BG,foreground=INK,font=('Arial',10))
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',background=SURFACE,foreground=MUTED,padding=(14,5))
    style.map('TNotebook.Tab',background=[('selected',HEADER)],foreground=[('selected',INK)])
    style.configure('TButton',background=HEADER,foreground=INK,borderwidth=0,padding=(7,4))
    style.map('TButton',background=[('active','#d5d9dd')],foreground=[('disabled','#69737e')])
    style.configure('TCheckbutton',background=BG,foreground=MUTED)
    style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',INK)])
    style.configure('TCombobox',fieldbackground=SURFACE,background=HEADER,foreground=INPUT_INK,arrowcolor=INK,padding=3)
    style.map('TCombobox',fieldbackground=[('readonly',SURFACE)],foreground=[('readonly',INPUT_INK)],selectbackground=[('readonly',SURFACE)],selectforeground=[('readonly',INPUT_INK)])
    style.configure('Vertical.TScrollbar',background=HEADER,troughcolor=SURFACE,arrowcolor=MUTED,borderwidth=0)
    root.option_add('*TCombobox*Listbox.background',SURFACE)
    root.option_add('*TCombobox*Listbox.foreground',INK)
