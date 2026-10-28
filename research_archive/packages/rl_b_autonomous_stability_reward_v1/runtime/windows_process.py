"""Windows-only owned Job Object and process telemetry. No simulator changes."""
import ctypes as c
from ctypes import wintypes as w
import time
k=c.WinDLL('kernel32',use_last_error=True)
p=c.WinDLL('psapi',use_last_error=True)
class Basic(c.Structure):
    _fields_=[('user',c.c_int64),('process_user',c.c_int64),('flags',w.DWORD),('min_ws',c.c_size_t),('max_ws',c.c_size_t),('active',w.DWORD),('affinity',c.c_size_t),('priority',w.DWORD),('scheduling',w.DWORD)]
class IO(c.Structure):
    _fields_=[(x,c.c_uint64) for x in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
class Extended(c.Structure):
    _fields_=[('basic',Basic),('io',IO),('process_memory',c.c_size_t),('job_memory',c.c_size_t),('peak_process',c.c_size_t),('peak_job',c.c_size_t)]
class Memory(c.Structure):
    _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(x,c.c_size_t) for x in ('peak_ws','ws','peak_paged','paged','peak_nonpaged','nonpaged','pagefile','peak_pagefile','private')]
k.CreateJobObjectW.restype=w.HANDLE
k.SetInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD]
k.AssignProcessToJobObject.argtypes=[w.HANDLE,w.HANDLE]
k.SetProcessAffinityMask.argtypes=[w.HANDLE,c.c_size_t]
k.SetPriorityClass.argtypes=[w.HANDLE,w.DWORD]
k.TerminateJobObject.argtypes=[w.HANDLE,w.UINT]
k.CloseHandle.argtypes=[w.HANDLE]
k.GetProcessTimes.argtypes=[w.HANDLE,c.c_void_p,c.c_void_p,c.c_void_p,c.c_void_p]
k.GetProcessIoCounters.argtypes=[w.HANDLE,c.c_void_p]
k.QueryInformationJobObject.argtypes=[w.HANDLE,c.c_int,c.c_void_p,w.DWORD,c.c_void_p]
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD]
k.OpenProcess.restype=w.HANDLE
p.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.c_void_p,w.DWORD]
class ProcessIds(c.Structure):
    _fields_=[('assigned',w.DWORD),('count',w.DWORD),('ids',c.c_size_t*128)]
def check(ok):
    if not ok:raise c.WinError(c.get_last_error())
class OwnedJob:
    def __init__(self,process):
        self.handle=k.CreateJobObjectW(None,None);check(self.handle)
        limits=Extended();limits.basic.flags=0x2000 # KILL_ON_JOB_CLOSE
        check(k.SetInformationJobObject(self.handle,9,c.byref(limits),c.sizeof(limits)))
        check(k.AssignProcessToJobObject(self.handle,int(process._handle)))
        check(k.SetPriorityClass(int(process._handle),0x4000)) # BELOW_NORMAL
        check(k.SetProcessAffinityMask(int(process._handle),0x1)) # one logical CPU
        self.process=process
    def resume(self):
        nt=c.WinDLL('ntdll');nt.NtResumeProcess.argtypes=[w.HANDLE];nt.NtResumeProcess.restype=c.c_long
        status=nt.NtResumeProcess(int(self.process._handle))
        if status!=0:raise RuntimeError(f'NtResumeProcess failed: {status}')
    def stats(self):
        ids=ProcessIds();check(k.QueryInformationJobObject(self.handle,3,c.byref(ids),c.sizeof(ids),None))
        row=dict(pids=list(ids.ids[:ids.count]),rss_bytes=0,peak_rss_bytes=0,private_bytes=0,pss_bytes=None,cpu_s=0.,write_bytes=0,read_bytes=0,telemetry_scope='all live owned job processes; peak_rss is sum of per-process peaks')
        for pid in row['pids']:
            h=k.OpenProcess(0x410,False,pid)
            if not h:continue # exited between enumeration and open
            try:
                m=Memory();m.cb=c.sizeof(m)
                if p.GetProcessMemoryInfo(h,c.byref(m),m.cb):
                    row['rss_bytes']+=m.ws;row['peak_rss_bytes']+=m.peak_ws;row['private_bytes']+=m.private
                a,b,kt,ut=[c.c_uint64() for _ in range(4)]
                if k.GetProcessTimes(h,c.byref(a),c.byref(b),c.byref(kt),c.byref(ut)):row['cpu_s']+=(kt.value+ut.value)/1e7
                io=IO()
                if k.GetProcessIoCounters(h,c.byref(io)):row['write_bytes']+=io.write_bytes;row['read_bytes']+=io.read_bytes
            finally:k.CloseHandle(h)
        return row
    def close(self):
        if self.handle:
            check(k.TerminateJobObject(self.handle,143));check(k.CloseHandle(self.handle));self.handle=None
def self_memory():
    m=Memory();m.cb=c.sizeof(m);k.GetCurrentProcess.restype=w.HANDLE
    check(p.GetProcessMemoryInfo(k.GetCurrentProcess(),c.byref(m),m.cb))
    return m.ws,m.peak_ws
