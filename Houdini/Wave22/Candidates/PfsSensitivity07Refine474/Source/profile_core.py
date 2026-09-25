"""05の断面・交点を検査する純関数。HOM・MCP・元データ書換えなし。"""
import math


def face_index(boxes,cell=.04):
    grid={};wide=[]
    for row in boxes:
        number,xlo,xhi,zlo,zhi=row
        a,b=math.floor((xlo-1e-5)/cell),math.floor((xhi+1e-5)/cell)
        c,d=math.floor((zlo-1e-5)/cell),math.floor((zhi+1e-5)/cell)
        if (b-a+1)*(d-c+1)>256:wide.append(row);continue
        for ix in range(a,b+1):
            for iz in range(c,d+1):grid.setdefault((ix,iz),[]).append(row)
    return {'cell':cell,'grid':grid,'wide':wide}


def candidate_faces(index,x,z):
    rows=index['grid'].get((math.floor(x/index['cell']),math.floor(z/index['cell'])),[])+index['wide']
    return [number for number,a,b,c,d in rows if a-1e-5<=x<=b+1e-5 and c-1e-5<=z<=d+1e-5]


def original_gauge(sample,x,z,bounds):
    """04の121点/25二分の観測を変更せず再現する。"""
    lo,hi=bounds['min'],bounds['max'];eps=1e-5
    if not(lo[0]+eps<x<hi[0]-eps and lo[2]+eps<z<hi[2]-eps):return {'valid':False}
    bottom=max(-.6+.12,lo[1]+.01);top=min(.25,hi[1]-.01)
    ys=[bottom+(top-bottom)*j/120 for j in range(121)];vs=[float(sample((x,y,z)))for y in ys]
    crossings=[j for j in range(120)if vs[j]<0 and vs[j+1]>=0]
    valid=all(math.isfinite(v)for v in vs)and vs[0]<0 and vs[-1]>0 and len(crossings)==1
    result={'valid':valid,'crossing_count':len(crossings),'bracket_y_m':[bottom,top]}
    if valid:
        j=crossings[0];a=ys[j];b=ys[j+1]
        for _ in range(25):
            mid=(a+b)/2
            if sample((x,mid,z))<0:a=mid
            else:b=mid
        result['eta_m']=(a+b)/2
    return result


def registered_positions(gauges):
    return [{'gauge':g+1,'dx_m':ix*.02,'z_m':iz*.06,'x_m':x+ix*.02}
            for g,x in enumerate(gauges)for ix in range(-6,7)for iz in range(-2,3)]


def vertical_samples(top=.25):
    # 補間場の細かい照会であり、元.06m場の物理解像度を上げない。
    assert top>-.12
    return sorted(set([-.5999]+[-.57+i*.03 for i in range(15)]+[-.12+i*.0025 for i in range(math.floor((top+.12)/.0025)+1)]+[top]))


def enumerate_hits(query,top=.4,bottom=-.7,epsilon=1e-6,limit=64):
    """query(min,max)の最近hitを反復。primitive0も有効、Noneだけがmiss。"""
    hits=[];minimum=0.;maximum=top-bottom
    for _ in range(limit):
        hit=query(minimum,maximum)
        if hit is None:return {'hits':hits,'complete_within_step':True,'height_resolution_m':epsilon}
        y=hit['position_m'][1];distance=top-y
        if not all(math.isfinite(v)for v in hit['position_m']+hit['normal']):raise ValueError('交点が非有限')
        if not minimum-1e-10<=distance<=maximum+1e-10:raise ValueError('交点の前進範囲が不正')
        if hits and y>=hits[-1]['position_m'][1]-epsilon*.5:raise ValueError('交点反復が前進しない')
        hits.append(hit);minimum=distance+epsilon
        if minimum>maximum:return {'hits':hits,'complete_within_step':True,'height_resolution_m':epsilon}
    raise ValueError('交点数の事前上限を超えた')


def incidence_consistency(strict_hits,incidences,height_tolerance=1e-6,default_first_present=False):
    """native全体queryと面限定queryを照合し、不一致でも原観測を捨てない。"""
    comparisons=[]
    for hit in strict_hits:
        same=[(i,p)for i,p in enumerate(incidences)if p['primitive']==hit['primitive']and p.get('requested_primitive',p['primitive'])==hit['primitive']]
        errors=[(i,abs(p['position_m'][1]-hit['position_m'][1]))for i,p in same]
        comparisons.append({'primitive':hit['primitive'],'strict_height_m':hit['position_m'][1],
                            'same_primitive_incidence_indices':[i for i,_ in same],
                            'minimum_height_error_m':min((e for _,e in errors),default=None),
                            'matched_incidence_indices':[i for i,e in errors if e<=height_tolerance],
                            'matched':any(e<=height_tolerance for _,e in errors)})
    pattern_ids_valid=all(p.get('requested_primitive',p['primitive'])==p['primitive']for p in incidences)
    strict_default_coverage=not default_first_present or bool(strict_hits)
    reverse=[]
    for i,p in enumerate(incidences):
        error=min((abs(p['position_m'][1]-h['position_m'][1])for h in strict_hits),default=None)
        reverse.append({'incidence_index':i,'primitive':p['primitive'],'incidence_height_m':p['position_m'][1],
                        'minimum_strict_height_error_m':error,'matched':error is not None and error<=height_tolerance})
    return {'passed':pattern_ids_valid and strict_default_coverage and all(p['matched']for p in comparisons+reverse),
            'default_first_present':default_first_present,'strict_default_coverage':strict_default_coverage,
            'pattern_ids_valid':pattern_ids_valid,'height_tolerance_m':height_tolerance,'strict_hit_comparisons':comparisons,
            'incidence_height_comparisons':reverse,'unmatched_incidence_indices':[p['incidence_index']for p in reverse if not p['matched']],
            'meaning_ja':'主toleranceの全体queryと面限定queryの数値整合性。空のrayは形状存在を証明しない。不一致でも両側原交点を保持し次組を保留する。'}


def sign_profile(sample,x,z,bounds,ys=None,tolerance=1e-6):
    ys=vertical_samples(min(.25,bounds['max'][1]-.01))if ys is None else ys
    if not all(bounds['min'][i]<=v<=bounds['max'][i]for i,v in enumerate((x,ys[0],z))) or not bounds['min'][1]<=ys[-1]<=bounds['max'][1]:
        raise ValueError('縦線がfield外。ゼロ水位で補わない')
    values=[float(sample((x,y,z)))for y in ys]
    if not all(math.isfinite(v)for v in values):raise ValueError('符号場が非有限')
    nonzero=[i for i,v in enumerate(values)if v!=0];crossings=[]
    for a,b in zip(nonzero,nonzero[1:]):
        if values[a]*values[b]>=0:continue
        lo,hi=ys[a],ys[b];flo=values[a]
        if b==a+2:root=ys[a+1]
        else:
            while hi-lo>tolerance:
                mid=(lo+hi)*.5;f=float(sample((x,mid,z)))
                if not math.isfinite(f):raise ValueError('根探索中に非有限')
                if f==0:lo=hi=mid;break
                if (f<0)==(flo<0):lo=mid;flo=f
                else:hi=mid
            root=(lo+hi)*.5
        crossings.append({'kind':'wet_to_dry'if values[a]<0 else 'dry_to_wet','y_m':root,
                          'bracket_y_m':[ys[a],ys[b]],'zero_plateau':b>a+2})
    wet=[v for v in crossings if v['kind']=='wet_to_dry']
    zero_indices=[i for i,v in enumerate(values)if v==0]
    zero_plateau=any(b==a+1 for a,b in zip(zero_indices,zero_indices[1:]))
    tangent_zero_indices=[i for i in zero_indices if 0<i<len(values)-1 and values[i-1]*values[i+1]>0]
    single=len(wet)==1 and len(crossings)==1 and values[0]<0 and values[-1]>0 and not zero_plateau and not tangent_zero_indices
    return {'y_m':ys,'phi':values,'crossings':crossings,'wet_to_dry_count':len(wet),
            'zero_sample_indices':zero_indices,'zero_plateau_detected':zero_plateau,'tangent_zero_indices':tangent_zero_indices,
            'single_wet_to_dry_local':single,
            'first_phi_negative':values[0]<0,'height_m':wet[0]['y_m']if single else None,
            'meaning_ja':'有限区間の補間場の符号交差。全域連通・距離場精度・水量の証明ではない。'}


def polygon_metrics(points):
    if len(points)<3 or not all(math.isfinite(v)for p in points for v in p):raise ValueError('面頂点が不正')
    normal=[0.,0.,0.]
    for p,q in zip(points,points[1:]+points[:1]):
        normal[0]+=(p[1]-q[1])*(p[2]+q[2]);normal[1]+=(p[2]-q[2])*(p[0]+q[0]);normal[2]+=(p[0]-q[0])*(p[1]+q[1])
    length=math.sqrt(sum(v*v for v in normal))
    if length==0:return {'vertex_count':len(points),'degenerate':True,'max_plane_deviation_m':None}
    n=[v/length for v in normal]
    departure=max(abs(sum((p[j]-points[0][j])*n[j]for j in range(3)))for p in points)
    return {'vertex_count':len(points),'degenerate':False,'newell_normal':n,'max_plane_deviation_m':departure,
            'meaning_ja':'面を三角扇へ置換せず、頂点から局所平面逸脱を観測する。'}


def quad_diagonal_sensitivity(points,x,z):
    """二つの対角線は数値感度の観測だけ。元HOM交点を置換しない。"""
    if len(points)!=4:return {'applicable':False}
    def height(indices):
        a,b,c=[points[i]for i in indices];den=(b[2]-c[2])*(a[0]-c[0])+(c[0]-b[0])*(a[2]-c[2])
        if abs(den)<1e-18:return None
        u=((b[2]-c[2])*(x-c[0])+(c[0]-b[0])*(z-c[2]))/den
        v=((c[2]-a[2])*(x-c[0])+(a[0]-c[0])*(z-c[2]))/den;w=1-u-v
        if min(u,v,w)<-1e-12:return None
        return u*a[1]+v*b[1]+w*c[1]
    candidates=[[v for tri in pair if (v:=height(tri))is not None]for pair in [((0,1,2),(0,2,3)),((0,1,3),(1,2,3))]]
    determinate=all(v and max(v)-min(v)<=1e-9 for v in candidates)
    delta=abs(candidates[0][0]-candidates[1][0])if determinate else None
    return {'applicable':True,'candidate_heights_m':candidates,'two_diagonals_determinate':determinate,
            'projected_convexity_checked':False,'geometric_validity_certified':False,
            'absolute_difference_m':delta,'numerical_0p1mm_flag':delta is not None and delta>=.0001,
            'response_scale_1mm_flag':delta is not None and delta>=.001,
            'meaning_ja':'二分割の高さが各々定まるという観測だけ。投影凸性は未検査で、凹面・射影退化・幾何の妥当性は認定しない。感度フラグは物理合否や原因確定ではない。'}


def continuity_rows(profiles):
    lookup={(p['gauge'],round(p['dx_m'],6),round(p['z_m'],6)):p for p in profiles};out=[]
    for key,p in lookup.items():
        for axis,step in [('x',.02),('z',.06)]:
            other=(key[0],round(key[1]+(step if axis=='x'else 0),6),round(key[2]+(step if axis=='z'else 0),6))
            if other not in lookup:continue
            q=lookup[other];a=p['native_default_first_y_m'];b=q['native_default_first_y_m']
            out.append({'from_key':list(key),'to_key':list(other),'axis':axis,'distance_m':step,
                        'mesh_height_difference_m':None if a is None or b is None else b-a,
                        'mesh_slope':None if a is None or b is None else (b-a)/step,
                        'meaning_ja':'離散近傍差のみ。数学的連続性や主水面の一価性の証明ではない。'})
    return out
