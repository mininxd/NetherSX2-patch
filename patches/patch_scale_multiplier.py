#!/usr/bin/env python3
"""Patch NetherSX2/AetherSX2 APK to add 0.05x, 0.1x, and 0.25x resolution scale multipliers."""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
BUNDLED_LIB_DIR = REPO_ROOT / "decomp/lib"

SCALES = [
    {"value": "0.050000", "scale": "0.05", "p_label": "~24p"},
    {"value": "0.100000", "scale": "0.1", "p_label": "~48p"},
    {"value": "0.250000", "scale": "0.25", "p_label": "~120p"},
]

LOCALE_TEMPLATES = {
    "values": "{s}x Native",
    "values-ar-rSA": "{s}x الدقة",
    "values-ckb-rIR": "{s}x کوالێتی گرافیک",
    "values-es-rES": "{s}x Nativo",
    "values-fil-rPH": "{s}x Neytib",
    "values-fr-rFR": "{s}x Natif",
    "values-hu-rHU": "Natív {s}x",
    "values-in-rID": "{s}x Resolusi",
    "values-it-rIT": "{s}x Nativo",
    "values-ko-rKR": "{s}x",
    "values-nl-rNL": "{s}x Origineel",
    "values-pt-rBR": "{s_comma}x Nativa",
    "values-pt-rPT": "{s}x Nativo",
    "values-ru-rRU": "{s}x нативное",
    "values-sk-rSK": "{s_comma}x natívne",
    "values-th-rTH": "{s}x จากความละเอียดดั้งเดิม",
    "values-zh-rCN": "{s}倍原生",
    "values-zh-rTW": "{s}x 原生",
}


def get_entry_label(folder_name: str, s: str, p_label: str, sample_first: str) -> str:
    s_comma = s.replace(".", ",")
    has_p = "(~240p)" in sample_first
    tmpl = LOCALE_TEMPLATES.get(folder_name)
    if tmpl:
        base = tmpl.format(s=s, s_comma=s_comma)
        if has_p:
            base += f" ({p_label})"
        return base
    if "0.5" in sample_first:
        label = sample_first.replace("0.5", s)
        if has_p:
            label = label.replace("~240p", p_label)
        return label
    elif "0,5" in sample_first:
        label = sample_first.replace("0,5", s_comma)
        return label
    return f"{s}x Native" + (f" ({p_label})" if has_p else "")


def patch_arrays(res_dir: Path) -> int:
    modified_files = 0
    scale_values_set = {s["value"] for s in SCALES}

    for arrays_path in sorted(res_dir.glob("values*/arrays.xml")):
        tree = ET.parse(arrays_path)
        root = tree.getroot()
        changed = False
        folder_name = arrays_path.parent.name

        # Patch gs_upscale_values in res/values/arrays.xml
        for sa in root.findall("./string-array[@name='gs_upscale_values']"):
            for item in list(sa):
                if item.text in scale_values_set:
                    sa.remove(item)
            for i, s in enumerate(SCALES):
                new_item = ET.Element("item")
                new_item.text = s["value"]
                sa.insert(i, new_item)
            changed = True

        # Patch gs_upscale_entries in res/values/arrays.xml and all localized folders
        for sa in root.findall("./string-array[@name='gs_upscale_entries']"):
            sample_first = ""
            for item in list(sa):
                t = item.text or ""
                if not any(k in t for k in ["0.05", "0,05", "0.1", "0,1", "0.25", "0,25"]):
                    sample_first = t
                    break

            for item in list(sa):
                t = item.text or ""
                if any(k in t for k in ["0.05", "0,05", "0.1", "0,1", "0.25", "0,25"]):
                    sa.remove(item)

            for i, s in enumerate(SCALES):
                label = get_entry_label(folder_name, s["scale"], s["p_label"], sample_first)
                new_item = ET.Element("item")
                new_item.text = label
                sa.insert(i, new_item)
            changed = True

        if changed:
            # Preserve indent formatting
            ET.indent(tree, space="    ")
            tree.write(arrays_path, encoding="utf-8", xml_declaration=True)
            modified_files += 1
            print(f"Patched resolution scale multipliers in {arrays_path.relative_to(res_dir)}")

    return modified_files


# Aarch64 instruction pattern in libemucore.so:
# fmin s1, s0, s1: 01 58 21 1e
# fmov s2, #0.5:   02 10 2c 1e
# fcmp s0, s2:     00 20 22 1e
# fcsel s0, s2, s1, mi: 40 4c 21 1e
SCALE_CLAMP_PATTERN = b"\x01\x58\x21\x1e\x02\x10\x2c\x1e\x00\x20\x22\x1e\x40\x4c\x21\x1e"
# Replacement replaces `fcsel s0, s2, s1, mi` (which clamps s0 to 0.5f if s0 < 0.5f)
# with `fmov s0, s1` (20 40 20 1e), preserving requested sub-0.5x scaling (0.05x, 0.1x, 0.25x).
SCALE_UNCLAMPED_REPLACEMENT = b"\x01\x58\x21\x1e\x02\x10\x2c\x1e\x00\x20\x22\x1e\x20\x40\x20\x1e"


def patch_emucore_scale_clamp(decoded_dir: Path) -> int:
    """Unclamp upscale_multiplier minimum in libemucore.so so sub-0.5x scaling actually renders."""
    patched_count = 0
    for so_path in decoded_dir.rglob("libemucore.so"):
        data = bytearray(so_path.read_bytes())
        count = data.count(SCALE_CLAMP_PATTERN)
        if count == 1:
            idx = data.index(SCALE_CLAMP_PATTERN)
            data[idx : idx + len(SCALE_CLAMP_PATTERN)] = SCALE_UNCLAMPED_REPLACEMENT
            so_path.write_bytes(data)
            patched_count += 1
            print(f"Patched and unclamped resolution scale in {so_path.name} at offset 0x{idx:x}")
        elif SCALE_UNCLAMPED_REPLACEMENT in data:
            print(f"{so_path.name} is already unclamped for sub-0.5x scaling")
            patched_count += 1
        else:
            print(f"Warning: Scale clamp pattern not found in {so_path.name}")
    return patched_count


def patch_decoded_dir(decoded_dir: Path) -> int:
    res_dir = decoded_dir / "res"
    if not res_dir.exists():
        raise SystemExit(f"res directory not found in {decoded_dir}")
    modified_count = patch_arrays(res_dir)
    print(f"Patched resolution scale multipliers in {modified_count} array files.")
    patch_emucore_scale_clamp(decoded_dir)
    return modified_count


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def default_output_path(input_apk: Path) -> Path:
    return input_apk.with_name(f"{input_apk.stem}-0.25x.apk")


def default_tool(name: str, bundled_jar: str) -> str:
    candidate = BUNDLED_LIB_DIR / bundled_jar
    if candidate.exists():
        return str(candidate)
    return name


def tool_cmd(tool: str, label: str) -> list[str]:
    path = Path(tool)
    if path.suffix == ".jar":
        if not path.exists():
            raise SystemExit(f"{label} jar not found: {path}")
        return ["java", "-jar", str(path.resolve())]
    if os.sep in tool or (os.altsep and os.altsep in tool):
        if not path.exists():
            raise SystemExit(f"{label} executable not found: {path}")
        return [str(path.resolve())]
    if shutil.which(tool) is None:
        raise SystemExit(f"{label} not found on PATH: {tool}")
    return [tool]


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


def patch_apk(args: argparse.Namespace) -> None:
    input_path = args.input.resolve()
    if input_path.is_dir():
        patch_decoded_dir(input_path)
        return

    output_apk = (args.output or default_output_path(input_path)).resolve()
    apktool = tool_cmd(args.apktool, "apktool")
    apksigner = None if args.unsigned else tool_cmd(args.apksigner, "apksigner")
    keystore = args.keystore.resolve() if args.keystore else None

    if not input_path.exists():
        raise SystemExit(f"Input APK not found: {input_path}")
    if not args.unsigned:
        if keystore is None:
            raise SystemExit("Signing requires --keystore, or pass --unsigned to leave the rebuilt APK unsigned")
        if not keystore.exists():
            raise SystemExit(f"Keystore not found: {keystore}")

    work_dir = Path(tempfile.mkdtemp(prefix="nethersx2-scale-"))
    work_dir = work_dir.resolve()
    decoded = work_dir / "decoded"
    unsigned = work_dir / "unsigned.apk"
    aligned = work_dir / "aligned.apk"

    try:
        run(apktool + ["d", "-f", "--frame-path", str(work_dir / "framework"), "-o", str(decoded), str(input_path)])
        patch_decoded_dir(decoded)
        run(apktool + ["b", "--use-aapt2", "--frame-path", str(work_dir / "framework"), "-o", str(unsigned), str(decoded)])
        align_apk(unsigned, aligned)
        if args.unsigned:
            shutil.copyfile(aligned, output_apk)
        else:
            run(
                apksigner
                + [
                    "sign",
                    "--ks",
                    str(keystore),
                    "--ks-pass",
                    f"pass:{args.ks_pass}",
                    "--key-pass",
                    f"pass:{args.key_pass}",
                    "--out",
                    str(output_apk),
                    str(aligned),
                ]
            )
            run(apksigner + ["verify", "--verbose", str(output_apk)])
        print(f"patched APK: {output_apk}")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    bundled_keystore = BUNDLED_LIB_DIR / "android.jks"
    parser = argparse.ArgumentParser(
        description="Patch a NetherSX2/AetherSX2 APK or decoded directory to add 0.25x scale multiplier."
    )
    parser.add_argument("input", type=Path, help="Input APK or decoded directory")
    parser.add_argument("-o", "--output", type=Path, help="Output APK path (when input is APK)")
    parser.add_argument("--apktool", default=default_tool("apktool", "apktool.jar"))
    parser.add_argument("--apksigner", default=default_tool("apksigner", "apksigner.jar"))
    parser.add_argument(
        "--keystore",
        type=Path,
        default=bundled_keystore if bundled_keystore.exists() else None,
        help="Signing keystore. Defaults to decomp/lib/android.jks when present.",
    )
    parser.add_argument("--ks-pass", default="android_sign")
    parser.add_argument("--key-pass", default="android_sign_alias")
    parser.add_argument("--unsigned", action="store_true", help="Write an unsigned APK")
    return parser.parse_args()


def main() -> None:
    patch_apk(parse_args())


if __name__ == "__main__":
    main()
