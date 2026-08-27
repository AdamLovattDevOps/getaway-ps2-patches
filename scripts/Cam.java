//@category Getaway
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.scalar.*;
import java.io.*;
import java.util.*;
import java.util.regex.*;

public class Cam extends GhidraScript {
  Memory M; FunctionManager FM; ReferenceManager RM; DecompInterface ifc; String out;
  Address A(long o){ return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(o); }
  Set<Function> todo = new LinkedHashSet<>();
  String dec(Function f){ DecompileResults r=ifc.decompileFunction(f,60,monitor); return r.getDecompiledFunction()!=null?r.getDecompiledFunction().getC():"// fail "+r.getErrorMessage(); }
  void save(Function f) throws Exception { try(PrintWriter pw=new PrintWriter(out+"/decomp/"+f.getName()+".c")){pw.print(dec(f));} }
  List<Long> ptrsTo(long target) throws Exception { List<Long> r=new ArrayList<>(); byte[] pat=new byte[]{(byte)target,(byte)(target>>8),(byte)(target>>16),(byte)(target>>24)};
    Address s=A(0x100000), e=A(0x3d9464); while(true){ Address h=M.findBytes(s,e,pat,null,true,monitor); if(h==null)break; if((h.getOffset()&3)==0) r.add(h.getOffset()); s=h.add(1);} return r; }
  public void run() throws Exception {
    String[] a=getScriptArgs(); out=a[0]; M=currentProgram.getMemory(); FM=currentProgram.getFunctionManager(); RM=currentProgram.getReferenceManager();
    ifc=new DecompInterface(); ifc.openProgram(currentProgram); new File(out+"/decomp").mkdirs();
    // a) RTTI: map __tf funcs -> class names via string refs
    Map<Function,String> tf=new LinkedHashMap<>();
    for (Data d : currentProgram.getListing().getDefinedData(true)) {
      if (d.getAddress().getOffset()>=0x10000000) break;
      Object v=d.getValue(); if(v==null) continue; String s=v.toString(); if(!s.matches("^\\d+[A-Za-z_]\\w*$")) continue;
      String cls=s.replaceFirst("^\\d+","");
      for (Reference r: RM.getReferencesTo(d.getAddress())) { Function f=FM.getFunctionContaining(r.getFromAddress()); if(f!=null && f.getBody().getNumAddresses()<400) tf.put(f,cls); }
    }
    Pattern bss=Pattern.compile("(?:DAT|PTR|UNK|LAB)_00([3-5][0-9a-f]{5})");
    try(PrintWriter pw=new PrintWriter(out+"/vtables.txt")){
      for (Map.Entry<Function,String> e: tf.entrySet()){
        String cls=e.getValue(); if(!cls.matches(a.length>1?a[1]:".*")) continue;
        Function f=e.getKey(); if(f.getName().startsWith("FUN_")) f.setName("__tf_"+cls, SourceType.ANALYSIS);
        String c=dec(f); Matcher m=bss.matcher(c); Set<Long> cands=new TreeSet<>();
        while(m.find()){ long v=Long.parseLong(m.group(1),16); if(v>=0x3d9464) cands.add(v);} 
        for(long ti:cands){ for(long vref:ptrsTo(ti)){ long vt=vref+4; pw.printf("== %s __tf=%s typeinfo=%08x vtable=%08x\n",cls,f.getName(),ti,vt);
          for(int i=0;i<64;i++){ long v=M.getInt(A(vt+4L*i))&0xffffffffL; if(v<0x100000||v>=0x3d0000||(v&3)!=0)break; Function vf=FM.getFunctionAt(A(v));
            if(vf==null){pw.printf("  [%2d] %08x nofunc\n",i,v);continue;} if(vf.getName().startsWith("FUN_")) vf.setName(cls+"_vf"+i,SourceType.ANALYSIS); pw.printf("  [%2d] %08x %s\n",i,v,vf.getName()); todo.add(vf);} } }
      }
    }
    // b) pad: callers of Pad ctor and of scePadPortOpen chain
    try(PrintWriter pw=new PrintWriter(out+"/pad.txt")){
      for(String n: new String[]{"FUN_002a3388"}){ Function f=getGlobalFunctions(n).get(0); f.setName("Pad_ctor",SourceType.ANALYSIS);
        for(Reference r: RM.getReferencesTo(f.getEntryPoint())){ Function c=FM.getFunctionContaining(r.getFromAddress()); pw.printf("Pad_ctor caller %s @%s\n",c,r.getFromAddress()); if(c!=null)todo.add(c);} }
      // libpad neighbourhood: list functions 0x30e000-0x30f800
      for(Function f: FM.getFunctions(A(0x30e000),true)){ if(f.getEntryPoint().getOffset()>0x30f800)break; pw.printf("libpad %08x %5d %s\n",f.getEntryPoint().getOffset(),f.getBody().getNumAddresses(),f.getName()); }
    }
    for(Function f: todo) save(f);
    println("done "+todo.size());
  }
}
