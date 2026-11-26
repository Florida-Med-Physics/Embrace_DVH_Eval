"""Shared light interface palette; blue is reserved for editable numeric fields."""
import os
import platform
from pathlib import Path
from tkinter import ttk, font as tkfont


def system_font():
    """The operating system's own UI typeface; Windows 11 ships Segoe UI Variable."""
    if platform.system()=='Windows':
        fonts=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Fonts'
        return 'Segoe UI Variable Text' if (fonts/'SegUIVar.ttf').exists() else 'Segoe UI'
    return 'Helvetica Neue' if platform.system()=='Darwin' else 'DejaVu Sans'


FONT=system_font()
# Segoe UI Variable has a Display cut tuned for large titles.
TITLE_FONT=FONT.replace(' Text',' Display')

BG='#f4f5f7'
SURFACE='#ffffff'
ALT='#fafafa'
HEADER='#e6e9ed'
INK='#17212b'
MUTED='#505b67'
BLUE='#d9eff7'
INPUT_INK='#17212b'
INACTIVE='#eef0f2'
COLORS={'neutral':SURFACE,'pass':'#73bf6e','warn':'#f5cc52','fail':'#e0574d'}


def apply_theme(root):
    style=ttk.Style(root)
    style.theme_use('clam')
    for name in ('TkDefaultFont','TkTextFont','TkMenuFont','TkHeadingFont'):
        tkfont.nametofont(name,root=root).configure(family=FONT,size=10)
    style.configure('.',background=BG,foreground=INK,font=(FONT,10))
    style.configure('TNotebook',background=BG,borderwidth=0)
    style.configure('TNotebook.Tab',background=SURFACE,foreground=MUTED,padding=(14,5))
    style.map('TNotebook.Tab',
              background=[('selected','#202326'),('active',HEADER)],
              foreground=[('selected','#ffffff'),('active',INK)],
              font=[('selected',(FONT,10,'bold'))],
              lightcolor=[('selected','#202326')],
              darkcolor=[('selected','#202326')])
    style.configure('TButton',background=HEADER,foreground=INK,borderwidth=0,padding=(7,4))
    style.map('TButton',background=[('active','#d5d9dd')],foreground=[('disabled','#69737e')])
    style.configure('Load.TButton',background='#f7f8fa',borderwidth=2,relief='raised',bordercolor='#8996a3',lightcolor='#ffffff',darkcolor='#a5afb9',padding=(8,4),font=(FONT,9,'bold'))
    style.map('Load.TButton',background=[('disabled',HEADER),('pressed','#cbd3da'),('active','#e4e9ee')],relief=[('pressed','sunken')],bordercolor=[('disabled','#cbd0d5'),('active','#627487')],lightcolor=[('disabled',HEADER),('pressed','#a5afb9')],darkcolor=[('disabled',HEADER),('pressed','#ffffff')])
    style.configure('Compact.Load.TButton',padding=(5,1))
    style.configure('Card.Load.TButton',padding=(3,1),font=(FONT,9,'bold'))
    style.configure('File.Load.TButton',padding=(3,1),font=(FONT,8,'bold'))
    style.configure('TCheckbutton',background=BG,foreground=MUTED)
    style.map('TCheckbutton',background=[('active',BG)],foreground=[('active',INK)])
    style.configure('TCombobox',fieldbackground=SURFACE,background=HEADER,foreground=INPUT_INK,arrowcolor=INK,padding=3)
    style.map('TCombobox',fieldbackground=[('readonly',SURFACE)],foreground=[('readonly',INPUT_INK)],selectbackground=[('readonly',SURFACE)],selectforeground=[('readonly',INPUT_INK)])
    style.configure('Editable.TCombobox',fieldbackground=BLUE,background=BLUE)
    style.map('Editable.TCombobox',fieldbackground=[('disabled',INACTIVE),('readonly',BLUE)],background=[('disabled',INACTIVE),('readonly',BLUE)],selectbackground=[('readonly',BLUE)],selectforeground=[('readonly',INPUT_INK)])
    style.configure('Vertical.TScrollbar',background=HEADER,troughcolor=SURFACE,arrowcolor=MUTED,borderwidth=0)
    root.option_add('*TCombobox*Listbox.background',SURFACE)
    root.option_add('*TCombobox*Listbox.foreground',INK)
