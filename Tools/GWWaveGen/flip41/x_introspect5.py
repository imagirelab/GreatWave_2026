import hou
dop = hou.node("/obj").createNode("dopnet", "X")
fs = dop.createNode("flipsolver::2.0", "fs")
for nm in ("enable_surface_weights", "compute_surface_weights", "limit_surface_weights", "create_surface_weights", "gasparticletosdf", "reinitalize_surface", "enable_surface_reinit", "enable_vel_advect_narrowband", "overwrite_in_narrow_band", "overwrite_out_of_surface", "enable_NB_velocity_blend"):
    n = fs.node(nm)
    if n is None:
        print("missing", nm); continue
    out = []
    for p in n.parms():
        try:
            e = p.expression()
        except Exception:
            e = None
        if e or not p.isAtDefault():
            try:
                out.append((p.name(), e if e else p.eval()))
            except Exception:
                pass
    print("==", nm, n.type().name(), out[:30])
names = [p.name() for p in fs.parms()]
print([ (n, fs.parm(n).eval()) for n in names if any(s in n.lower() for s in ("weight", "fraction", "ghost", "radius", "reinit", "narrow", "band", "surface"))])
