#pragma once
// A native filesystem call can yield while retaining KOS locks. Source ISR
// timeslicing must wait for that bounded call to release those locks. This
// does not disable IRQs, KOS preemption, or source gameplay scheduling.
extern "C" {
void* re4dc_io_begin();
void re4dc_io_end(void* owner);
int re4dc_io_busy(const void* source_thread);
}
class Re4dcIoScope {
    void* owner_;
public:
    Re4dcIoScope() : owner_(re4dc_io_begin()) {}
    ~Re4dcIoScope() { re4dc_io_end(owner_); }
    Re4dcIoScope(const Re4dcIoScope&)=delete;
    Re4dcIoScope& operator=(const Re4dcIoScope&)=delete;
};

// Serialize one recovered DVD queue step across native reads that can yield.
// A declined acquisition is still pending; callers yield and retry, never skip
// the step. Ownership extends through source post-callback bookkeeping.
extern "C" void* re4dc_dvd_step_begin();
extern "C" void re4dc_dvd_step_end(void*);
