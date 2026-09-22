"""Bounded attribute audit for rigid PS2 scenario records the pinned tool omits.

32-byte records retain both normals and RGBA. Existing VIF qword fields still
price 24-byte records; the node's first-segment byte extent prices 32. This
reader qualifies inventory only, never repacking, PS2 execution or native upload.
"""
import math,struct

def audit_rigid32(data):
 def span(at,n):
  if at<0 or n<0 or at>len(data)-n:raise ValueError('rigid32 record exceeds BIN')
  return data[at:at+n]
 if span(0,2)!=b'\x30\0':raise ValueError('not PS2 BIN')
 count,off=struct.unpack('<HI',span(10,6));span(off,count*16)
 materials=[];records=0
 for m in range(count):
  desc=span(off+16*m,16);node=struct.unpack_from('<I',desc,12)[0]
  total,extra,bones=struct.unpack('<HBB',span(node,4));cur=node+((4+bones+15)//16)*16
  if bones!=1:raise ValueError('not single rigid-part variant')
  segments=[]
  for sn in range(extra+1):
   h1,h2,h3=[span(cur+i*16,16) for i in range(3)];n=h2[0];scale=struct.unpack_from('<f',h2,12)[0]
   if not n or not math.isfinite(scale) or scale<=0 or h1[12:]!=bytes.fromhex('2080016c') or h3[12:14]!=bytes.fromhex('2180'):raise ValueError('unrecognized rigid32 segment control')
   size=n*32
   if sn==0 and total!=cur-node+48+size:raise ValueError('node first-segment extent disagrees with rigid32')
   span(cur+48,size);vertices=[];normals=[]
   for i in range(n):
    v=struct.unpack_from('<3hH3hH2h2H3hH',data,cur+48+i*32)
    if any(abs(x)>128 for x in v[4:7]):raise ValueError('rigid32 normal outside PS2 range')
    vertices.append([*v[:3],*v[8:10],*v[12:15],v[15],v[7],v[11]])
    normals.append(v[4:7])
   records+=n;segments.append(dict(kind='NORMAL_WITH_COLOR',scale=scale,vertices=vertices,normals=normals,declared_qwc_bytes=h3[0]*16,audited_bytes=size))
   cur+=48+size
   if sn:span(cur,16);cur+=16
  materials.append(dict(material=m,descriptor=desc.hex(),segments=segments))
 if not materials:raise ValueError('empty rigid32 BIN')
 return dict(status='audited-rigid32',kind='NORMAL_WITH_COLOR',color_records=records,normal_records=records,materials=materials,render_qualified=False,qualification='Node extent / attribute range / segment bounds; VIF24 versus actual32 mismatch remains a repack/runtime boundary')