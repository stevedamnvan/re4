#pragma once
// Selectable immutable EVD backing. It is not a mutable ARAM implementation.
#ifndef RE4DC_EVENT_FILES
#define RE4DC_EVENT_FILES 0
#endif
#define RE4DC_EVENT_FILE_FLAG 4
struct Re4dcEventFileStats {
    unsigned prepared, installed, moves, failures;
    unsigned bytes_read, worst_wait_us, metadata_bytes_read;
};
extern "C" {
int re4dc_event_file_name(const char* name);
int re4dc_event_file_prepare(const char* name, unsigned bytes);
int re4dc_event_file_install(const char* name, unsigned bytes, void* destination);
void re4dc_event_file_moved();
const Re4dcEventFileStats* re4dc_event_file_stats();
// Source unit ownership remains in DC; no duplicate range registry.
int re4dc_event_file_range(unsigned address, unsigned bytes);
void re4dc_event_file_reject_swap();
int re4dc_dvd_native_path(const char* name, char* output, unsigned capacity);
}
