// Inspection adapter for the pinned JADERLINK assembly, not another BIN decoder.
// Output contains private source attributes; do not commit generated JSON.
using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using System.Collections;
using System.Globalization;
using SHARED_PS2_BIN.EXTRACT;
class Ps2BinAudit {
 static string Json(object v) {
  if(v==null)return "null";
  if(v is string) {var b=new System.Text.StringBuilder("\"");foreach(char c in (string)v){if(c=='"'||c=='\\')b.Append('\\').Append(c);else if(c<32)b.Append("\\u").Append(((int)c).ToString("x4"));else b.Append(c);}return b.Append('"').ToString();}
  if(v is bool)return (bool)v?"true":"false";
  if(v is IDictionary){var items=new List<string>();foreach(DictionaryEntry e in (IDictionary)v)items.Add(Json(e.Key)+":"+Json(e.Value));return "{"+string.Join(",",items)+"}";}
  if(v is IEnumerable){var items=new List<string>();foreach(var e in (IEnumerable)v)items.Add(Json(e));return "["+string.Join(",",items)+"]";}
  if(v is IFormattable)return ((IFormattable)v).ToString(null,CultureInfo.InvariantCulture);
  return "{"+string.Join(",",v.GetType().GetProperties().Select(p=>Json(p.Name)+":"+Json(p.GetValue(v,null))))+"}";
 }
 static int Main(string[] args) {

  foreach(var request in File.ReadLines(args[0])) {
   var a=request.Split('\t'); var result=new Dictionary<string,object>();
   result["smd"]=a[0];result["bin"]=int.Parse(a[1]);result["offset"]=long.Parse(a[2]);result["bytes"]=int.Parse(a[3]);
   try {
    var data=new byte[int.Parse(a[3])];using(var file=File.OpenRead(a[0])) {file.Position=long.Parse(a[2]);int n=0;while(n<data.Length){int got=file.Read(data,n,data.Length-n);if(got==0)throw new EndOfStreamException();n+=got;}}
    PS2BIN bin;long end;using(var stream=new MemoryStream(data,false))bin=BINdecoder.Decode(stream,0,out end);
    if(bin.Magic!=0x30 || end>data.Length)throw new InvalidDataException("BIN magic or extent");
    var parts=new List<object>();int color=0,normal=0;
    for(int i=0;i<bin.Nodes.Length;i++) {
     var segments=new List<object>();foreach(var s in bin.Nodes[i].Segments){
      var vertices=new List<int[]>();foreach(var v in s.vertexLines) vertices.Add(new int[]{v.VerticeX,v.VerticeY,v.VerticeZ,v.TextureU,v.TextureV,v.NormalX,v.NormalY,v.NormalZ,v.UnknownB,v.IndexComplement,v.IndexMount});
      if(s.IsScenarioColor)color+=vertices.Count;else normal+=vertices.Count;
      segments.Add(new {kind=s.IsScenarioColor?"COLOR":"NORMAL",scale=s.ConversionFactorValue,vertices=vertices});
     }
     parts.Add(new {material=i,descriptor=BitConverter.ToString(bin.materials[i].materialLine).Replace("-","").ToLowerInvariant(),segments=segments});
    }
    result["status"]="decoded";result["kind"]=color>0?(normal>0?"MIXED":"COLOR"):"NORMAL";result["color_records"]=color;result["normal_records"]=normal;result["materials"]=parts;result["decoded_end"]=end;
   }catch(Exception e){result["status"]="rejected";result["reason"]=e.GetType().Name+": "+e.Message;}
   Console.WriteLine(Json(result));
  }
  return 0;
 }
}