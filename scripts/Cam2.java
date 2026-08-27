//@category Getaway
import ghidra.app.script.GhidraScript; import ghidra.app.decompiler.*; import ghidra.program.model.listing.*; import ghidra.program.model.symbol.*; import ghidra.program.model.address.*; import java.io.*; import java.util.*; import java.nio.file.*;
public class Cam2 extends GhidraScript {
  Address A(long o){ return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(o); }
  public void run() throws Exception { String out=getScriptArgs()[0]; FunctionManager FM=currentProgram.getFunctionManager(); ReferenceManager RM=currentProgram.getReferenceManager();
    DecompInterface ifc=new DecompInterface(); ifc.openProgram(currentProgram); Set<Function> todo=new LinkedHashSet<>();
    for(String line: Files.readAllLines(Paths.get(out+"/vtables.txt"))){ String[] t=line.split(" "); String cls=t[1].split("/")[0]; 
      Function tf=FM.getFunctionAt(A(Long.parseLong(t[2].substring(3),16))); if(tf!=null&&tf.getName().startsWith("FUN_")) tf.setName("__tf_"+cls,SourceType.ANALYSIS); if(tf!=null) todo.add(tf);
      for(int i=5;i<t.length;i++){ Function f=FM.getFunctionAt(A(Long.parseLong(t[i],16))); if(f==null){ f=createFunction(A(Long.parseLong(t[i],16)),null);} if(f==null)continue; if(f.getName().startsWith("FUN_")) f.setName(cls+"_vf"+(i-5),SourceType.ANALYSIS); todo.add(f);} }
    try(PrintWriter pw=new PrintWriter(out+"/padrefs.txt")){ 
      for(long a=0x3dcd00;a<0x3dd000;a+=1){ for(Reference r: RM.getReferencesTo(A(a))){ Function f=FM.getFunctionContaining(r.getFromAddress()); pw.printf("%08x <- %s @%s %s\n",a,f!=null?f.getName():"?",r.getFromAddress(),r.getReferenceType()); if(f!=null) todo.add(f);} } }
    try(PrintWriter pw=new PrintWriter(out+"/platctl.txt")){ for(Data d: currentProgram.getListing().getDefinedData(true)){ if(d.getAddress().getOffset()>=0x10000000)break; Object v=d.getValue(); if(v==null||!v.toString().contains("platform_controller"))continue; for(Reference r: RM.getReferencesTo(d.getAddress())){ Function f=FM.getFunctionContaining(r.getFromAddress()); pw.printf("%s <- %s\n",v,f); if(f!=null) todo.add(f);} } }
    new File(out+"/decomp").mkdirs();
    for(Function f: todo){ DecompileResults r=ifc.decompileFunction(f,90,monitor); try(PrintWriter pw=new PrintWriter(out+"/decomp/"+f.getName()+".c")){ pw.print(r.getDecompiledFunction()!=null?r.getDecompiledFunction().getC():"// fail "+r.getErrorMessage()); } }
    println("done "+todo.size()); } }
