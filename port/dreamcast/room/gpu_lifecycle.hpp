#pragma once
namespace re4dc::gpu {
// Call between scenes, before retiring or replacing submitted resources.
enum class FenceResult { ready, ta_timeout, render_timeout };
FenceResult quiesce();
}
