"""所有キャッシュを再読込して形状・粒子連結・ID継承を実測するHoudini側処理。"""
import hashlib,json,math,time
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
ROOT=Path(STAGE)
index=json.loads((ROOT/'Evidence/17_cache_index.json').read_text(encoding='utf8'))
RADIUS=.16
MIN_PARTICLES=12
MIN_VOLUME=.005
def components(count,edges):
 parent=list(range(count))
 def root(i):
  while parent[i]!=i: parent[i]=parent[parent[i]];i=parent[i]
  return i
 for a,b in edges:
  a=root(a);b=root(b)
  if a!=b: parent[b]=a
 groups=defaultdict(list)
 for i in range(count): groups[root(i)].append(i)
 return list(groups.values())
def vectors(g,name): return np.array(g.pointFloatAttribValues(name),dtype=float).reshape((-1,3))
def bbox(points): return {'min':points.min(axis=0).tolist(),'max':points.max(axis=0).tolist()}
rows=[];previous=[];events=[]
for sample in index['samples']:
 k=sample['sample'];g=hou.Geometry();g.loadFromFile(str(ROOT/sample['mesh_file']))
 particles=hou.Geometry();particles.loadFromFile(str(ROOT/sample['particle_file']))
 P=vectors(g,'P');N=vectors(g,'N')
 # FLIP SOPはsurface/velocity等のVolume保持点も返す。未接続点だけが粒子。
 fluid_indices=[p.number() for p in particles.points() if not p.prims()]
 Q=vectors(particles,'P')[fluid_indices];V=vectors(particles,'v')[fluid_indices]
 assert np.isfinite(P).all() and np.isfinite(N).all() and np.isfinite(Q).all() and np.isfinite(V).all()
 nl=np.linalg.norm(N,axis=1);assert nl.min()>.99 and nl.max()<1.01
 raw_ids=particles.pointIntAttribValues('id');ids=[raw_ids[i] for i in fluid_indices];unique_ids=len(set(ids))==len(ids)
 faces=[[p.number() for p in prim.points()] for prim in g.prims()]
 edges=Counter(tuple(sorted((face[i],face[(i+1)%len(face)]))) for face in faces for i in range(len(face)))
 groups=components(len(P),edges.keys());assignment={p:c for c,group in enumerate(groups) for p in group}
 counts=Counter(assignment[face[0]] for face in faces)
 tri=np.array([(face[0],face[j],face[j+1]) for face in faces for j in range(1,len(face)-1)],dtype=int)
 tri_groups=np.array([assignment[int(i)] for i in tri[:,0]],dtype=int)
 a,b,c=P[tri[:,0]],P[tri[:,1]],P[tri[:,2]];cross=np.cross(b-a,c-a);length=np.linalg.norm(cross,axis=1)
 # Houdiniの頂点順は面法線と逆向きの外積。面の向きを同時に計測する。
 volumes=np.bincount(tri_groups,weights=-np.einsum('ij,ij->i',a,np.cross(b,c))/6,minlength=len(groups))
 areas=np.bincount(tri_groups,weights=length*.5,minlength=len(groups));triangles=len(tri)
 face_normals=np.array([tuple(prim.normal()) for prim,face in zip(g.prims(),faces) for j in range(1,len(face)-1)])
 valid=length>1e-12;dots=np.einsum('ij,ij->i',-cross[valid]/length[valid,None],face_normals[valid])
 mesh_components=[{'index':c,'points':len(group),'polygons':counts[c],'signed_volume_m3':float(volumes[c]),'area_m2':float(areas[c]),'significant':bool(abs(volumes[c])>=MIN_VOLUME),**bbox(P[group])} for c,group in enumerate(groups)]
 buckets=defaultdict(list);particle_edges=[]
 for i,q in enumerate(Q):
  cell=tuple(np.floor(q/RADIUS).astype(int))
  for dx in (-1,0,1):
   for dy in (-1,0,1):
    for dz in (-1,0,1):
     for j in buckets[(cell[0]+dx,cell[1]+dy,cell[2]+dz)]:
      if np.dot(q-Q[j],q-Q[j])<=RADIUS*RADIUS: particle_edges.append((i,j))
  buckets[cell].append(i)
 pc=components(len(Q),particle_edges)
 significant_pc=[group for group in pc if len(group)>=MIN_PARTICLES]
 current=[set(ids[i] for i in group) for group in significant_pc] if unique_ids else []
 if previous:
  intersections=[[len(a&b) for b in current] for a in previous]
  split=[i for i,row in enumerate(intersections) if sum(value>=8 for value in row)>=2]
  merge=[j for j in range(len(current)) if sum(row[j]>=8 for row in intersections)>=2]
  if split or merge: events.append({'sample_before':k-1,'sample_after':k,'time_before':(k-1)/index['fps'],'time_after':k/index['fps'],'particle_id_overlap_matrix':intersections,'split_predecessors':split,'merge_successors':merge,'previous_significant_components':len(previous),'current_significant_components':len(current)})
 previous=current
 row={'sample':k,'frame':sample['frame'],'time_seconds':sample['time_seconds'],'particle_count':len(Q),'particle_components_total':len(pc),'particle_components_significant':len(significant_pc),'particle_component_sizes':sorted([len(a) for a in pc],reverse=True),'particle_bounds':bbox(Q),'particle_max_speed_m_s':float(np.linalg.norm(V,axis=1).max()),'particle_ids_unique':unique_ids,'particle_id_unique_count':len(set(ids)),'mesh_points':len(P),'mesh_polygons':len(faces),'mesh_triangles':triangles,'mesh_topology_sha256':hashlib.sha256(json.dumps(faces,separators=(',',':')).encode()).hexdigest(),'mesh_components_total':len(groups),'mesh_components_significant':sum(c['significant'] for c in mesh_components),'mesh_components':mesh_components,'mesh_signed_volume_m3':float(volumes.sum()),'mesh_bounds':bbox(P),'boundary_edges':sum(v==1 for v in edges.values()),'nonmanifold_edges':sum(v>2 for v in edges.values()),'normal_length_min':float(nl.min()),'normal_length_max':float(nl.max()),'face_orientation_min':min(dots),'all_P_N_v_finite':True,'mesh_attributes':[a.name() for a in g.pointAttribs()],'particle_attributes':[a.name() for a in particles.pointAttribs()]}
 rows.append(row)
report={'clip_id':'GreatWave17_FLIP_02','classification':'実FLIPの小試料・海洋物理精度の検証ではない','sample_rate':index['fps'],'sample_count':len(rows),'time_seconds':[r['time_seconds'] for r in rows],'coordinate_system':'Houdini Y-up / m','particle_connectivity_radius_m':RADIUS,'significant_particle_count_min':MIN_PARTICLES,'significant_mesh_volume_min_m3':MIN_VOLUME,'lineage_shared_id_min':8,'particle_lineage_events':events,'samples':rows,'distinct_mesh_topology_count':len(set(r['mesh_topology_sha256'] for r in rows)),'all_finite_normals_and_geometry':all(r['all_P_N_v_finite'] for r in rows),'all_meshes_closed_manifold':all(r['boundary_edges']==0 and r['nonmanifold_edges']==0 for r in rows),'positive_component_volumes':all(c['signed_volume_m3']>0 for r in rows for c in r['mesh_components']),'physical_accuracy_verified':False,'hmd_verified':False}
(ROOT/'Evidence/17_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=lambda x:x.item())+'\n',encoding='utf8')
result={'sample_count':len(rows),'event_count':len(events),'events':events,'closed_manifold':report['all_meshes_closed_manifold'],'positive_component_volumes':report['positive_component_volumes'],'counts':[[r['sample'],r['particle_components_significant'],r['mesh_components_significant'],r['particle_count']] for r in rows]}
