#!/usr/bin/env python3
"""Patch NetherSX2/AetherSX2 APK to add 0.25x resolution scale multiplier."""
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

LOCALE_ENTRY_MAP = {
    "values": "0.25x Native",
    "values-ar-rSA": "0.25x الدقة",
    "values-ckb-rIR": "0.25x کوالێتی گرافیک",
    "values-es-rES": "0.25x Nativo",
    "values-fil-rPH": "0.25x Neytib",
    "values-fr-rFR": "0.25x Natif",
    "values-hu-rHU": "Natív 0.25x",
    "values-in-rID": "0.25x Resolusi",
    "values-it-rIT": "0.25x Nativo",
    "values-ko-rKR": "0.25x",
    "values-nl-rNL": "0.25x Origineel",
    "values-pt-rBR": "0,25x Nativa",
    "values-pt-rPT": "0.25x Nativo",
    "values-ru-rRU": "0.25x нативное",
    "values-sk-rSK": "0,25x natívne",
    "values-th-rTH": "0.25x จากความละเอียดดั้งเดิม (~120p)",
    "values-zh-rCN": "0.25倍原生",
    "values-zh-rTW": "0.25x 原生",
}


def patch_arrays(res_dir: Path) -> int:
    modified_files = 0

    for arrays_path in sorted(res_dir.glob("values*/arrays.xml")):
        tree = ET.parse(arrays_path)
        root = tree.getroot()
        changed = False
        folder_name = arrays_path.parent.name

        # Patch gs_upscale_values in res/values/arrays.xml
        for sa in root.findall("./string-array[@name='gs_upscale_values']"):
            items = [item.text for item in sa.findall("item")]
            if items and "0.250000" not in items:
                new_item = ET.Element("item")
                new_item.text = "0.250000"
                sa.insert(0, new_item)
                changed = True

        # Patch gs_upscale_entries in res/values/arrays.xml and all localized folders
        for sa in root.findall("./string-array[@name='gs_upscale_entries']"):
            items = [item.text for item in sa.findall("item")]
            if items and not any("0.25" in (t or "") for t in items):
                label = LOCALE_ENTRY_MAP.get(folder_name)
                if not label:
                    first = items[0] or ""
                    if "0.5" in first:
                        label = first.replace("0.5", "0.25").replace("~240p", "~120p")
                    elif "0,5" in first:
                        label = first.replace("0,5", "0,25")
                    elif "0 5" in first:
                        label = first.replace("0 5", "0.25")
                    else:
                        label = "0.25x Native"

                new_item = ET.Element("item")
                new_item.text = label
                sa.insert(0, new_item)
                changed = True

        if changed:
            # Preserve indent formatting
            ET.indent(tree, space="    ")
            tree.write(arrays_path, encoding="utf-8", xml_declaration=True)
            modified_files += 1
            print(f"Patched resolution scale multiplier in {arrays_path.relative_to(res_dir)}")

    return modified_files


def patch_decoded_dir(decoded_dir: Path) -> int:
    res_dir = decoded_dir / "res"
    if not res_dir.exists():
        raise SystemExit(f"res directory not found in {decoded_dir}")
    modified_count = patch_arrays(res_dir)
    print(f"Patched 0.25x scale multiplier in {modified_count} array files.")
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
