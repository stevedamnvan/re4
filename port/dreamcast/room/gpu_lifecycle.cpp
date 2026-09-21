#include "gpu_lifecycle.hpp"
#include <dc/pvr.h>
namespace re4dc::gpu {
FenceResult quiesce() {
    if(pvr_wait_ready() < 0) return FenceResult::ta_timeout;
    if(pvr_wait_render_done() < 0) return FenceResult::render_timeout;
    return FenceResult::ready;
}
}
