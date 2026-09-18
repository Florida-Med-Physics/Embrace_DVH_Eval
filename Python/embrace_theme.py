"""Shared dark interface palette; cyan is reserved for editable fields."""
from tkinter import ttk

BG='#101215'
SURFACE='#1b1e23'
ALT='#20242a'
HEADER='#2b3037'
INK='#edf1f5'
MUTED='#aeb8c4'
BLUE='#a8e4f5'
INPUT_INK='#13232d'
INACTIVE='#262b31'
COLORS={'neutral':SURFACE,'pass':'#cde7d2','warn':'#ffedb5','fail':'#f3c5c1'}


def apply_theme(root):
    style=ttk.Style(root)
    style.theme_use('clam')
    style.configure('.',background=BG,foreground=INK,font=('Arial',10))
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',background=SURFACE,foreground=MUTED,padding=(14,5))
    style.map('TNotebook.Tab',background=[('selected',HEADER)],foreground=[('selected',INK)])
    style.configure('TButton',background=HEADER,foreground=INK,borderwidth=0,padding=(7,4))
    style.map('TButton',background=[('active','#3b424c')],foreground=[('disabled','#69737e')])
    style.configure('TCheckbutton',background=BG,foreground=MUTED)
    style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',INK)])
    style.configure('TCombobox',fieldbackground=BLUE,background=HEADER,foreground=INPUT_INK,arrowcolor=INK,padding=3)
    style.map('TCombobox',fieldbackground=[('readonly',BLUE)],foreground=[('readonly',INPUT_INK)],selectbackground=[('readonly',BLUE)],selectforeground=[('readonly',INPUT_INK)])
    style.configure('Vertical.TScrollbar',background=HEADER,troughcolor=SURFACE,arrowcolor=MUTED,borderwidth=0)
    root.option_add('*TCombobox*Listbox.background',SURFACE)
    root.option_add('*TCombobox*Listbox.foreground',INK)
