"""Ask for explicit cc volumes when a relative-volume TXT omits them."""
from tkinter import simpledialog
from embrace_core import MissingVolumeError


def import_with_volumes(parent, load):
    volumes = {}
    while True:
        try:
            return load(volumes)
        except MissingVolumeError as error:
            for name in error.names:
                volume = simpledialog.askfloat('Structure volume required',
                    f'{name}\n\nThis DVH uses volume percentages. Enter the structure volume in cc:',
                    parent=parent, minvalue=0.000001)
                if volume is None:
                    return None
                volumes[name] = volume
