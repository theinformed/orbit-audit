# Offline format experiment only; never emits a production binary or changes references.
# Dry run by design: at most two in-memory artifacts, stdout report only (<4 KiB).
# Compare the same gzip level (9) used by the publisher. No network or dependencies.
import json,struct,gzip,os,time
m=json.load(open('public/data/manifest.json'))
def head(out,major,n):
 if n<24:out.append(major*32+n)
 elif n<256:out.extend(bytes([major*32+24,n]))
 elif n<65536:out.extend(bytes([major*32+25])+struct.pack('>H',n))
 elif n<4294967296:out.extend(bytes([major*32+26])+struct.pack('>I',n))
 else:out.extend(bytes([major*32+27])+struct.pack('>Q',n))
def cbor(v,out):
 if v is None:out.append(246)
 elif v is False:out.append(244)
 elif v is True:out.append(245)
 elif isinstance(v,int):head(out,0 if v>=0 else 1,v if v>=0 else -1-v)
 elif isinstance(v,float):out.extend(b'\xfb'+struct.pack('>d',v))
 elif isinstance(v,str):
  b=v.encode();head(out,3,len(b));out.extend(b)
 elif isinstance(v,list):
  head(out,4,len(v))
  for x in v:cbor(x,out)
 else:
  head(out,5,len(v))
  for k,x in v.items():cbor(k,out);cbor(x,out)
for key,p in [('orbitEvents',m['orbitEvents']['path']),('historyShard0',m['orbitHistory']['shards'][0]['path'])]:
 b=open('public/data/'+p,'rb').read();v=json.loads(b);out=bytearray();t=time.perf_counter();cbor(v,out)
 result={'artifact':key,'path':p,'json':len(b),'jsonGzipExisting':os.path.getsize('public/data/'+p+'.gz'),'cbor':len(out),'cborGzip9':len(gzip.compress(out,compresslevel=9)),'encodeSeconds':round(time.perf_counter()-t,3)}
 # Numeric JSON arrays replaced by typed-array references; retain ALL other structure.
 nums=bytearray();vectors=[0]
 def column(x):
  if isinstance(x,list):
   if len(x)>=8 and all(type(y) in (int,float) and (type(y)!=int or abs(y)<=2**53) for y in x):
    offset=len(nums);nums.extend(struct.pack('<'+'d'*len(x),*x));vectors[0]+=1
    return {'$float64le':[offset,len(x)]}
   return [column(y) for y in x]
  if isinstance(x,dict):return {k:column(y) for k,y in x.items()}
  return x
 meta=json.dumps(column(v),separators=(',',':'),ensure_ascii=False).encode();packed=struct.pack('<I',len(meta))+meta+nums
 result.update(float64Vectors=vectors[0],float64Numbers=len(nums)//8,float64Container=len(packed),float64Gzip9=len(gzip.compress(packed,compresslevel=9)))
 print(json.dumps(result))
