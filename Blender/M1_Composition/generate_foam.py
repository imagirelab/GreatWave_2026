"""13: 静止構図用の少数の爪・帯と前景波。粒子計算やアニメーションではない。"""
import bpy, bmesh, math, json
from mathutils import Vector
from pathlib import Path
OUT=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1

def mat(name,color):
    m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); return m
cream=mat('M1_FoamCream',(.95,.91,.77))
blue=mat('M1_Blue',(.065,.27,.39))
indigo=mat('M1_Indigo',(.018,.10,.20))
def convert(p): return (-p[0],-p[2],p[1])
def mesh_object(name,points,faces,material):
    mesh=bpy.data.meshes.new(name); mesh.from_pydata([convert(p) for p in points],[],faces); mesh.update()
    obj=bpy.data.objects.new(name,mesh); bpy.context.collection.objects.link(obj); mesh.materials.append(material)
    bm=bmesh.new(); bm.from_mesh(mesh); bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces)); bm.to_mesh(mesh); bm.free()
    for p in mesh.polygons:p.use_smooth=True
    return obj
def curve(a,b,c,d,t):return (1-t)**3*Vector(a)+3*(1-t)**2*t*Vector(b)+3*(1-t)*t*t*Vector(c)+t**3*Vector(d)
def tube(name,centers,radius,material):
    vertices=[]; faces=[]; sides=10
    for i,p in enumerate(centers):
        tangent=(centers[min(len(centers)-1,i+1)]-centers[max(0,i-1)]).normalized()
        normal=tangent.cross(Vector((0,0,1)))
        if normal.length<.1:normal=tangent.cross(Vector((0,1,0)))
        normal.normalize(); binormal=tangent.cross(normal).normalized()
        r=radius*(1-.86*i/(len(centers)-1))
        for j in range(sides):vertices.append(p+r*(math.cos(j*math.tau/sides)*normal+math.sin(j*math.tau/sides)*binormal))
    for i in range(len(centers)-1):
        for j in range(sides):faces.append((i*sides+j,i*sides+(j+1)%sides,(i+1)*sides+(j+1)%sides,(i+1)*sides+j))
    faces.extend([tuple(reversed(range(sides))),tuple((len(centers)-1)*sides+j for j in range(sides))])
    return mesh_object(name,vertices,faces,material)
def profile(u):
    if u<.62:return curve((-22,-.3),(-20,6),(-15,15.7),(-8,17.5),u/.62)
    return curve((-8,17.5),(-1,21),(5.8,17),(3.2,11.7),(u-.62)/.38)
def crest(u,v):
    p=profile(u); t=(profile(min(1,u+.001))-profile(max(0,u-.001))).normalized(); n=Vector((-t.y,t.x))
    width=6*(1-u)**1.15+1.1
    x=p.x+n.x*width+math.sin(math.pi*u/2)**2*(2.5*math.sin(math.pi*v)-2*v)
    y=(p.y+n.y*width)*(.86+.14*math.sin(math.pi*(.10+.85*v)))
    z=-7.5+20*v+1.5*math.sin(math.pi*u)*math.sin(math.pi*v)
    return Vector((x,y,z))

front=[crest(.50+.50*i/52,0)+Vector((0,.12,-.17)) for i in range(53)]
tube('M1_Foam_FrontRibbon',front,.57,cream)
groups=[]
for index,(u,v,scale) in enumerate([(.55,0,.9),(.64,0,1.1),(.73,0,.95),(.81,0,1.05),(.89,0,.9),(.97,0,.8),(.79,.4,.9),(.89,.7,.8),(.96,1,.75)]):
    origin=crest(u,v)+Vector((0,.15,-.24))
    for fork in range(3):
        a=origin+Vector((-.25*fork,.10*fork,.2*fork))
        b=origin+Vector((.6+fork*.35,.35-fork*.10,-.2)) * scale
        c=origin+Vector((1.9+fork*.5,-.4-fork*.35,-.7-fork*.1))*scale
        d=origin+Vector((1.5+fork*.5,-1.25-fork*.42,-.7-fork*.1))*scale
        tube(f'M1_Foam_Claw_{index:02d}_{fork}',[curve(a,b,c,d,t/20) for t in range(21)],(.32-fork*.045)*scale,cream)
    groups.append({'u':u,'v':v,'scale':scale})

# 原画の前景の尖りを確認する、厚みのある小さな静止の波。
section=[(-14,-.25),(-11,1.4),(-8,4.8),(-6.8,6.3),(-5,4.5),(-2,1.2),(2,-.25),(2,-2),(-14,-2)]
points=[]
for side in (0,1):
    for x,y in section:points.append((x+side*1.2,y*(1-.18*side),-13+side*6.5))
n=len(section); faces=[tuple(reversed(range(n))),tuple(n+i for i in range(n))]
for i in range(n):faces.append((i,(i+1)%n,n+(i+1)%n,n+i))
mesh_object('M1_ForegroundSwell_Static',points,faces,blue)
tube('M1_ForegroundFoam_Static',[Vector((x,y+.15,-13.12)) for x,y in section[:7]],.42,cream)

objects=[o for o in bpy.context.scene.objects if o.type=='MESH']
checks=[]
for obj in objects:
    bm=bmesh.new();bm.from_mesh(obj.data)
    checks.append({'name':obj.name,'non_manifold_edges':sum(not e.is_manifold for e in bm.edges),'volume_m3':abs(bm.calc_volume())})
    bm.free();obj.select_set(True)
passed=all(c['non_manifold_edges']==0 and c['volume_m3']>0 for c in checks)
if not passed:raise RuntimeError('13の閉形状検査に失敗')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'M1_Foam_Static.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'foam_static.fbx'),use_selection=True,global_scale=1,apply_unit_scale=True,
    apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',use_space_transform=True,bake_space_transform=False,
    bake_anim=False,object_types={'MESH'},add_leaf_bones=False,use_triangles=True,path_mode='STRIP')
report={'software':bpy.app.version_string,'static_not_simulated':True,'claw_groups':groups,'checks':checks,'passed':passed}
(OUT/'13_blender_foam.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('M1_STEP13_BLENDER_PASS',len(objects))
