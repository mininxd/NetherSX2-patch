#!/usr/bin/env python3
"""Build NetherSX2 Adreno and Mali APKs with 0.25x resolution scale and generate xdelta."""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
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
        "EmuCore/GS/Renderer": "14",               # Default to Vulkan backend (direct command buffer on Mali)
        "EmuCore/GS/ThreadedPresentation": "true",  # Decouple frame presentation thread
        "EmuCore/GS/HWDownloadMode": "1",          # Disable Readbacks (eliminates TBDR tile flush stalls on Mali-G57)
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
            print(f"  ✓ Configured Vulkan (14), Threaded Presentation, and HWDownloadMode (1) in {p.name}")
    for p in work_dir.rglob("graphics_game_settings_preferences.xml"):
        if update_preference_xml(p, {"EmuCore/GS/HWDownloadMode": "1"}):
            print(f"  ✓ Defaulted HWDownloadMode (1 - Disable Readbacks) in {p.name}")
    for p in work_dir.rglob("advanced_preferences.xml"):
        if update_preference_xml(p, adv_updates):
            print(f"  ✓ Configured DisableDualSourceBlend and SkipDuplicateFrames in {p.name}")
    for p in work_dir.rglob("system_preferences.xml"):
        if update_preference_xml(p, sys_updates):
            print(f"  ✓ Configured MTVU, Performance Core Affinity, and FastCDVD in {p.name}")

    # Customize Setup Wizard and Settings to clearly label Fast Mode (Mali Edition)
    import hashlib
    import zlib

    str_updated = 0
    for p in work_dir.rglob("strings.xml"):
        text = p.read_text(encoding="utf-8")
        original = text
        parent = p.parent.name
        if "values-in" in parent:
            text = re.sub(r'(<string name="setup_wizard_safe_defaults">)[^<]+(</string>)', r'\g<1>Mode Cepat (Edisi Mali)\g<2>', text)
            text = re.sub(r'(<string name="setup_wizard_safe_defaults_summary">)[^<]+(</string>)', r'\g<1>Dioptimalkan untuk GPU Mali (Vulkan, Matikan Readback, Presentasi Berulir, MTVU, Afinitas Core Kinerja).\g<2>', text)
            text = re.sub(r'(<string name="setup_wizard_settings_message">)[^<]+(</string>)', r'\g<1>Silakan pilih preset kinerja untuk digunakan. Untuk GPU Mali (mis. Mali-G57 MC2), pilih Mode Cepat (Edisi Mali) untuk rendering Vulkan yang dioptimalkan, tanpa lag TBDR tile flush, presentasi berulir, dan afinitas core kinerja CPU. Anda dapat mengatur ulang profil kapan saja di Pengaturan Aplikasi.\g<2>', text)
            text = re.sub(r'(<string name="settings_reset_to_fast_defaults">)[^<]+(</string>)', r'\g<1>Atur Ulang ke Default Cepat (Edisi Mali)\g<2>', text)
        else:
            text = re.sub(r'(<string name="setup_wizard_safe_defaults">)[^<]+(</string>)', r'\g<1>Fast Mode (Mali Edition)\g<2>', text)
            text = re.sub(r'(<string name="setup_wizard_safe_defaults_summary">)[^<]+(</string>)', r'\g<1>Optimized for Mali GPUs (Vulkan, Disabled Readbacks, Threaded Presentation, MTVU, Performance Core Affinity).\g<2>', text)
            text = re.sub(r'(<string name="setup_wizard_settings_message">)[^<]+(</string>)', r'\g<1>Please select a performance preset to use. For Mali GPUs (e.g. Mali-G57 MC2), select Fast Mode (Mali Edition) for preconfigured Vulkan rendering, eliminated TBDR tile flush stalls, threaded presentation, and performance-core CPU affinity. You can change this profile at any time in App Settings.\g<2>', text)
            text = re.sub(r'(<string name="settings_reset_to_fast_defaults">)[^<]+(</string>)', r'\g<1>Reset To Fast Defaults (Mali Edition)\g<2>', text)
        if text != original:
            p.write_text(text, encoding="utf-8")
            str_updated += 1
    print(f"  ✓ Updated Setup Wizard & Settings to 'Fast Mode (Mali Edition)' in {str_updated} strings.xml files")

    # Patch classes.dex so Setup Wizard selects Fast Mode (Mali Edition) by default
    dex_target = b"\x1a\x0e\x96\x15\x1a\x00\x5b\x24"      # getString("UI/PerformancePreset", "safe")
    dex_replacement = b"\x1a\x0e\x96\x15\x1a\x00\x16\x29" # getString("UI/PerformancePreset", "unsafe")
    for dex_path in work_dir.rglob("classes*.dex"):
        dex_data = bytearray(dex_path.read_bytes())
        if dex_target in dex_data:
            idx = dex_data.index(dex_target)
            dex_data[idx:idx+len(dex_target)] = dex_replacement
            # Recompute DEX SHA-1 signature and Adler32 checksum
            dex_data[12:32] = hashlib.sha1(dex_data[32:]).digest()
            dex_data[8:12] = (zlib.adler32(dex_data[12:]) & 0xffffffff).to_bytes(4, "little")
            dex_path.write_bytes(dex_data)
            print(f"  ✓ Patched {dex_path.name} to default Setup Wizard preset to 'Fast Mode (Mali Edition)'")


def inject_scale_multiplier(input_apk: Path, output_apk: Path, work_name: str, is_mali: bool = False) -> None:
    work_dir = REPO_ROOT / work_name
    if work_dir.exists():
        shutil.rmtree(work_dir)

    apkeditor = ensure_apkeditor()
    # Decode with -dex so classes.dex and native libraries are kept raw and resource IDs are preserved
    run_cmd(["java", "-jar", str(apkeditor), "d", "-dex", "-f", "-i", str(input_apk), "-o", str(work_dir)])

    # Delete all custom controller PNG buttons entirely and restore clean original vector buttons
    remove_custom_controller_buttons(work_dir)

    # If building Mali APK, apply Mali-specific Vulkan and Threaded Presentation defaults
    if is_mali:
        apply_mali_optimizations(work_dir)

    # Patch resolution scale multiplier in arrays.xml and libemucore.so
    sys.path.insert(0, str(PATCHES_DIR))
    from patch_scale_multiplier import patch_arrays, patch_emucore_scale_clamp
    modified = 0
    for res_dir in work_dir.rglob("res"):
        if res_dir.is_dir():
            modified += patch_arrays(res_dir)
    print(f"Patched resolution scales (0.05x, 0.1x, 0.25x) in {modified} arrays.xml files inside {work_name}")
    patch_emucore_scale_clamp(work_dir)

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


def verify_all() -> None:
    print("\n==========================================")
    print("Verifying built artifacts...")
    print("==========================================")
    for apk in [ADRENO_FINAL_APK, MALI_FINAL_APK]:
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
            custom_buttons = [n for n in z.namelist() if n.endswith(".png") and "ic_controller_" in n]
            if custom_buttons:
                raise SystemExit(f"ERROR: Custom controller buttons still found in {apk.name}: {custom_buttons}")
            xml_buttons = [n for n in z.namelist() if n.startswith("res/drawable/ic_controller_") and n.endswith(".xml")]
            if len(xml_buttons) != 34:
                raise SystemExit(f"ERROR: Expected 34 original controller XML buttons, found {len(xml_buttons)} in {apk.name}!")
            if apk == MALI_FINAL_APK and b"Fast Mode (Mali Edition)" not in arsc:
                raise SystemExit(f"ERROR: 'Fast Mode (Mali Edition)' missing in {apk.name} resources.arsc!")
        print(f"✓ {apk.name}: 0.05x, 0.1x, 0.25x (XML + unclamped libemucore.so) & original controller XML buttons verified")

    if not ADRENO_FINAL_XDELTA.exists() or ADRENO_FINAL_XDELTA.stat().st_size == 0:
        raise SystemExit(f"Missing or empty xdelta: {ADRENO_FINAL_XDELTA}")
    print(f"✓ {ADRENO_FINAL_XDELTA.name} confirmed ({ADRENO_FINAL_XDELTA.stat().st_size} bytes)")
    print("\nAll builds and verifications completed successfully!")


def main() -> None:
    build_adreno()
    build_mali()
    verify_all()


if __name__ == "__main__":
    main()
