#!/usr/bin/env python3
"""Patch libemucore.so in NetherSX2/AetherSX2 APK to optimize Vulkan rendering on Mali GPUs.

Modifications to the native core (libemucore.so):
1. Unlock native hardware Dual-Source Blending for ARM Mali GPUs:
   By default, GSDeviceVK hard-checks if the GPU vendor is ARM Mali (0x13b5), and if so,
   actively disables dual-source blending even when the driver reports full hardware support.
   This forces the emulator into slow multipass fallback pipelines with heavy texture barriers.
   We patch the conditional branch so that Mali GPUs with dual-source blend support can use it directly.

2. Remove fatal Vulkan format incompatibility lockouts:
   GSDeviceVK enforces strict optimal-tiling feature bitmasks across 6 texture formats.
   On many Mali drivers (especially older Bifrost/Valhall or vendor BSP stacks), one or more formats
   lack specific bits, causing AetherSX2 to hard-abort with:
   'Vulkan Renderer Unavailable: Required format %u is missing bits'.
   The engine already contains built-in alternative fallback format paths (e.g. RGBA32F for HDR, D32F for depth).
   We bypass these 6 fatal abort branches with NOPs so Vulkan initializes cleanly on Mali GPUs.
"""
from __future__ import annotations

import struct
from pathlib import Path

ARM64_NOP = bytes.fromhex("1f2003d5")

# Pattern for ARM Mali dual-source blend blacklist check:
#   eor w9, w10, #1 (49 01 00 52)
#   cbz w9, <skip_enable> (49 00 00 34)
#   mov w13, #2 (4d 00 80 52)
MALI_DUAL_SRC_PATTERN = bytes.fromhex("49010052490000344d008052")
MALI_DUAL_SRC_REPLACEMENT = bytes.fromhex("490100521f2003d54d008052")

# Known offsets for format abort branches in 3668 and 4248
FORMAT_BRANCH_TARGETS_3668 = [0x6821cc, 0x6821d4, 0x6821dc, 0x6821e4, 0x6821ec, 0x6821f4]
FORMAT_BRANCH_TARGETS_4248 = [0x65b2dc, 0x65b2e4, 0x65b2ec, 0x65b2f4, 0x65b2fc, 0x65b304]


def patch_format_checks(data: bytearray, branch_targets: list[int], search_start: int, search_end: int) -> int:
    """Find and NOP the 6 format check abort branches targeting branch_targets."""
    patched = 0
    for target in branch_targets:
        for i in range(search_start, search_end, 4):
            w = struct.unpack("<I", data[i : i + 4])[0]
            # Match b.ne instruction: opcode 0x54000001 | (imm19 << 5)
            if (w & 0xFF00001F) == 0x54000001:
                imm19 = (w >> 5) & 0x7FFFF
                if imm19 >= (1 << 18):
                    imm19 -= (1 << 19)
                dest = i + (imm19 << 2)
                if dest == target:
                    data[i : i + 4] = ARM64_NOP
                    patched += 1
                    break
    return patched


def patch_mali_vulkan_core(decoded_dir: Path) -> int:
    """Apply native code improvements for Mali Vulkan rendering to all libemucore.so in decoded_dir."""
    patched_count = 0

    for so_path in decoded_dir.rglob("libemucore.so"):
        data = bytearray(so_path.read_bytes())
        modified = False

        # 1. Unlock Dual-Source Blending on Mali
        idx = data.find(MALI_DUAL_SRC_PATTERN)
        if idx != -1:
            data[idx : idx + len(MALI_DUAL_SRC_PATTERN)] = MALI_DUAL_SRC_REPLACEMENT
            modified = True
            print(f"  ✓ [{so_path.name}] Unlocked native hardware Dual-Source Blending for Mali at 0x{idx+4:x}")
        elif MALI_DUAL_SRC_REPLACEMENT in data:
            print(f"  ✓ [{so_path.name}] Dual-Source Blending is already unlocked for Mali")

        # 2. Bypass fatal format missing bits checks (Vulkan Renderer Unavailable)
        # Check if 3668 or 4248 by inspecting known search windows
        b_3668 = patch_format_checks(data, FORMAT_BRANCH_TARGETS_3668, 0x681D00, 0x682000)
        if b_3668 == 6:
            modified = True
            print(f"  ✓ [{so_path.name}] Bypassed all 6 fatal format checks for 3668 (enabled built-in fallback formats)")
        else:
            b_4248 = patch_format_checks(data, FORMAT_BRANCH_TARGETS_4248, 0x65AF00, 0x65B100)
            if b_4248 == 6:
                modified = True
                print(f"  ✓ [{so_path.name}] Bypassed all 6 fatal format checks for 4248 (enabled built-in fallback formats)")

        if modified:
            so_path.write_bytes(data)
            patched_count += 1

    return patched_count


if __name__ == "__main__":
    import sys
    target_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
    count = patch_mali_vulkan_core(target_dir)
    print(f"Patched {count} libraries.")
