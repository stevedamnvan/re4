/* CHAR_DATA_BLOCK=1 (game30.mk; layout only): the character adapters' data - every .rodata, .data and .bss
   input section of coarse_actor.o (Leon) and coarse_ganado.o (the Ganados): the private runtime headers'
   meshes, palettes, weights and bind tables and the adapters' own state - linked as one block right after
   .data and padded so that whatever follows it moves by whole 16 KiB (the SH4 operand cache size).
   The game's .rodata and .data then sit at the addresses they have without character data, and its .bss
   (after the block) on the same cache sets, whatever the character data's size.
   The block lies before __bss_start, so neither KOS's clear of [__bss_start, _end) nor the heap at _end
   touches it, and objcopy -O binary writes it (its .bss part as zeros) like .data: no bss gap is padded.
   A -T script's input patterns are matched before the default script's, so these sections leave the
   default .rodata, .data and .bss. */
SECTIONS
{
  __re4dc_char_data_base = .;
  .re4dc_char_data :
  {
    *coarse_actor.o(.rodata .rodata.* .data .data.* .bss .bss.* COMMON)
    *coarse_ganado.o(.rodata .rodata.* .data .data.* .bss .bss.* COMMON)
  }
  . = __re4dc_char_data_base + ((. - __re4dc_char_data_base + 16383) & ~16383);
  __re4dc_char_data_end = .;
}
INSERT AFTER .data;
