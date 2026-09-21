/* PowerPC link names the generator cannot derive (tools/gen_aliases.py):
 * constructors declared with an asm label the SH-4 compiler ignores, GCC 2.95
 * allocation builtins, a libc name reached through asm("memset"), and a
 * variable defined under an asm label but referenced as a plain C symbol. */
__ZN11cSsPartsMgrC1Ev = __ZN9cPartsMgrC1Ev;      /* cSsPartsMgr() asm("__9cPartsMgr") */
__ZN11cSsPartsMgrC2Ev = __ZN9cPartsMgrC1Ev;
__ZN13cSsModInfoMgrC1Ev = __ZN11cModInfoMgrC1Ev; /* cSsModInfoMgr() asm("__11cModInfoMgr") */
__ZN13cSsModInfoMgrC2Ev = __ZN11cModInfoMgrC1Ev;
___builtin_new = __Znwj;                          /* puzzle.cpp: GCC 2.95 names of operator new/delete */
___builtin_vec_new = __Znaj;
___builtin_delete = __ZdlPv;
___builtin_vec_delete = __ZdaPv;
memset = _memset;                                 /* route_ck.cpp memset_v(...) asm("memset") */
_m3r = m3r;                                       /* pl_knife.cpp: defined under asm("m3r") */
