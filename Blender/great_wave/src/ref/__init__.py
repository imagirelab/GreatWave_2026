"""ref -- read-out of the Houdini motion reference (1.abc) and other dynamics references.

Owned by the reference-motion agent.  The foundation only creates the package.
The Houdini cache is a MOTION reference only (spec sections 1 and 6.1); it is never a
geometry source for the delivered mesh.  Inputs are read-only.
"""
