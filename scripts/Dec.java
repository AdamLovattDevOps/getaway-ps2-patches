//@category Getaway
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*; import ghidra.program.model.listing.*; import ghidra.program.model.address.*; import java.io.*;
public class Dec extends GhidraScript { public void run() throws Exception { String[] a=getScriptArgs(); DecompInterface ifc=new DecompInterface(); ifc.openProgram(currentProgram);
  for(int i=1;i<a.length;i++){ Function f; if(a[i].startsWith("0x")) f=currentProgram.getFunctionManager().getFunctionContaining(currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.parseLong(a[i].substring(2),16))); else f=getGlobalFunctions(a[i]).get(0);
    DecompileResults r=ifc.decompileFunction(f,90,monitor); try(PrintWriter pw=new PrintWriter(a[0]+"/decomp/"+f.getName()+".c")){ pw.print(r.getDecompiledFunction()!=null?r.getDecompiledFunction().getC():"// fail "+r.getErrorMessage()); } } } }
