"""15修正：右の上り斜面と左船の支持波を新規閉メッシュで作る。流体ではない。"""
import bpy,bmesh,math,json
from pathlib import Path
OUT=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene.unit_settings.scale_length=1

def material(name,color):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);return m
mats=[material('M1_Blue',(.065,.27,.39)),material('M1_Indigo',(.018,.10,.20)),material('M1_LightBlue',(.23,.46,.53)),material('M1_FoamCream',(.95,.91,.77))]

def height(profile,x):
 for i in range(len(profile)-1):
  a,b=profile[i:i+2]
  if x<=b[0]:
   t=(x-a[0])/(b[0]-a[0]);return a[1]+(b[1]-a[1])*t
 return profile[-1][1]

def swell(name,profile,zmin,zmax,depth_factor):
 nx,nz=96,20;verts=[];faces=[];indices=[]
 for j in range(nz+1):
  v=j/nz;z=zmin+(zmax-zmin)*v
  for i in range(nx+1):
   u=i/nx;x=profile[0][0]+(profile[-1][0]-profile[0][0])*u
   y=height(profile,x)*depth_factor(v)
   verts.append((-x,-z,y))
 n=len(verts)
 for x,z,y in list(verts):verts.append((x,z,-1.1))
 for j in range(nz):
  for i in range(nx):
   a=j*(nx+1)+i;b=a+1;c=a+nx+1;d=c+1
   faces.extend([(a,b,d,c),(n+a,n+c,n+d,n+b)])
   indices.extend([0,1])
 perimeter=list(range(nx+1))+[j*(nx+1)+nx for j in range(1,nz+1)]+[nz*(nx+1)+i for i in range(nx-1,-1,-1)]+[j*(nx+1) for j in range(nz-1,0,-1)]
 for k,a in enumerate(perimeter):
  b=perimeter[(k+1)%len(perimeter)];faces.append((a,n+a,n+b,b));indices.append(1)
 mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
 obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
 for m in mats:mesh.materials.append(m)
 for p,idx in zip(mesh.polygons,indices):p.material_index=idx;p.use_smooth=True
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bad=sum(not e.is_manifold for e in bm.edges);volume=abs(bm.calc_volume());bm.to_mesh(mesh);bm.free()
 assert bad==0 and volume>0
 return {'name':name,'non_manifold_edges':bad,'volume_m3':volume,'vertices':len(verts),'profile_xy_m':profile,'depth_minmax_m':[zmin,zmax]}
checks=[]
checks.append(swell('M1_Revision_RightSlope',[(0,-.25),(6,.05),(11,1.3),(16,3.6),(21,7.3),(26,12.4),(32,17.4)],-24,22,lambda v:.48+.52*math.sin(math.pi*v*.75)))
checks.append(swell('M1_Revision_LeftSupport',[(-25,-.25),(-22,4.5),(-18,4.8),(-14,2.9),(-9,0),(-5,-.25)],-15,-4,lambda v:.92+.08*math.sin(math.pi*v)))
for o in bpy.context.scene.objects:o.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'M1_Revision01_Slopes.blend'))
bpy.ops.export_scene.fbx(filepath=str(OUT/'revision_slopes.fbx'),use_selection=True,global_scale=1,apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',axis_forward='-Z',axis_up='Y',use_space_transform=True,bake_space_transform=False,bake_anim=False,object_types={'MESH'},add_leaf_bones=False,use_triangles=True,path_mode='STRIP')
report={'software':bpy.app.version_string,'static_not_fluid':True,'checks':checks,'passed':all(c['non_manifold_edges']==0 and c['volume_m3']>0 for c in checks)}
(OUT/'15_revision_blender.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('M1_REVISION01_BLENDER_PASS')
