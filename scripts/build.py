#!/usr/bin/env python3
"""Build NetherSX2 Adreno and Mali APKs with 0.25x resolution scale and generate xdelta."""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DECOMP_LIB = REPO_ROOT / "decomp" / "lib"
PATCHES_DIR = REPO_ROOT / "patches"

# Adreno paths
ADRENO_SRC_APK = REPO_ROOT / "apk" / "xyz.aethersx2.android_v1.5-4248_adreno.apk"
ADRENO_FALLBACK_APK = REPO_ROOT / "15210-v1.5-4248.apk"
ADRENO_URL = "https://github.com/Trixarian/NetherSX2-patch/releases/download/0.0/15210-v1.5-4248.apk"
ADRENO_MD5 = "c98b0e4152d3b02fbfb9f62581abada5"
ADRENO_NETHERSX2_XDELTA = REPO_ROOT / "old" / "scripts" / "builder" / "lib" / "nethersx2.xdelta"
ADRENO_FINAL_APK = REPO_ROOT / "xyz.aethersx2.android_adreno.apk"
ADRENO_FINAL_XDELTA = REPO_ROOT / "xyz.aethersx2.android_.xdelta"

# Mali paths
MALI_SRC_APK = REPO_ROOT / "apk" / "xyz.aethersx2.android_v1.5-3668_mali.apk"
MALI_FALLBACK_APK = REPO_ROOT / "13930-v1.5-3668.apk"
MALI_URL = "https://github.com/Trixarian/NetherSX2-classic/releases/download/0.0/13930-v1.5-3668.apk"
MALI_MD5 = "4a1751fa99bc4dcd647114c4d64e7985"
MALI_CLASSIC_XDELTA_URL = "https://github.com/Trixarian/NetherSX2-classic/releases/download/1.0/nethersx2-classic.xdelta"
MALI_CLASSIC_XDELTA = REPO_ROOT / "nethersx2-classic.xdelta"
MALI_FINAL_APK = REPO_ROOT / "xyz.aethersx2.android_mali.apk"

# Switch paths (Nvidia Tegra X1 / Maxwell GM20B)
SWITCH_FINAL_APK = REPO_ROOT / "xyz.aethersx2.android_switch.apk"

# Tools
APKEDITOR_JAR = DECOMP_LIB / "APKEditor.jar"
APKEDITOR_URL = "https://github.com/REAndroid/APKEditor/releases/download/V1.4.9/APKEditor-1.4.9.jar"
APKSIGNER_JAR = DECOMP_LIB / "apksigner.jar"
KEYSTORE = DECOMP_LIB / "android.jks"


def run_cmd(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def get_xdelta_bin() -> str:
    xdelta_bin = shutil.which("xdelta3") or shutil.which("xdelta")
    if not xdelta_bin:
        raise SystemExit("xdelta3 executable not found")
    return xdelta_bin


def ensure_apkeditor() -> Path:
    if not APKEDITOR_JAR.exists():
        print(f"Downloading APKEditor from {APKEDITOR_URL}...")
        urllib.request.urlretrieve(APKEDITOR_URL, APKEDITOR_JAR)
    return APKEDITOR_JAR


def align_apk(input_apk: Path, output_apk: Path, alignment: int = 4) -> None:
    pad_header_id = 0xD935
    with zipfile.ZipFile(input_apk, "r") as zin, zipfile.ZipFile(output_apk, "w") as zout:
        for src in zin.infolist():
            info = zipfile.ZipInfo(src.filename, date_time=src.date_time)
            info.compress_type = src.compress_type
            info.comment = src.comment
            info.external_attr = src.external_attr
            info.internal_attr = src.internal_attr
            info.create_system = src.create_system
            info.extra = src.extra
            data = zin.read(src.filename)

            if src.compress_type == zipfile.ZIP_STORED:
                filename_len = len(src.filename.encode("utf-8"))
                data_offset = zout.fp.tell() + 30 + filename_len + len(info.extra)
                needed = (-data_offset) % alignment
                if needed:
                    total_extra = needed if needed >= 4 else needed + alignment
                    payload_len = total_extra - 4
                    info.extra += (
                        pad_header_id.to_bytes(2, "little")
                        + payload_len.to_bytes(2, "little")
                        + (b"\x00" * payload_len)
                    )

            zout.writestr(info, data)


def zipalign_apk(input_apk: Path, output_apk: Path) -> None:
    if shutil.which("zipalign"):
        run_cmd(["zipalign", "-f", "-p", "4", str(input_apk), str(output_apk)])
    else:
        align_apk(input_apk, output_apk)


def sign_apk(unsigned_apk: Path, signed_apk: Path) -> None:
    run_cmd([
        "java", "-jar", str(APKSIGNER_JAR),
        "sign",
        "--ks", str(KEYSTORE),
        "--ks-pass", "pass:android_sign",
        "--key-pass", "pass:android_sign_alias",
        "--out", str(signed_apk),
        str(unsigned_apk),
    ])
    run_cmd(["java", "-jar", str(APKSIGNER_JAR), "verify", "--verbose", str(signed_apk)])


def get_adreno_base_apk() -> Path:
    if ADRENO_SRC_APK.exists():
        md5 = hashlib.md5(ADRENO_SRC_APK.read_bytes()).hexdigest()
        if md5 == ADRENO_MD5:
            return ADRENO_SRC_APK
    if ADRENO_FALLBACK_APK.exists():
        md5 = hashlib.md5(ADRENO_FALLBACK_APK.read_bytes()).hexdigest()
        if md5 == ADRENO_MD5:
            return ADRENO_FALLBACK_APK

    print(f"Downloading Adreno base APK from {ADRENO_URL}...")
    urllib.request.urlretrieve(ADRENO_URL, ADRENO_FALLBACK_APK)
    return ADRENO_FALLBACK_APK


def get_mali_base_apk() -> Path:
    if MALI_SRC_APK.exists():
        md5 = hashlib.md5(MALI_SRC_APK.read_bytes()).hexdigest()
        if md5 == MALI_MD5:
            return MALI_SRC_APK
    if MALI_FALLBACK_APK.exists():
        md5 = hashlib.md5(MALI_FALLBACK_APK.read_bytes()).hexdigest()
        if md5 == MALI_MD5:
            return MALI_FALLBACK_APK

    print(f"Downloading Mali base APK from {MALI_URL}...")
    urllib.request.urlretrieve(MALI_URL, MALI_FALLBACK_APK)
    return MALI_FALLBACK_APK


def remove_custom_controller_buttons(work_dir: Path) -> None:
    # Delete all custom controller PNG button images from the APK
    deleted = 0
    for png in list(work_dir.rglob("ic_controller_*.png")):
        png.unlink()
        deleted += 1
    print(f"Deleted {deleted} custom controller PNG images from {work_dir.name}")

    # Restore clean original AetherSX2 vector XML buttons (plain text XML)
    buttons_dir = REPO_ROOT / "patches" / "controller_buttons"
    if buttons_dir.exists():
        restored = 0
        for res_dir in work_dir.rglob("res"):
            if res_dir.is_dir():
                dest_drawable = res_dir / "drawable"
                dest_drawable.mkdir(parents=True, exist_ok=True)
                for xml_file in buttons_dir.glob("*.xml"):
                    shutil.copyfile(xml_file, dest_drawable / xml_file.name)
                    restored += 1
        print(f"Restored {restored} clean original AetherSX2 controller vector XML buttons.")


def apply_mali_optimizations(work_dir: Path) -> None:
    print("Applying exclusive Mali GPU core, rendering, and CPU-affinity performance optimizations...")
    import re

    def update_preference_xml(file_path: Path, updates: dict[str, str]) -> int:
        if not file_path.exists():
            return 0
        text = file_path.read_text(encoding="utf-8")
        original = text
        for key, new_val in updates.items():
            def replace_default(m: re.Match) -> str:
                tag = m.group(0)
                if "app:defaultValue=" in tag:
                    return re.sub(r'app:defaultValue="[^"]*"', f'app:defaultValue="{new_val}"', tag)
                elif tag.endswith("/>"):
                    return tag[:-2].rstrip() + f' app:defaultValue="{new_val}" />'
                elif tag.endswith(">"):
                    return tag[:-1].rstrip() + f' app:defaultValue="{new_val}">'
                return tag

            pattern = re.compile(rf'<[^>]+app:key="{re.escape(key)}"[^>]*>', re.DOTALL)
            text = pattern.sub(replace_default, text)
        if text != original:
            file_path.write_text(text, encoding="utf-8")
            return 1
        return 0

    gfx_updates = {
        "EmuCore/GS/Renderer": "14",                 # Default to Vulkan backend (direct command buffer on Mali)
        "EmuCore/GS/ThreadedPresentation": "true",    # Decouple frame presentation thread
        "EmuCore/GS/HWDownloadMode": "1",            # Disable Readbacks (eliminates light occlusion & TBDR tile flush stalls)
        "EmuCore/GS/accurate_blending_unit": "0",    # Minimum Blending Accuracy (eliminates multi-pass light/sun/bloom lag)
        "EmuCore/GS/texture_preloading": "2",        # Full Texture Hash Cache (keeps decoded textures resident in RAM)
    }
    adv_updates = {
        "EmuCore/GS/DisableDualSourceBlend": "true", # Fix Mali driver dual-source blending bottlenecks
        "EmuCore/GS/SkipDuplicateFrames": "true",    # Conserve tile memory bandwidth on Mali TBDR
    }
    sys_updates = {
        "EmuCore/Speedhacks/vuThread": "true",        # MTVU (Multi-Threaded VU1) for 8-core Mali SoCs
        "EmuCore/AffinityControlMode": "7",           # Bind emulation threads to Performance Cores
        "EmuCore/Speedhacks/fastCDVD": "true",        # Fast CDVD read speeds
    }

    # Inject global HWDownloadMode into graphics_preferences.xml if absent
    for p in work_dir.rglob("graphics_preferences.xml"):
        text = p.read_text(encoding="utf-8")
        if "EmuCore/GS/HWDownloadMode" not in text:
            hw_download_tag = """    <ListPreference app:defaultValue="1"
                    app:entries="@array/gs_hardware_download_mode_entries"
                    app:entryValues="@array/gs_hardware_download_mode_values"
                    app:iconSpaceReserved="false"
                    app:key="EmuCore/GS/HWDownloadMode"
                    app:title="@string/gs_hardware_download_mode"
                    app:useSimpleSummaryProvider="true" />
  </PreferenceCategory>"""
            text = re.sub(
                r'(<ListPreference[^>]+app:key="EmuCore/GS/texture_preloading"[^>]*>[\s\n]*)(</PreferenceCategory>)',
                r'\g<1>' + hw_download_tag,
                text,
            )
            p.write_text(text, encoding="utf-8")

    for p in work_dir.rglob("graphics_preferences.xml"):
        if update_preference_xml(p, gfx_updates):
            print(f"  ✓ Configured Vulkan (14), Threaded Presentation, HWDownloadMode (1), Blending Accuracy (0 - Minimum), and Texture Preloading (2 - Full) in {p.name}")
    for p in work_dir.rglob("graphics_game_settings_preferences.xml"):
        if update_preference_xml(p, {
            "EmuCore/GS/HWDownloadMode": "1",
            "EmuCore/GS/accurate_blending_unit": "0",
            "EmuCore/GS/texture_preloading": "2",
        }):
            print(f"  ✓ Defaulted HWDownloadMode (1), Blending Accuracy (0), and Texture Preload (2) in {p.name}")
    for p in work_dir.rglob("advanced_preferences.xml"):
        if update_preference_xml(p, adv_updates):
            print(f"  ✓ Configured DisableDualSourceBlend and SkipDuplicateFrames in {p.name}")
    for p in work_dir.rglob("system_preferences.xml"):
        if update_preference_xml(p, sys_updates):
            print(f"  ✓ Configured MTVU, Performance Core Affinity, and FastCDVD in {p.name}")

    # Customize ONLY the Setup Wizard preset button text: change Fast/Unsafe to Fast(Mali)/Unsafe,
    # keeping the original descriptions and reset setting text untouched.
    str_updated = 0
    for p in work_dir.rglob("strings.xml"):
        text = p.read_text(encoding="utf-8")
        original = text
        text = re.sub(r'(<string name="setup_wizard_safe_defaults">)[^<]+(</string>)', r'\g<1>Fast(Mali)/Unsafe Defaults\g<2>', text)
        if text != original:
            p.write_text(text, encoding="utf-8")
            str_updated += 1
    print(f"  ✓ Updated Setup Wizard preset button to 'Fast(Mali)/Unsafe Defaults' in {str_updated} strings.xml files")

    # Patch classes.dex:
    # 1. Setup Wizard selects Fast(Mali)/Unsafe Defaults by default ("safe" -> "unsafe")
    # 2. Setup Wizard defaults Renderer to Vulkan ("14") instead of OpenGL ("12")
    dex_target = b"\x1a\x0e\x96\x15\x1a\x00\x5b\x24"      # getString("UI/PerformancePreset", "safe")
    dex_replacement = b"\x1a\x0e\x96\x15\x1a\x00\x16\x29" # getString("UI/PerformancePreset", "unsafe")
    str_12_target = b"00000\x00\x0212\x00\r3rdparty.h"
    str_14_replacement = b"00000\x00\x0214\x00\r3rdparty.h"

    for dex_path in work_dir.rglob("classes*.dex"):
        dex_data = bytearray(dex_path.read_bytes())
        dex_modified = False
        if dex_target in dex_data:
            idx = dex_data.index(dex_target)
            dex_data[idx:idx+len(dex_target)] = dex_replacement
            dex_modified = True
            print(f"  ✓ Patched {dex_path.name} to default Setup Wizard preset to 'Fast(Mali)/Unsafe Defaults'")

        if str_12_target in dex_data:
            idx = dex_data.index(str_12_target)
            dex_data[idx:idx+len(str_12_target)] = str_14_replacement
            dex_modified = True
            print(f"  ✓ Patched {dex_path.name} Setup Wizard default Renderer to Vulkan (14)")

        if dex_modified:
            # Recompute DEX SHA-1 signature and Adler32 checksum
            dex_data[12:32] = hashlib.sha1(dex_data[32:]).digest()
            dex_data[8:12] = (zlib.adler32(dex_data[12:]) & 0xffffffff).to_bytes(4, "little")
            dex_path.write_bytes(dex_data)

    # Patch NativeLibrary.setDefaultSettings in libemucore.so:
    # 1. When 'unsafe' preset is applied, set HWDownloadMode to '1' (Disable Readbacks - Unsynchronized)
    # 2. Keep EECycleSkip at '0' (Normal) instead of '2' (Cycle Skip 2) to eliminate animation jitter,
    #    black screens, and visual glitches in Black and other games.
    so_pattern_hw = bytes.fromhex("82c7ff9042541591e00313aae10314aae30316aa00013fd6")
    so_replacement_hw = bytes.fromhex("82c7ff9042541591e00313aae10314aae30317aa00013fd6")

    so_pattern_skip = bytes.fromhex("5911899a7611899ae00313aa") # csel x25, x10, x9; csel x22, x11, x9; mov x0, x19
    so_replacement_skip = bytes.fromhex("5911899af60309aae00313aa") # csel x25, x10, x9; mov x22, x9; mov x0, x19

    for so_path in work_dir.rglob("libemucore.so"):
        so_data = bytearray(so_path.read_bytes())
        so_modified = False
        if so_pattern_hw in so_data:
            idx = so_data.index(so_pattern_hw)
            so_data[idx:idx+len(so_pattern_hw)] = so_replacement_hw
            so_modified = True
            print(f"  ✓ Patched {so_path.name} setDefaultSettings to set HWDownloadMode=1 (Unsynchronized)")
        if so_pattern_skip in so_data:
            idx = so_data.index(so_pattern_skip)
            so_data[idx:idx+len(so_pattern_skip)] = so_replacement_skip
            so_modified = True
            print(f"  ✓ Patched {so_path.name} setDefaultSettings to keep EECycleSkip=0 (Normal) in Unsafe mode")
        if so_modified:
            so_path.write_bytes(so_data)


def apply_switch_optimizations(work_dir: Path) -> None:
    """Apply optimizations specifically for Nintendo Switch (Nvidia Tegra X1 / Maxwell 256 CUDA cores):
    1. Vulkan backend (14) - direct command buffer execution on Nvidia's desktop-grade Vulkan driver.
    2. DisableDualSourceBlend: "false" - Enable hardware dual-source blending (Maxwell architecture executes desktop dual-source blending natively).
    3. ThreadedPresentation: "true" - Decouples presentation thread to eliminate frame pacing jitter on Cortex-A57 CPU cores.
    4. HWDownloadMode: "1" - Disable Readbacks (Unsynchronized) to stop CPU/GPU synchronization wait-states.
    5. MTVU (vuThread: "true") - Offloads VU1 to separate thread, utilizing the Switch's 4 cores.
    6. EECycleRate: "-1" (75% Underclock) - Prevents audio crackle and thermal throttling on the Switch's 1.0-1.7 GHz CPU.
    7. Fast CDVD (fastCDVD: "true") - Faster game streaming and asset loading.
    8. AffinityControlMode: "0" - No core pinning, letting Linux CFS distribute load across all 4 A57 cores.
    """
    def update_preference_xml(file_path: Path, updates: dict[str, str]) -> int:
        if not file_path.exists():
            return 0
        text = file_path.read_text(encoding="utf-8")
        original = text
        for key, new_val in updates.items():
            def replace_default(match: re.Match) -> str:
                tag = match.group(0)
                if 'app:defaultValue="' in tag:
                    return re.sub(r'app:defaultValue="[^"]*"', f'app:defaultValue="{new_val}"', tag)
                elif tag.endswith("/>"):
                    return tag[:-2].rstrip() + f' app:defaultValue="{new_val}" />'
                elif tag.endswith(">"):
                    return tag[:-1].rstrip() + f' app:defaultValue="{new_val}">'
                return tag

            pattern = re.compile(rf'<[^>]+app:key="{re.escape(key)}"[^>]*>', re.DOTALL)
            text = pattern.sub(replace_default, text)
        if text != original:
            file_path.write_text(text, encoding="utf-8")
            return 1
        return 0

    gfx_updates = {
        "EmuCore/GS/Renderer": "14",                 # Vulkan
        "EmuCore/GS/ThreadedPresentation": "true",    # Threaded presentation (huge on 4-core A57)
        "EmuCore/GS/HWDownloadMode": "1",            # Disable Readbacks (Unsynchronized)
        "EmuCore/GS/accurate_blending_unit": "1",    # Basic Blending (Maxwell hardware handles blending effortlessly)
        "EmuCore/GS/texture_preloading": "2",        # Full Texture Hash Cache
    }
    adv_updates = {
        "EmuCore/GS/DisableDualSourceBlend": "false", # Maxwell GM20B has native hardware dual-source blending!
        "EmuCore/GS/SkipDuplicateFrames": "false",
    }
    sys_updates = {
        "EmuCore/Speedhacks/vuThread": "true",        # MTVU (vital for 4 A57 cores)
        "EmuCore/Speedhacks/EECycleRate": "-1",       # 75% EE Underclock (matches Switch CPU clock headroom)
        "EmuCore/Speedhacks/fastCDVD": "true",        # Fast CDVD
        "EmuCore/AffinityControlMode": "0",           # Normal affinity for Tegra X1
    }

    # Inject global HWDownloadMode into graphics_preferences.xml if absent
    for p in work_dir.rglob("graphics_preferences.xml"):
        text = p.read_text(encoding="utf-8")
        if "EmuCore/GS/HWDownloadMode" not in text:
            hw_download_tag = """    <ListPreference app:defaultValue="1"
                    app:entries="@array/gs_hardware_download_mode_entries"
                    app:entryValues="@array/gs_hardware_download_mode_values"
                    app:iconSpaceReserved="false"
                    app:key="EmuCore/GS/HWDownloadMode"
                    app:title="@string/gs_hardware_download_mode"
                    app:useSimpleSummaryProvider="true" />
  </PreferenceCategory>"""
            text = re.sub(
                r'(<ListPreference[^>]+app:key="EmuCore/GS/texture_preloading"[^>]*>[\s\n]*)(</PreferenceCategory>)',
                r'\g<1>' + hw_download_tag,
                text,
            )
            p.write_text(text, encoding="utf-8")

    for p in work_dir.rglob("graphics_preferences.xml"):
        if update_preference_xml(p, gfx_updates):
            print(f"  ✓ Configured Switch Tegra X1 graphics in {p.name}")
    for p in work_dir.rglob("graphics_game_settings_preferences.xml"):
        if update_preference_xml(p, {
            "EmuCore/GS/HWDownloadMode": "1",
            "EmuCore/GS/accurate_blending_unit": "1",
            "EmuCore/GS/texture_preloading": "2",
        }):
            print(f"  ✓ Defaulted HWDownloadMode (1), Blending Accuracy (1), and Texture Preload (2) in {p.name}")
    for p in work_dir.rglob("advanced_preferences.xml"):
        if update_preference_xml(p, adv_updates):
            print(f"  ✓ Enabled hardware Dual-Source Blend for Tegra X1 Maxwell in {p.name}")
    for p in work_dir.rglob("system_preferences.xml"):
        if update_preference_xml(p, sys_updates):
            print(f"  ✓ Configured MTVU, -1 EE Cycle Rate, and FastCDVD for Switch in {p.name}")

    # Customize Setup Wizard preset text for Switch
    str_updated = 0
    for p in work_dir.rglob("strings.xml"):
        text = p.read_text(encoding="utf-8")
        original = text
        text = re.sub(r'(<string name="setup_wizard_safe_defaults">)[^<]+(</string>)', r'\g<1>Switch(Tegra X1) Defaults\g<2>', text)
        if text != original:
            p.write_text(text, encoding="utf-8")
            str_updated += 1
    print(f"  ✓ Updated Setup Wizard preset button to 'Switch(Tegra X1) Defaults' in {str_updated} strings.xml files")


def patch_preserve_user_data_on_reset(work_dir: Path) -> None:
    """Patch NativeLibrary.setDefaultSettings in libemucore.so:
    Prevent resetting core, memory cards, achievements, and input bindings when resetting to Optimal or Fast defaults.
    Replaces:
      mov w2, #1 (reset_core = true)  -> mov w2, wzr (reset_core = false)
      mov w3, #1 (reset_input = true) -> mov w3, wzr (reset_input = false)
    Ensures that applying performance presets never wipes memory cards, RetroAchievements login/settings, or custom controls.
    """
    pattern = bytes.fromhex("e1031f2a2200805223008052e4031f2ae5031f2a")
    replacement = bytes.fromhex("e1031f2ae2031f2ae3031f2ae4031f2ae5031f2a")

    for so_path in work_dir.rglob("libemucore.so"):
        so_data = bytearray(so_path.read_bytes())
        if pattern in so_data:
            idx = so_data.index(pattern)
            so_data[idx:idx+len(pattern)] = replacement
            so_path.write_bytes(so_data)
            print(f"  ✓ Patched {so_path.name} setDefaultSettings to preserve memory cards, achievements, and controls on reset")


def patch_gameindex(work_dir: Path) -> None:
    """Patch GameIndex.yaml inside decoded APK:
    1. Black: Ensure vuClampMode: 3 (fixes SPS polygon spikes), autoFlush: 1 (fixes light strips), and minimumBlendingLevel: 2.
    2. Downhill Domination: Disable sun lighting / lens flare post-processing and stage backdrop, and disable autoFlush (1 -> 0).
    3. Tales of the Abyss: Disable autoFlush (1 -> 0) to prevent TBDR tile flush stalls.
    """
    downhill_patch = """  patches:
    default:
      content: |-
        author=Community
        comment=Disable Sun, Lens Flare Post-processing, and Stage Backdrop
        patch=1,EE,0029DBA5,byte,0
        patch=1,EE,0029E200,byte,0
    5AE01D98:
      content: |-
        author=Community
        comment=Disable Sun, Lens Flare Post-processing, and Stage Backdrop
        patch=1,EE,0029DBA5,byte,0
        patch=1,EE,0029E200,byte,0
"""
    black_serials = ["SLAJ-25078", "SLES-53886", "SLES-54030", "SLPM-66354", "SLUS-21376", "SLKA-25372"]

    def patch_downhill_scus(m: re.Match) -> str:
        block = m.group(0)
        block = re.sub(r"(autoFlush:\s*)1", r"\g<1>0", block)
        if "patches:" not in block:
            block = block.rstrip() + "\n" + downhill_patch
        else:
            if "0029E200" not in block:
                block = block.replace("patch=1,EE,0029DBA5,byte,0", "patch=1,EE,0029DBA5,byte,0\n        patch=1,EE,0029E200,byte,0")
        return block

    gi_updated = 0
    for p in work_dir.rglob("GameIndex.yaml"):
        text = p.read_text(encoding="utf-8")
        orig = text
        for s in black_serials:
            # Ensure vuClampMode is 3 (fixes SPS polygon explosion)
            pattern_vu = rf"({s}:.*?\n\s*name:\s*[\"\x27]Black[\"\x27].*?vuClampMode:\s*)[0-2]"
            text = re.sub(pattern_vu, r"\g<1>3", text, flags=re.DOTALL)
            # Ensure autoFlush is 1 (fixes light strips and missing sky)
            pattern_af = rf"({s}:.*?\n\s*name:\s*[\"\x27]Black[\"\x27].*?autoFlush:\s*)0"
            text = re.sub(pattern_af, r"\g<1>1", text, flags=re.DOTALL)
            # Ensure minimumBlendingLevel: 2 is present in Black's gsHWFixes
            pattern_blend = rf"({s}:.*?\n\s*name:\s*[\"\x27]Black[\"\x27].*?gsHWFixes:\s*\n)(?!\s*minimumBlendingLevel:)"
            text = re.sub(pattern_blend, r"\g<1>    minimumBlendingLevel: 2 # Fixes building and object lighting.\n", text, flags=re.DOTALL)

        # Patch Downhill Domination SCUS-97177 (NTSC-U) with sun disable patch and autoFlush 0
        text = re.sub(r"SCUS-97177:.*?(?=\n[A-Z]{4}-[0-9]{5}:|\Z)", patch_downhill_scus, text, flags=re.DOTALL)

        # Disable autoFlush for other Downhill Domination releases (PAL and Demos)
        for s in ["SLES-52202", "SCUS-97329", "SLED-52325"]:
            pattern_dh = rf"({s}:.*?\n\s*name:\s*[\"\x27]Downhill Domination.*?autoFlush:\s*)1"
            text = re.sub(pattern_dh, r"\g<1>0", text, flags=re.DOTALL)

        # Disable autoFlush for Tales of the Abyss
        for s in ["SCAJ-20163", "SLUS-21386"]:
            pattern_tales = rf"({s}:.*?\n\s*name:\s*[\"\x27]Tales of the Abyss.*?autoFlush:\s*)1"
            text = re.sub(pattern_tales, r"\g<1>0", text, flags=re.DOTALL)

        # Patch Midnight Club 3 (SLUS-21355, SLUS-21029, SLES-53717, SLES-52942) to disable motion blur
        mc3_blur_patch = """        // Disable Motion Blur (eliminates Mali TBDR fillrate lag and blur accumulation)
        patch=1,EE,201CC3D4,extended,00000000
        patch=1,EE,201CC3D8,extended,00000000
        patch=1,EE,201CC3E0,extended,00000000
        patch=1,EE,201CC3E8,extended,00000000
        patch=1,EE,201CC38C,extended,00000000
        patch=1,EE,201CC39C,extended,00000000"""

        def patch_mc3_block(m: re.Match) -> str:
            block = m.group(0)
            if "201CC3D4" not in block:
                block = re.sub(r"(patch=1,EE,2052[0-9A-F]{4},extended,00000000)", r"\g<1>\n" + mc3_blur_patch, block)
            return block

        for s in ["SLUS-21355", "SLUS-21029", "SLES-53717", "SLES-52942"]:
            text = re.sub(rf"({s}:.*?\n)(?=[A-Z]{{4}}-[0-9]{{5}}:|\Z)", patch_mc3_block, text, flags=re.DOTALL)

        if text != orig:
            p.write_text(text, encoding="utf-8")
            gi_updated += 1
    print(f"  ✓ Patched GameIndex.yaml (optimized Black, Downhill Domination, Tales of the Abyss, and Midnight Club 3 in {gi_updated} files)")


def patch_manifest_target_sdk(work_dir: Path, target_sdk: int = 34) -> None:
    """Update AndroidManifest.xml targetSdkVersion and compileSdkVersion to modern Android standards (API 34)."""
    manifest_path = work_dir / "AndroidManifest.xml"
    if not manifest_path.exists():
        return
    text = manifest_path.read_text(encoding="utf-8")
    orig = text

    # Update android:targetSdkVersion
    if 'android:targetSdkVersion=' in text:
        text = re.sub(r'android:targetSdkVersion="[0-9]+"', f'android:targetSdkVersion="{target_sdk}"', text)
    elif '<uses-sdk' in text:
        text = re.sub(r'(<uses-sdk\b[^>]*?)(\s*/>|>)', rf'\g<1> android:targetSdkVersion="{target_sdk}"\g<2>', text)

    # Update compileSdkVersion and platformBuildVersionCode so Android 14/15 does not see legacy build versions
    text = re.sub(r'android:compileSdkVersion="[0-9]+"', f'android:compileSdkVersion="{target_sdk}"', text)
    text = re.sub(r'android:compileSdkVersionCodename="[^"]+"', f'android:compileSdkVersionCodename="{target_sdk}"', text)
    text = re.sub(r'platformBuildVersionCode="[0-9]+"', f'platformBuildVersionCode="{target_sdk}"', text)
    text = re.sub(r'platformBuildVersionName="[^"]+"', f'platformBuildVersionName="{target_sdk}"', text)

    for json_file in work_dir.glob("*.json"):
        try:
            jtext = json_file.read_text(encoding="utf-8")
            jtext_mod = re.sub(r'("targetSdkVersion"\s*:\s*)[0-9]+', rf'\g<1>{target_sdk}', jtext)
            jtext_mod = re.sub(r'("target_sdk_version"\s*:\s*)[0-9]+', rf'\g<1>{target_sdk}', jtext_mod)
            if jtext_mod != jtext:
                json_file.write_text(jtext_mod, encoding="utf-8")
        except Exception:
            pass

    if text != orig:
        manifest_path.write_text(text, encoding="utf-8")
        print(f"  ✓ Patched AndroidManifest.xml: targetSdkVersion={target_sdk}, compileSdkVersion={target_sdk}")


def inject_scale_multiplier(input_apk: Path, output_apk: Path, work_name: str, is_mali: bool = False, is_switch: bool = False) -> None:
    work_dir = REPO_ROOT / work_name
    if work_dir.exists():
        shutil.rmtree(work_dir)

    apkeditor = ensure_apkeditor()
    # Decode with -dex so classes.dex and native libraries are kept raw and resource IDs are preserved
    run_cmd(["java", "-jar", str(apkeditor), "d", "-dex", "-f", "-i", str(input_apk), "-o", str(work_dir)])

    # Delete all custom controller PNG buttons entirely and restore clean original vector buttons
    remove_custom_controller_buttons(work_dir)

    # Patch GameIndex.yaml with database optimizations (Black, Downhill Domination)
    patch_gameindex(work_dir)

    # If building Mali or Switch APK, apply device-specific defaults
    if is_mali:
        apply_mali_optimizations(work_dir)
    elif is_switch:
        apply_switch_optimizations(work_dir)

    # Preserve user data (Memory Cards, RetroAchievements login & settings, controller mappings) when resetting defaults
    patch_preserve_user_data_on_reset(work_dir)

    # Patch targetSdkVersion and compileSdkVersion to Android 14 (API 34) for full Android 15 compatibility
    patch_manifest_target_sdk(work_dir, target_sdk=34)

    # Patch resolution scale multiplier in arrays.xml and libemucore.so
    sys.path.insert(0, str(PATCHES_DIR))
    from patch_scale_multiplier import patch_arrays, patch_emucore_scale_clamp
    from patch_mali_vulkan import patch_mali_vulkan_core
    modified = 0
    for res_dir in work_dir.rglob("res"):
        if res_dir.is_dir():
            modified += patch_arrays(res_dir)
    print(f"Patched resolution scales (0.05x, 0.1x, 0.25x) in {modified} arrays.xml files inside {work_name}")
    patch_emucore_scale_clamp(work_dir)
    patch_mali_vulkan_core(work_dir)

    # Rebuild with APKEditor (preserves original resource IDs)
    raw_rebuilt = REPO_ROOT / f"{work_name}_rebuilt.apk"
    run_cmd(["java", "-jar", str(apkeditor), "b", "-framework-version", "34", "-f", "-i", str(work_dir), "-o", str(raw_rebuilt)])

    # Zipalign
    aligned = REPO_ROOT / f"{work_name}_aligned.apk"
    zipalign_apk(raw_rebuilt, aligned)

    # Sign
    sign_apk(aligned, output_apk)

    # Cleanup temporary files
    shutil.rmtree(work_dir, ignore_errors=True)
    if raw_rebuilt.exists():
        raw_rebuilt.unlink()
    if aligned.exists():
        aligned.unlink()


def build_adreno() -> None:
    print("\n==========================================")
    print("Building NetherSX2 Adreno (v1.5-4248) APK")
    print("==========================================")
    base_apk = get_adreno_base_apk()
    xdelta_bin = get_xdelta_bin()

    if not ADRENO_NETHERSX2_XDELTA.exists():
        raise SystemExit(f"Adreno NetherSX2 xdelta patch not found: {ADRENO_NETHERSX2_XDELTA}")

    adreno_nethersx2_base = REPO_ROOT / "adreno_nethersx2_base.apk"
    # Apply official NetherSX2 4248 patch
    run_cmd([xdelta_bin, "-d", "-f", "-s", str(base_apk), str(ADRENO_NETHERSX2_XDELTA), str(adreno_nethersx2_base)])

    # Inject 0.25x scale multiplier and sign
    inject_scale_multiplier(adreno_nethersx2_base, ADRENO_FINAL_APK, "work_adreno")
    if adreno_nethersx2_base.exists():
        adreno_nethersx2_base.unlink()

    # Also keep nethersx2.apk for compatibility
    shutil.copyfile(ADRENO_FINAL_APK, REPO_ROOT / "nethersx2.apk")

    # Generate xdelta against base Adreno APK
    if ADRENO_FINAL_XDELTA.exists():
        ADRENO_FINAL_XDELTA.unlink()
    run_cmd([xdelta_bin, "-e", "-f", "-s", str(base_apk), str(ADRENO_FINAL_APK), str(ADRENO_FINAL_XDELTA)])
    shutil.copyfile(ADRENO_FINAL_XDELTA, REPO_ROOT / "nethersx2.xdelta")
    print(f"Generated {ADRENO_FINAL_XDELTA} ({ADRENO_FINAL_XDELTA.stat().st_size} bytes)")


def build_mali() -> None:
    print("\n==========================================")
    print("Building NetherSX2 Mali (v1.5-3668) APK")
    print("==========================================")
    base_apk = get_mali_base_apk()
    xdelta_bin = get_xdelta_bin()

    # Ensure classic xdelta is downloaded
    if not MALI_CLASSIC_XDELTA.exists():
        print(f"Downloading NetherSX2 classic xdelta from {MALI_CLASSIC_XDELTA_URL}...")
        urllib.request.urlretrieve(MALI_CLASSIC_XDELTA_URL, MALI_CLASSIC_XDELTA)

    mali_nethersx2_base = REPO_ROOT / "mali_nethersx2_base.apk"
    # Apply NetherSX2 Classic 3668 patch
    run_cmd([xdelta_bin, "-d", "-f", "-s", str(base_apk), str(MALI_CLASSIC_XDELTA), str(mali_nethersx2_base)])

    # Inject 0.25x scale multiplier and sign
    inject_scale_multiplier(mali_nethersx2_base, MALI_FINAL_APK, "work_mali", is_mali=True)
    if mali_nethersx2_base.exists():
        mali_nethersx2_base.unlink()
    print(f"Successfully built {MALI_FINAL_APK}")


def build_switch() -> None:
    print("\n==========================================")
    print("Building NetherSX2 Nintendo Switch (Tegra X1) APK")
    print("==========================================")
    base_apk = get_adreno_base_apk()
    xdelta_bin = get_xdelta_bin()

    if not ADRENO_NETHERSX2_XDELTA.exists():
        raise SystemExit(f"Adreno NetherSX2 xdelta patch not found: {ADRENO_NETHERSX2_XDELTA}")

    switch_nethersx2_base = REPO_ROOT / "switch_nethersx2_base.apk"
    run_cmd([xdelta_bin, "-d", "-f", "-s", str(base_apk), str(ADRENO_NETHERSX2_XDELTA), str(switch_nethersx2_base)])

    inject_scale_multiplier(switch_nethersx2_base, SWITCH_FINAL_APK, "work_switch", is_switch=True)
    if switch_nethersx2_base.exists():
        switch_nethersx2_base.unlink()
    shutil.copyfile(SWITCH_FINAL_APK, REPO_ROOT / "nethersx2_switch.apk")
    print(f"Successfully built {SWITCH_FINAL_APK}")


def verify_all() -> None:
    print("\n==========================================")
    print("Verifying built artifacts...")
    print("==========================================")
    for apk in [ADRENO_FINAL_APK, MALI_FINAL_APK, SWITCH_FINAL_APK]:
        if not apk.exists():
            raise SystemExit(f"Missing output APK: {apk}")
        with zipfile.ZipFile(apk) as z:
            arsc = z.read("resources.arsc")
            for scale_val in [b"0.050000", b"0.100000", b"0.250000"]:
                if scale_val not in arsc:
                    raise SystemExit(f"ERROR: {scale_val.decode()} render option missing in {apk.name}!")
            so_bytes = z.read("lib/arm64-v8a/libemucore.so")
            patched_pattern = b"\x01\x58\x21\x1e\x02\x10\x2c\x1e\x00\x20\x22\x1e\x20\x40\x20\x1e"
            if patched_pattern not in so_bytes:
                raise SystemExit(f"ERROR: libemucore.so in {apk.name} still has 0.5f minimum clamp!")
            mali_vulkan_pattern = bytes.fromhex("490100521f2003d54d008052")
            if mali_vulkan_pattern not in so_bytes:
                raise SystemExit(f"ERROR: libemucore.so in {apk.name} missing Mali Vulkan dual-source blend patch!")
            custom_buttons = [n for n in z.namelist() if n.endswith(".png") and "ic_controller_" in n]
            if custom_buttons:
                raise SystemExit(f"ERROR: Custom controller buttons still found in {apk.name}: {custom_buttons}")
            xml_buttons = [n for n in z.namelist() if n.startswith("res/drawable/ic_controller_") and n.endswith(".xml")]
            if len(xml_buttons) != 34:
                raise SystemExit(f"ERROR: Expected 34 original controller XML buttons, found {len(xml_buttons)} in {apk.name}!")
            if apk == MALI_FINAL_APK and b"Fast(Mali)/Unsafe Defaults" not in arsc:
                raise SystemExit(f"ERROR: 'Fast(Mali)/Unsafe Defaults' missing in {apk.name} resources.arsc!")
            if apk == SWITCH_FINAL_APK and b"Switch(Tegra X1) Defaults" not in arsc:
                raise SystemExit(f"ERROR: 'Switch(Tegra X1) Defaults' missing in {apk.name} resources.arsc!")
            if shutil.which("aapt"):
                out = subprocess.check_output(["aapt", "dump", "badging", str(apk)]).decode("utf-8", errors="ignore")
                if "targetSdkVersion:'34'" not in out:
                    raise SystemExit(f"ERROR: targetSdkVersion is not 34 in {apk.name}!")
        print(f"✓ {apk.name}: 0.05x, 0.1x, 0.25x (XML + unclamped libemucore.so) & targetSdkVersion 34 verified")

    if not ADRENO_FINAL_XDELTA.exists() or ADRENO_FINAL_XDELTA.stat().st_size == 0:
        raise SystemExit(f"Missing or empty xdelta: {ADRENO_FINAL_XDELTA}")
    print(f"✓ {ADRENO_FINAL_XDELTA.name} confirmed ({ADRENO_FINAL_XDELTA.stat().st_size} bytes)")
    print("\nAll builds and verifications completed successfully!")


def main() -> None:
    build_adreno()
    build_mali()
    build_switch()
    verify_all()


if __name__ == "__main__":
    main()
