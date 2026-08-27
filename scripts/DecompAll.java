//@category Getaway
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*; import ghidra.program.model.listing.*; import java.io.*;
public class DecompAll extends GhidraScript { public void run() throws Exception { String out=getScriptArgs()[0]; new File(out).mkdirs(); DecompInterface ifc=new DecompInterface(); ifc.openProgram(currentProgram); int n=0;
  for(Function f: currentProgram.getFunctionManager().getFunctions(true)){ if(monitor.isCancelled())break; File o=new File(out+"/"+f.getName()+".c"); DecompileResults r=ifc.decompileFunction(f,45,monitor); try(PrintWriter pw=new PrintWriter(o)){ pw.print(r.getDecompiledFunction()!=null?r.getDecompiledFunction().getC():"// fail "+r.getErrorMessage()); } n++; if(n%500==0) println("decompiled "+n); } println("done "+n); } }
