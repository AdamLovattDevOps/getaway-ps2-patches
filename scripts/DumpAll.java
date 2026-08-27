//Dump functions, strings+xrefs, and RTTI-ish names to text files under args[0]
//@category Getaway
import ghidra.app.script.GhidraScript;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import java.io.*;
import java.util.*;

public class DumpAll extends GhidraScript {
  public void run() throws Exception {
    String[] a = getScriptArgs();
    String out = a.length > 0 ? a[0] : "/tmp";
    Listing L = currentProgram.getListing();
    ReferenceManager RM = currentProgram.getReferenceManager();
    FunctionManager FM = currentProgram.getFunctionManager();
    try (PrintWriter pw = new PrintWriter(out + "/functions.txt")) {
      for (Function f : FM.getFunctions(true))
        pw.printf("%08x %6d %s\n", f.getEntryPoint().getOffset(), f.getBody().getNumAddresses(), f.getName());
    }
    try (PrintWriter pw = new PrintWriter(out + "/strings.txt")) {
      DataIterator di = L.getDefinedData(true);
      while (di.hasNext()) {
        Data d = di.next();
        if (!(d.getDataType() instanceof StringDataType) && !(d.getDataType() instanceof TerminatedStringDataType)) continue;
        Object v = d.getValue(); if (v == null) continue;
        String s = v.toString().replace("\n","\\n").replace("\r","\\r");
        StringBuilder xr = new StringBuilder();
        for (Reference r : RM.getReferencesTo(d.getAddress())) {
          Function f = FM.getFunctionContaining(r.getFromAddress());
          xr.append(' ').append(f != null ? f.getName() : ("?" + r.getFromAddress()));
        }
        pw.printf("%08x |%s|%s\n", d.getAddress().getOffset(), s, xr);
      }
    }
    println("functions=" + FM.getFunctionCount());
  }
}
