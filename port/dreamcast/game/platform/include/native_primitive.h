#pragma once
// Native draw adapters consume source OT/position/normal bytes synchronously
// and copy final PVR packets before returning to the source Render() caller.
// Render() runs before SetPrimBuffPtr()/ClearOt()/next-frame preparation.
// The PVR never receives pointers into this source allocation. The existing
// native frame fence still owns PVR resources. A deferred source-pointer or
// DMA adapter must complete consumption before reset, or select two buffers.
#ifndef RE4DC_PRIMITIVE_BUFFERS
#define RE4DC_PRIMITIVE_BUFFERS 1
#endif
#if RE4DC_PRIMITIVE_BUFFERS != 1 && RE4DC_PRIMITIVE_BUFFERS != 2
#error RE4DC_PRIMITIVE_BUFFERS must be 1 or 2
#endif
