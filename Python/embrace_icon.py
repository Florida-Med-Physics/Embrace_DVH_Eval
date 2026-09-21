"""Set the window icon and explicitly set the native macOS Dock icon."""
from pathlib import Path
import sys
import tkinter as tk


def apply_icon(root):
    path = Path(__file__).resolve().parent / 'assets' / 'eqd2.png'
    if not path.is_file():
        return
    root._app_icon = tk.PhotoImage(file=str(path))
    root.iconphoto(True, root._app_icon)
    if sys.platform == 'darwin':
        import ctypes
        from ctypes import c_void_p, c_char_p
        objc = ctypes.CDLL('/usr/lib/libobjc.A.dylib')
        objc.objc_getClass.argtypes = [c_char_p]
        objc.objc_getClass.restype = c_void_p
        objc.sel_registerName.argtypes = [c_char_p]
        objc.sel_registerName.restype = c_void_p
        def send(receiver, selector, *args):
            signature = ctypes.CFUNCTYPE(c_void_p, c_void_p, c_void_p, *([c_void_p] * len(args)))
            call = signature(('objc_msgSend', objc))
            return call(receiver, objc.sel_registerName(selector), *args)
        filename = send(objc.objc_getClass(b'NSString'), b'stringWithUTF8String:', ctypes.cast(c_char_p(str(path).encode()), c_void_p))
        image = send(send(objc.objc_getClass(b'NSImage'), b'alloc'), b'initWithContentsOfFile:', filename)
        if image:
            application = send(objc.objc_getClass(b'NSApplication'), b'sharedApplication')
            send(application, b'setApplicationIconImage:', image)
            send(image, b'release')
