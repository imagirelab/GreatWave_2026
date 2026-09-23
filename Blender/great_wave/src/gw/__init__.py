"""gw -- foundation utilities of the great_wave Blender project (numpy + bpy only).

Modules
-------
bootstrap : sys.path / '--' argument helpers, prefixed logging for headless runs
paths     : every project path, params.json / thresholds.json access, write guard
frame     : painting px <-> pct <-> H units <-> metres, CAM_print numbers (spec section 4)
imgio     : load images through bpy, exact pure-python PNG writer / reader
draw      : numpy raster drawing (lines, markers, overlays, resize, contact sheets, 5x7 text)
plot      : numpy line plots

Submodules are imported lazily by the user (`from gw import frame, draw`); importing
`gw` itself pulls in nothing heavy and never needs bpy.
"""

__version__ = "0.1.0"
__all__ = ["bootstrap", "paths", "frame", "imgio", "draw", "plot"]
