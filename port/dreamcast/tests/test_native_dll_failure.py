"""Actual recovered DLL wrappers must stop before entry after a rejected link."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(shutil.which('g++'), 'host C++ compiler required')
class NativeDllFailure(unittest.TestCase):
    def test_source_failure_does_not_return_or_report_completion(self):
        source = (ROOT / 'src/game/main_sub.cpp').read_text()
        macro = source[source.index('#if defined(__PPC__)\n#define HALT()'):source.index('#define VALID_PTR')]
        unlink = source[source.index('void DLL_Unlink(OSModuleHeader* module)\n{'):source.index('// Links a REL')]
        start = source.index('void DLL_Link(OSModuleHeader* module, void* bss)\n{')
        link = source[start:source.index('\n}', start)+2]
        fixture = r'''
#include <cstring>
using u32 = unsigned;
struct OSModuleHeader { void (*epilog)(); };
static bool accepted; static int reports, errors, sleeps, epilogs, entered;
struct Logger { void err(int,int,const char*,...) { ++errors; } } logger;
Logger* pLog=&logger;
void OSReport(const char* s,...) { if(std::strstr(s,"was completed"))++reports; }
void TaskSleep(int n) { sleeps+=n; }
int OSLink(OSModuleHeader*,void*) { return accepted; }
int OSUnlink(OSModuleHeader*) { return accepted; }
void re4dc_missing(const char* s) { if(std::strcmp(s,"DLL link/unlink failed"))throw 1; throw 9; }
void epilog() { ++epilogs; }
'''+macro+unlink+link+r'''
int main() {
    OSModuleHeader module{epilog};
    for(int which=0;which<2;++which) {
        accepted=false; reports=errors=sleeps=epilogs=entered=0;
        try { if(which)DLL_Unlink(&module);else DLL_Link(&module,nullptr); ++entered; }
        catch(int error) { if(error!=9)return 1; }
        if(entered || reports || errors!=1 || sleeps!=60 || epilogs!=which)return 2;
        accepted=true; reports=errors=sleeps=epilogs=0;
        if(which)DLL_Unlink(&module);else DLL_Link(&module,nullptr);
        if(reports!=1 || errors || sleeps || epilogs!=which)return 3;
    }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp = Path(tmp)/'fixture.cpp'; exe = Path(tmp)/'fixture'
            cpp.write_text(fixture)
            subprocess.run(['g++','-std=c++17','-O1',str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
