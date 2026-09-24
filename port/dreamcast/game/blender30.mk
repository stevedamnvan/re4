# D367 Blender-authored scenery knobs (items 20/21). Included at the end of the Makefile.
# Every knob defaults to 0 and then contributes nothing (identical image).
#   TREE_IMPOSTOR=1  a native mesh whose R4IM v2 package carries an impostor record
#                    (tools/mesh_annotate.py --impostors) draws, beyond TREE_IMPOSTOR_MM of
#                    view depth, as one camera-facing punch-through quad from a baked view
#                    atlas (4bpp palettised VQ texture package, format kPal4). Quads are
#                    batched per atlas into the PT list, which this knob enables.
#   TREE_IMPOSTOR_MM view depth (source mm) of the tree's centre where the quad takes over.
#   MESH_TEXTURES=1  a native mesh part with a texture record (tools/mesh_annotate.py --textures)
#                    draws with that prepared texture package (/cd/dc/tex/<crc>-<fnv>.re4tex)
#                    instead of its source image: the house shells (tools/house_shells.py)
#                    carry their baked GC detail this way. Geometry, pass and state stay the part's.
TREE_IMPOSTOR ?= 0
TREE_IMPOSTOR_MM ?= 12000
MESH_TEXTURES ?= 0
ifeq ($(TREE_IMPOSTOR),1)
ifneq ($(NATIVE_MESH)$(MESH_LOD),11)
$(error TREE_IMPOSTOR=1 requires NATIVE_MESH=1 and MESH_LOD=1 (R4IM v2 impostor records))
endif
endif
ifeq ($(MESH_TEXTURES),1)
ifneq ($(NATIVE_MESH)$(MESH_LOD),11)
$(error MESH_TEXTURES=1 requires NATIVE_MESH=1 and MESH_LOD=1 (R4IM v2 texture records))
endif
endif
.PHONY: blender30-force
$(OBJDIR)/blender30.h: blender30-force
	@mkdir -p $(dir $@)
	@printf '#define RE4DC_TREE_IMPOSTOR %s\n#define RE4DC_TREE_IMPOSTOR_MM %s\n#define RE4DC_MESH_TEXTURES %s\n' \
		'$(TREE_IMPOSTOR)' '$(TREE_IMPOSTOR_MM)' '$(MESH_TEXTURES)' > $@.tmp
	@cmp -s $@.tmp $@ || mv $@.tmp $@
	@rm -f $@.tmp
BLENDER30_PLATFORM = $(OBJDIR)/platform/native_static.o $(OBJDIR)/platform/native_ui.o \
	$(OBJDIR)/native-reuse/texture_package.o
$(BLENDER30_PLATFORM): $(OBJDIR)/blender30.h
$(BLENDER30_PLATFORM): PLATFORM_CPPFLAGS += -include $(OBJDIR)/blender30.h
