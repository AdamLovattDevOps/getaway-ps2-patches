//@category Getaway
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*; import ghidra.program.model.listing.*; import ghidra.program.model.symbol.*; import ghidra.program.model.address.*; import java.io.*; import java.util.*;
public class Cam3 extends GhidraScript { Address A(long o){ return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(o); }
 public void run() throws Exception { String out=getScriptArgs()[0]; FunctionManager FM=currentProgram.getFunctionManager(); ReferenceManager RM=currentProgram.getReferenceManager(); DecompInterface ifc=new DecompInterface(); ifc.openProgram(currentProgram);
  Function cb=FM.getFunctionAt(A(0x2954b8)); if(cb==null) cb=createFunction(A(0x2954b8),"PadCb0");
  try(PrintWriter pw=new PrintWriter(out+"/tblrefs.txt")){ for(long t: new long[]{0x3d97d4,0x3a5d48}){ pw.println("== refs to "+Long.toHexString(t)); for(Reference r: RM.getReferencesTo(A(t))){ Function f=FM.getFunctionContaining(r.getFromAddress()); pw.printf("  <- %s @%s %s\n",f!=null?f.getName():"?",r.getFromAddress(),r.getReferenceType()); } } }
  for(long a: new long[]{0x2954b8,0x2796d8,0x2797f0}){ Function f=FM.getFunctionContaining(A(a)); if(f==null)continue; DecompileResults r=ifc.decompileFunction(f,90,monitor); try(PrintWriter pw=new PrintWriter(out+"/decomp/"+f.getName()+".c")){ pw.print(r.getDecompiledFunction()!=null?r.getDecompiledFunction().getC():"// fail "+r.getErrorMessage()); } }
 } }
