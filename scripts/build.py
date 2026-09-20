#!/usr/bin/env python3
"""Build NetherSX2 APK and generate nethersx2.xdelta."""
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
APK_URL = "https://github.com/Trixarian/NetherSX2-patch/releases/download/0.0/15210-v1.5-4248.apk"
APK_MD5 = "c98b0e4152d3b02fbfb9f62581abada5"
BASE_APK = REPO_ROOT / "15210-v1.5-4248.apk"
WORK_DIR = REPO_ROOT / "4248"
UNSIGNED_APK = REPO_ROOT / "unsigned.apk"
ALIGNED_APK = REPO_ROOT / "aligned.apk"
FINAL_APK = REPO_ROOT / "nethersx2.apk"
FINAL_XDELTA = REPO_ROOT / "nethersx2.xdelta"

# libemucore.so binary patches
EMUCORE_PATCHES = {
    0x838560: bytes.fromhex("66000014"),  # Signature check 1
    0x83B324: bytes.fromhex("62000014"),  # Signature check 2
    0x829248: bytes.fromhex("35008052"),  # BIOS type check
    0x81b264: bytes.fromhex("04000014"),  # Scarface RetroAchievements hash check
}

# classes.dex binary patches
DEX_PATCHES = {
    0x222264: bytes.fromhex("0e00"),      # Disable ads
    0x3C5B70: bytes.fromhex("0e00"),      # Disable ads
    0x3BDAA4: bytes.fromhex("1211"),      # Restore launcher support
    0x3BDAAA: bytes.fromhex("04"),
    0x3BDAAD: bytes.fromhex("05"),
    0x3BDAB2: bytes.fromhex("15"),
    0x3BDAA6: bytes.fromhex("6e10930202000c037120b3901300"),
    0x3BDAB4: bytes([0] * 36),
    0x8: bytes.fromhex("dda2213a"),       # Checksum
}


def run_cmd(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def download_base_apk() -> None:
    if BASE_APK.exists():
        md5 = hashlib.md5(BASE_APK.read_bytes()).hexdigest()
        if md5 == APK_MD5:
            print("Found valid base APK:", BASE_APK)
            return
        print("Existing base APK MD5 mismatch, re-downloading...")
        BASE_APK.unlink()

    print(f"Downloading base APK from {APK_URL}...")
    urllib.request.urlretrieve(APK_URL, BASE_APK)
    md5 = hashlib.md5(BASE_APK.read_bytes()).hexdigest()
    if md5 != APK_MD5:
        raise SystemExit(f"Downloaded APK MD5 mismatch: expected {APK_MD5}, got {md5}")
    print("Base APK verified successfully.")


def decompile_apk() -> None:
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    apktool_jar = DECOMP_LIB / "apktool.jar"
    run_cmd(["java", "-jar", str(apktool_jar), "d", "-s", "-f", "-o", str(WORK_DIR), str(BASE_APK)])


def patch_manifest_and_layout() -> None:
    manifest_path = WORK_DIR / "AndroidManifest.xml"
    layout_path = WORK_DIR / "res" / "layout" / "activity_main.xml"

    xml_bin = "xmlstarlet" if shutil.which("xmlstarlet") else "xml"
    if not shutil.which(xml_bin):
        raise SystemExit("xmlstarlet (or xml) executable not found")

    # Manifest cleanup
    run_cmd([
        xml_bin, "ed", "-L",
        "-d", "manifest/uses-permission[@android:name='android.permission.ACCESS_NETWORK_STATE' or @android:name='com.google.android.gms.permission.AD_ID' or @android:name='android.permission.WAKE_LOCK' or @android:name='android.permission.FOREGROUND_SERVICE']",
        "-d", "manifest/queries",
        "-d", "manifest/application/service",
        "-d", "manifest/application/receiver",
        "-d", "manifest/application/meta-data[@android:name='com.google.android.gms.ads.APPLICATION_ID' or @android:name='com.google.android.gms.version']",
        "-d", "manifest/application/provider/meta-data[@android:name='androidx.work.WorkManagerInitializer']",
        "-d", "manifest/application/activity[@android:name='com.google.android.gms.ads.AdActivity' or @android:name='com.google.android.gms.version' or @android:name='com.google.android.gms.common.api.GoogleApiActivity' or @android:name='com.google.android.gms.ads.OutOfContextTestingActivity']",
        "-d", "manifest/application/provider[@android:name='com.google.android.gms.ads.MobileAdsInitProvider']",
        "-d", "manifest/application/activity/@android:preferMinimalPostProcessing",
        "-d", "manifest/application/@android:extractNativeLibs",
        "-u", "manifest/application/@android:label", "-v", "NetherSX2",
        "-u", "manifest/application/activity[@android:label='AetherSX2']/@android:label", "-v", "NetherSX2",
        str(manifest_path),
    ])

    # Layout cleanup
    run_cmd([
        xml_bin, "ed", "-L",
        "-d", "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/RelativeLayout/FrameLayout/@android:layout_above",
        "-a", "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/RelativeLayout/FrameLayout", "-t", "attr", "-n", "android:layout_alignParentBottom", "-v", "true",
        "-d", "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/RelativeLayout/com.google.android.gms.ads.AdView",
        "-u", "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/com.google.android.material.floatingactionbutton.FloatingActionButton/@android:layout_marginBottom", "-v", "16.0dip",
        str(layout_path),
    ])


def patch_scale_multiplier() -> None:
    # Use our standalone patch_scale_multiplier module
    sys.path.insert(0, str(REPO_ROOT / "patches"))
    import patch_scale_multiplier
    patch_scale_multiplier.patch_decoded_dir(WORK_DIR)


def patch_binary_file(path: Path, patches: dict[int, bytes]) -> None:
    if not path.exists():
        raise SystemExit(f"Binary file not found: {path}")
    data = bytearray(path.read_bytes())
    for offset, replacement in patches.items():
        data[offset : offset + len(replacement)] = replacement
    path.write_bytes(data)
    print(f"Patched {len(patches)} byte blocks in {path}")


def patch_binaries() -> None:
    patch_binary_file(WORK_DIR / "lib" / "arm64-v8a" / "libemucore.so", EMUCORE_PATCHES)
    patch_binary_file(WORK_DIR / "classes.dex", DEX_PATCHES)


def update_assets() -> None:
    dest_assets = WORK_DIR / "assets"
    dest_assets.mkdir(parents=True, exist_ok=True)

    # GameIndex
    merged_gameindex = REPO_ROOT / "GameIndex[merged].yaml"
    converted_gameindex = REPO_ROOT / "GameIndex[converted].yaml"
    if merged_gameindex.exists():
        shutil.copyfile(merged_gameindex, dest_assets / "GameIndex.yaml")
        print("Copied GameIndex[merged].yaml to assets/GameIndex.yaml")
    elif converted_gameindex.exists():
        shutil.copyfile(converted_gameindex, dest_assets / "GameIndex.yaml")
        print("Copied GameIndex[converted].yaml to assets/GameIndex.yaml")

    # Other repo assets
    src_assets = REPO_ROOT / "assets"
    if src_assets.exists():
        for asset in src_assets.glob("*"):
            if asset.is_file():
                shutil.copyfile(asset, dest_assets / asset.name)
                print(f"Copied {asset.name} to assets/")

    # Touchscreen theme drawables
    theme_drawables = REPO_ROOT / "old" / "scripts" / "theme" / "res" / "drawable"
    dest_drawables = WORK_DIR / "res" / "drawable"
    if theme_drawables.exists() and dest_drawables.exists():
        for png in theme_drawables.glob("*.png"):
            shutil.copyfile(png, dest_drawables / png.name)
            xml_counterpart = dest_drawables / f"{png.stem}.xml"
            if xml_counterpart.exists():
                xml_counterpart.unlink()


def rebuild_and_sign() -> None:
    apktool_jar = DECOMP_LIB / "apktool.jar"
    apksigner_jar = DECOMP_LIB / "apksigner.jar"
    keystore = DECOMP_LIB / "android.jks"

    run_cmd(["java", "-jar", str(apktool_jar), "b", "--use-aapt2", "-o", str(UNSIGNED_APK), str(WORK_DIR)])

    # Zipalign
    if shutil.which("zipalign"):
        run_cmd(["zipalign", "-f", "-v", "4", str(UNSIGNED_APK), str(ALIGNED_APK)])
    else:
        align_apk(UNSIGNED_APK, ALIGNED_APK)

    # Sign
    run_cmd([
        "java", "-jar", str(apksigner_jar),
        "sign",
        "--ks", str(keystore),
        "--ks-pass", "pass:android_sign",
        "--key-pass", "pass:android_sign_alias",
        "--out", str(FINAL_APK),
        str(ALIGNED_APK),
    ])
    run_cmd(["java", "-jar", str(apksigner_jar), "verify", "--verbose", str(FINAL_APK)])
    print("NetherSX2 APK successfully built and signed:", FINAL_APK)


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


def generate_xdelta() -> None:
    if FINAL_XDELTA.exists():
        FINAL_XDELTA.unlink()
    xdelta_bin = shutil.which("xdelta3") or shutil.which("xdelta")
    if not xdelta_bin:
        raise SystemExit("xdelta3 executable not found")

    run_cmd([xdelta_bin, "-e", "-f", "-s", str(BASE_APK), str(FINAL_APK), str(FINAL_XDELTA)])
    if not FINAL_XDELTA.exists() or FINAL_XDELTA.stat().st_size == 0:
        raise SystemExit("Failed to create nethersx2.xdelta")
    print(f"Successfully generated {FINAL_XDELTA} ({FINAL_XDELTA.stat().st_size} bytes)")


def main() -> None:
    download_base_apk()
    decompile_apk()
    patch_manifest_and_layout()
    patch_scale_multiplier()
    patch_binaries()
    update_assets()
    rebuild_and_sign()
    generate_xdelta()
    print("Build complete!")


if __name__ == "__main__":
    main()
