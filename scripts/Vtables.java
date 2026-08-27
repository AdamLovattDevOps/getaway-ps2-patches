//Recover vtables from GCC2 RTTI names; decompile functions by name list; dump callers.
//args: outdir  vtableRegex  decompList(comma names/addrs)  callersOf(comma names)
//@category Getaway
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.mem.*;
import java.io.*;
import java.util.*;

public class Vtables extends GhidraScript {
  Memory M; ReferenceManager RM; FunctionManager FM; Listing L;
  Address A(long o){ return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(o); }
  long u32(Address a) throws Exception { return M.getInt(a) & 0xffffffffL; }
  boolean inText(long v){ return v >= 0x100000 && v < 0x3d0000 && (v & 3)==0; }

  public void run() throws Exception {
    String[] a = getScriptArgs();
    String out=a[0]; String re=a.length>1?a[1]:".*Camera.*"; String dec=a.length>2?a[2]:""; String callers=a.length>3?a[3]:"";
    M=currentProgram.getMemory(); RM=currentProgram.getReferenceManager(); FM=currentProgram.getFunctionManager(); L=currentProgram.getListing();
    Set<Function> toDecomp = new LinkedHashSet<>();
    try (PrintWriter pw = new PrintWriter(out + "/vtables.txt")) {
      DataIterator di = L.getDefinedData(true);
      while (di.hasNext()) {
        Data d = di.next();
        if (!(d.getDataType() instanceof StringDataType) && !(d.getDataType() instanceof TerminatedStringDataType)) continue;
        if (d.getAddress().getOffset() >= 0x10000000) continue;
        String s = String.valueOf(d.getValue());
        if (!s.matches(re) || !s.matches("^\\d+.*")) continue;
        String cls = s.replaceFirst("^\\d+","");
        // typeinfo objects: data refs to the name
        for (Reference r : RM.getReferencesTo(d.getAddress())) {
          Address ti = r.getFromAddress();
          if (FM.getFunctionContaining(ti) != null) continue;
          // gcc2: typeinfo = {vptr, name}; ref is at ti+4 -> object at ti-4
          Address tiObj = ti.subtract(4);
          // vtables: {offset, typeinfo*} then funcs; find refs to tiObj
          for (Reference r2 : RM.getReferencesTo(tiObj)) {
            Address vt = r2.getFromAddress().add(4);
            pw.printf("== %s typeinfo=%08x vtable=%08x\n", cls, tiObj.getOffset(), vt.getOffset());
            for (int i=0;i<64;i++){
              long v = u32(vt.add(i*4));
              if (!inText(v)) break;
              Function f = FM.getFunctionAt(A(v));
              if (f==null){ pw.printf("  [%2d] %08x (nofunc)\n", i, v); continue; }
              pw.printf("  [%2d] %08x %s\n", i, v, f.getName());
              if (!f.getName().startsWith("FUN_") || f.getBody().getNumAddresses() > 0) toDecomp.add(f);
              if (!f.getName().equals(cls+"_vf"+i) && f.getName().startsWith("FUN_")) f.setName(cls+"_vf"+i, SourceType.ANALYSIS);
            }
          }
        }
      }
    }
    for (String n : dec.split(",")) { if(n.isEmpty()) continue;
      Function f = n.startsWith("0x") ? FM.getFunctionContaining(A(Long.parseLong(n.substring(2),16))) : getGlobalFunctions(n).isEmpty()?null:getGlobalFunctions(n).get(0);
      if (f!=null) toDecomp.add(f); else println("no func "+n); }
    try (PrintWriter pw = new PrintWriter(out + "/callers.txt")) {
      for (String n : callers.split(",")) { if(n.isEmpty()) continue;
        List<Function> fs = getGlobalFunctions(n); if (fs.isEmpty()) continue;
        Function f = fs.get(0); pw.println("== callers of "+n);
        for (Reference r : RM.getReferencesTo(f.getEntryPoint())) { Function c=FM.getFunctionContaining(r.getFromAddress()); pw.printf("  %s @%s\n", c!=null?c.getName():"?", r.getFromAddress()); if(c!=null) toDecomp.add(c);} }
    }
    DecompInterface ifc = new DecompInterface(); ifc.openProgram(currentProgram);
    new File(out+"/decomp").mkdirs();
    for (Function f : toDecomp) {
      DecompileResults res = ifc.decompileFunction(f, 60, monitor);
      try (PrintWriter pw = new PrintWriter(out+"/decomp/"+f.getName()+".c")) {
        pw.println(res.getDecompiledFunction()!=null ? res.getDecompiledFunction().getC() : "// decompile failed: "+res.getErrorMessage()); }
    }
    println("decompiled " + toDecomp.size());
  }
}
