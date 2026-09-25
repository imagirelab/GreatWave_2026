"""許可後の既存BGEO読戻し定義。hou.Geometryだけを使い、ノード/UI/solverへ触れない。"""
import hashlib
import ctypes
import json
import math
import struct
import time
from pathlib import Path


def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def read_pair(hou_api,mesh_path,solver_path,expected,plan):
    start=time.monotonic();budget=plan['budgets']['per_pair_cooperative_seconds'];memory_reads=[]
    def guard():
        if time.monotonic()-start>budget:raise TimeoutError('1組の協調読戻し予算を超えた')
        class MS(ctypes.Structure):
            _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(n,ctypes.c_ulonglong)for n in ('total','available','total_page','available_page','total_virtual','available_virtual','extended')]
        memory=MS();memory.length=ctypes.sizeof(memory);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
        memory_reads.append(int(memory.available))
        if memory.available<plan['budgets']['minimum_available_RAM_bytes']:raise MemoryError('空きRAM保護')
    guard()
    mesh_path,solver_path=Path(mesh_path),Path(solver_path)
    assert file_sha(mesh_path)==expected['mesh_sha256'] and file_sha(solver_path)==expected['solver_sha256']
    mesh=hou_api.Geometry();mesh.loadFromFile(str(mesh_path));guard()
    fluid=hou_api.Geometry();fluid.loadFromFile(str(solver_path));guard()
    found=[p for p in fluid.prims()if isinstance(p,hou_api.Volume)and p.attribValue('name')=='surface']
    assert len(found)==1;vol=found[0]
    bounds={'min':list(map(float,vol.boundingBox().minvec())),'max':list(map(float,vol.boundingBox().maxvec()))}
    transform=list(vol.transform().asTuple());assert all(math.isfinite(v)for v in transform)
    assert all(math.isfinite(v)for v in vol.allVoxels())
    p_values=mesh.pointFloatAttribValues('P');assert all(math.isfinite(v)for v in p_values)
    assert len(mesh.points())==expected['mesh_points'] and len(mesh.prims())==expected['mesh_faces']
    # 交点近傍の面だけを出すためのXZ候補。三角化・面の改変はしない。
    face_boxes=[]
    for prim in mesh.prims():
        corners=[list(map(float,v.point().position()))for v in prim.vertices()]
        assert len(corners)>=3
        face_boxes.append((prim.number(),min(p[0]for p in corners),max(p[0]for p in corners),min(p[2]for p in corners),max(p[2]for p in corners)))
    index=face_index(face_boxes);guard();profiles=[]
    for pos in registered_positions(plan['gauge_x_m']):
        guard();x,z=pos['x_m'],pos['z_m'];origin=hou_api.Vector3((x,.4,z));direction=hou_api.Vector3((0,-1,0))
        def native(minimum=None,maximum=None,pattern=None,tolerance=None):
            hitpos,normal,uvw=hou_api.Vector3(),hou_api.Vector3(),hou_api.Vector3()
            kwargs={}if minimum is None else {'min_hit':minimum,'max_hit':maximum,'tolerance':plan['intersection']['strict_tolerance_m']if tolerance is None else tolerance}
            if pattern is not None:kwargs['pattern']=str(pattern)
            primitive=mesh.intersect(origin,direction,hitpos,normal,uvw,**kwargs)
            if primitive<0:return None
            return {'primitive':primitive,'position_m':list(map(float,hitpos)),'normal':list(map(float,normal)),'uvw':list(map(float,uvw))}
        first=native()
        strict=enumerate_hits(native,epsilon=plan['intersection']['advance_epsilon_m'])
        sensitivity=enumerate_hits(lambda a,b:native(a,b,tolerance=plan['intersection']['sensitivity_tolerance_m']),epsilon=plan['intersection']['sensitivity_advance_m'])
        # 同じ高さの別面/共有辺の候補も削除せず、primitiveごとに保持する。
        incidences=[]
        for number in candidate_faces(index,x,z):
            hit=native(0.,1.1,number)
            if hit is not None:
                prim=mesh.prim(hit['primitive']);corners=[list(map(float,v.point().position()))for v in prim.vertices()]
                hit.update(requested_primitive=number,vertex_point_ids=[v.point().number()for v in prim.vertices()],vertices_m=corners,polygon=polygon_metrics(corners),
                           quad_diagonal_sensitivity=quad_diagonal_sensitivity(corners,x,z));incidences.append(hit)
        consistency=incidence_consistency(strict['hits'],incidences,plan['intersection']['strict_incidence_height_tolerance_m'],first is not None)
        field=sign_profile(vol.sample,x,z,bounds)
        row={**pos,'native_default_first':first,'native_default_first_y_m':None if first is None else first['position_m'][1],
             'strict_distinct_height_hits':strict,'sensitivity_distinct_height_hits':sensitivity,'unmerged_primitive_incidences':incidences,
             'strict_incidence_consistency':consistency,'field_profile':field}
        if pos['dx_m']==0 and z==0:
            original=expected['gauges'][pos['gauge']-1];replayed=original_gauge(vol.sample,x,z,bounds)
            row['center_original_gauge_replay']=replayed
            row['center_mesh_error_m']=None if first is None else first['position_m'][1]-original['mesh_eta_m']
            row['center_solver_error_m']=None if not replayed['valid']else replayed['eta_m']-original['eta_m']
            row['center_parity_passed']=(row['center_mesh_error_m']is not None and abs(row['center_mesh_error_m'])<=1e-6 and
                                         row['center_solver_error_m']is not None and abs(row['center_solver_error_m'])<=1e-8)
        profiles.append(row)
    guard()
    return {'sample':expected['sample'],'seconds':expected['sample']/60,'mesh_sha256':expected['mesh_sha256'],'solver_sha256':expected['solver_sha256'],
            'mesh_points':len(mesh.points()),'mesh_faces':len(mesh.prims()),'mesh_P_float64_sha256':hashlib.sha256(struct.pack('<%dd'%len(p_values),*p_values)).hexdigest(),
            'field':{'bounds':bounds,'transform':transform,'resolution':list(vol.resolution()),'voxel_m':list(vol.voxelSize()),'is_sdf_metadata':bool(vol.isSDF())},
            'profiles':profiles,'spatial_neighbour_differences':continuity_rows(profiles),
            'center_parity_passed':all(p['center_parity_passed']for p in profiles if 'center_parity_passed'in p),
            'strict_incidence_consistency_passed':all(p['strict_incidence_consistency']['passed']for p in profiles),
            'strict_incidence_mismatch_profile_indices':[i for i,p in enumerate(profiles)if not p['strict_incidence_consistency']['passed']],
            'read_seconds':time.monotonic()-start,'memory_guard':{'api':'Windows GlobalMemoryStatusEx','reads':len(memory_reads),
                'first_available_bytes':memory_reads[0],'last_available_bytes':memory_reads[-1],'min_available_bytes':min(memory_reads),
                'minimum_required_bytes':plan['budgets']['minimum_available_RAM_bytes']},
            'solver_executed':False,'nodes_created':False,
            'meaning_ja':'既存cacheの定義差診断。全体の連続性・減幅の単独原因・物理精度は認定しない。'}
