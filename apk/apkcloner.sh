#!/bin/bash

# Setup cleanup trap for Ctrl+C
cleanup() {
  echo -e "\nScript interrupted. Cleaning up..."
  # Restore original manifest if it exists
  if [ -f "${manifest_file}.original" ]; then
    mv "${manifest_file}.original" "$manifest_file"
  fi
  # Restore original strings.xml if it exists
  if [ -f "${strings_file}.original" ]; then
    mv "${strings_file}.original" "$strings_file"
  fi
  # Remove any intermediate files
  rm -f "output/${base_name}"_*_unsigned.apk "output/${base_name}"_*_aligned.apk
  exit 1
}
trap cleanup INT

# Setup portable in-place sed (macOS vs Linux)
if [ "$(uname -s)" = "Darwin" ]; then
  sedi() { sed -i '' "$@"; }
else
  sedi() { sed -i "$@"; }
fi

# Detect Android SDK build-tools if tools are not working in PATH
check_zipalign() {
  command -v zipalign >/dev/null 2>&1 && zipalign 2>&1 | grep -qi "zipalign"
}

if ! check_zipalign; then
  for bt in /opt/android-sdk/build-tools/* "$ANDROID_HOME"/build-tools/* "$ANDROID_SDK_ROOT"/build-tools/*; do
    if [ -x "$bt/zipalign" ] && "$bt/zipalign" 2>&1 | grep -qi "zipalign"; then
      export PATH="$bt:$PATH"
      break
    fi
  done
fi
if ! command -v apksigner >/dev/null 2>&1; then
  for bt in /opt/android-sdk/build-tools/* "$ANDROID_HOME"/build-tools/* "$ANDROID_SDK_ROOT"/build-tools/*; do
    if [ -x "$bt/apksigner" ]; then
      export PATH="$bt:$PATH"
      break
    fi
  done
fi

# Check for required tools
command -v apksigner >/dev/null 2>&1 || {
  echo "Error: apksigner is required but not installed. Please install Android SDK Build Tools."
  exit 1
}
check_zipalign || {
  echo "Error: zipalign is required but not installed. Please install Android SDK Build Tools."
  exit 1
}

# Create output directory
mkdir -p output

# Download latest APKEditor if not present
if [ ! -f "APKEditor.jar" ]; then
  echo "Downloading latest APKEditor..."
  APKEDITOR_URL=$(curl -s https://api.github.com/repos/REAndroid/APKEditor/releases/latest | grep -o 'https://.*APKEditor.*\.jar"' | sed 's/"$//')
  if [ -z "$APKEDITOR_URL" ]; then
    echo "Error: Could not find APKEditor download URL"
    exit 1
  fi
  echo "Downloading from: $APKEDITOR_URL"
  curl -L -o APKEditor.jar "$APKEDITOR_URL"
  if [ ! -f "APKEditor.jar" ]; then
    echo "Error: Failed to download APKEditor"
    exit 1
  fi
fi

# Parse command line options
no_revanced=false
while getopts "n-:" opt; do
  case $opt in
  n)
    no_revanced=true
    ;;
  -)
    case "${OPTARG}" in
    no-revanced)
      no_revanced=true
      ;;
    *)
      echo "Invalid option: --${OPTARG}" >&2
      exit 1
      ;;
    esac
    ;;
  \?)
    echo "Invalid option: -$OPTARG" >&2
    exit 1
    ;;
  esac
done
shift $((OPTIND - 1))

# Check if at least 2 arguments are provided
if [ "$#" -lt 2 ]; then
  echo "Usage: $0 [-n|--no-revanced] <input_file> <suffix1> [suffix2 ...]"
  echo "Options:"
  echo "  -n, --no-revanced    Disable ReVanced support"
  exit 1
fi

# ReVanced setup
REVANCED_DIR="revanced"
if [ "$no_revanced" = false ]; then
  mkdir -p "$REVANCED_DIR"
  cd "$REVANCED_DIR"

  # Function to get latest version from GitHub release
  get_latest_version() {
    curl -s "https://api.github.com/repos/$1/releases/latest" | grep -o '"tag_name": *"[^"]*"' | cut -d'"' -f4
  }

  # Function to get current version from file
  get_current_version() {
    if [ -f "$1" ]; then
      java -jar "$1" --version 2>/dev/null || echo "0"
    else
      echo "0"
    fi
  }

  # Check and update CLI
  echo "Checking ReVanced CLI version..."
  LATEST_CLI_VERSION=$(get_latest_version "revanced/revanced-cli")
  CURRENT_CLI_VERSION=$(get_current_version "revanced-cli.jar")

  if [ "$LATEST_CLI_VERSION" != "$CURRENT_CLI_VERSION" ]; then
    echo "Updating CLI from $CURRENT_CLI_VERSION to $LATEST_CLI_VERSION..."
    CLI_URL=$(curl -s https://api.github.com/repos/revanced/revanced-cli/releases/latest | grep -o 'https://.*all\.jar"' | sed 's/"$//')
    curl -L -o revanced-cli.jar "$CLI_URL"
  else
    echo "ReVanced CLI is up to date ($CURRENT_CLI_VERSION)"
  fi

  # Check and update Patches
  echo "Checking ReVanced Patches version..."
  LATEST_PATCHES_VERSION=$(get_latest_version "revanced/revanced-patches")
  CURRENT_PATCHES_VERSION=$(get_current_version "revanced-patches.rvp")

  if [ "$LATEST_PATCHES_VERSION" != "$CURRENT_PATCHES_VERSION" ]; then
    echo "Updating Patches from $CURRENT_PATCHES_VERSION to $LATEST_PATCHES_VERSION..."
    PATCHES_URL=$(curl -s https://api.github.com/repos/revanced/revanced-patches/releases/latest | grep -o 'https://.*\.rvp"' | sed 's/"$//')
    curl -L -o revanced-patches.rvp "$PATCHES_URL"
  else
    echo "ReVanced Patches are up to date ($CURRENT_PATCHES_VERSION)"
  fi

  # Check and update Integrations
  echo "Checking ReVanced Integrations version..."
  LATEST_INTEGRATIONS_VERSION=$(get_latest_version "revanced/revanced-integrations")
  CURRENT_INTEGRATIONS_VERSION=$(get_current_version "revanced-integrations.apk")

  if [ "$LATEST_INTEGRATIONS_VERSION" != "$CURRENT_INTEGRATIONS_VERSION" ]; then
    echo "Updating Integrations from $CURRENT_INTEGRATIONS_VERSION to $LATEST_INTEGRATIONS_VERSION..."
    INTEGRATIONS_URL=$(curl -s https://api.github.com/repos/revanced/revanced-integrations/releases/latest | grep -o 'https://.*\.apk"' | sed 's/"$//')
    curl -L -o revanced-integrations.apk "$INTEGRATIONS_URL"
  else
    echo "ReVanced Integrations are up to date ($CURRENT_INTEGRATIONS_VERSION)"
  fi

  cd ..
fi

# Get input file and remove it from arguments
input_file="$1"
shift

# Get base name without extension
base_name="${input_file%.*}"
extension="${input_file##*.}"
decompile_dir="output/${base_name}_decompile_xml"

# Only perform conversion and decompilation if the directory doesn't exist
if [ ! -d "$decompile_dir" ]; then
  # If file is APKM, convert to APK first
  if [ "$extension" = "apkm" ]; then
    echo "Converting APKM to APK..."
    java -jar APKEditor.jar m -i "$input_file" -o "output/${base_name}.apk"
    input_file="output/${base_name}.apk"
  fi

  # After getting input file but before processing
  echo "Checking APK info..."
  java -jar APKEditor.jar info -i "$input_file"

  # Decompile the APK (using -dex to skip smali and keep raw dex)
  echo "Decompiling APK..."
  java -jar APKEditor.jar d -dex -i "$input_file" -o "$decompile_dir"
else
  echo "Using existing decompiled files in ${decompile_dir}"
fi

# Check if AndroidManifest.xml exists
manifest_file="${decompile_dir}/AndroidManifest.xml"
if [ ! -f "$manifest_file" ]; then
  echo "Error: AndroidManifest.xml not found in decompiled files"
  exit 1
fi

# Get original package name
original_package=$(grep 'package="' "$manifest_file" | sed 's/.*package="\([^"]*\)".*/\1/')
if [ -z "$original_package" ]; then
  echo "Error: Could not find package name in AndroidManifest.xml"
  exit 1
fi

# Escape dots in package name for sed
escaped_package=$(echo "$original_package" | sed 's/\./\\./g')

# Check if debug.keystore exists, if not create it
if [ ! -f "output/debug.keystore" ]; then
  echo "Creating debug keystore..."
  keytool -genkey -v -keystore output/debug.keystore \
    -alias androiddebugkey \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US" \
    -storepass android -keypass android
fi

# Process each package name
for suffix in "$@"; do
  if [[ "$suffix" == *"."* ]]; then
    new_package="$suffix"
  else
    new_package="${original_package}.${suffix}"
  fi
  escaped_package=$(echo "$original_package" | sed 's/\./\\./g')
  escaped_new_package=$(echo "$new_package" | sed 's/\./\\./g')
  echo "Creating APK for package: $new_package"

  # Create backup of original manifest
  cp "$manifest_file" "${manifest_file}.original"

  # Change package name in manifest
  sedi "s/package=\"${escaped_package}\"/package=\"${escaped_new_package}\"/" "$manifest_file"

  # Update app label in manifest to PurpleSX2
  app_label="PurpleSX2"
  sedi "s/android:label=\"AetherSX2\"/android:label=\"${app_label}\"/g" "$manifest_file"
  sedi "s/android:label=\"NetherSX2\"/android:label=\"${app_label}\"/g" "$manifest_file"

  # Remove permission declarations but keep uses-permission
  sedi "/<permission /d" "$manifest_file"

  # Update custom permission references to use original package's permissions
  sedi "s/android:name=\"${escaped_new_package}\.\([^\"]*\)\"/android:name=\"${escaped_package}.\1\"/g" "$manifest_file"
  sedi "s/android:permission=\"${escaped_new_package}\.\([^\"]*\)\"/android:permission=\"${escaped_package}.\1\"/g" "$manifest_file"

  # Update all provider authorities to be unique
  sedi "s/android:authorities=\"[^\"]*${escaped_package}[^\"]*\"/android:authorities=\"${escaped_new_package}\"/g" "$manifest_file"

  # Preserve original package name for application and component class paths
  sedi "s/android:name=\"${escaped_new_package}\./android:name=\"${escaped_package}./g" "$manifest_file"

  # Update app name in all strings.xml files
  find "$decompile_dir" -name "strings.xml" | while read -r sfile; do
    cp "$sfile" "${sfile}.original"
    sedi "s/<string name=\"app_name\">[^<]*<\/string>/<string name=\"app_name\">${app_label}<\/string>/g" "$sfile"
  done

  # Apply 0.25x resolution scale multiplier patch if present
  if [ -f "../patches/patch_scale_multiplier.py" ]; then
    echo "Applying 0.25x resolution scale patch..."
    python3 -c "
import sys
from pathlib import Path
sys.path.insert(0, '..')
from patches.patch_scale_multiplier import patch_arrays
for res_dir in Path('$decompile_dir').rglob('res'):
    if res_dir.is_dir():
        patch_arrays(res_dir)
" 2>/dev/null || true
  fi

  # Bypass native package-segment check in libemucore.so so cloned package works
  for so in "$decompile_dir"/lib/*/libemucore.so "$decompile_dir"/root/lib/*/libemucore.so; do
    if [ -f "$so" ]; then
      echo "Patching package check in $so..."
      python3 -c '
import sys
with open(sys.argv[1], "r+b") as f:
    data = f.read()
    patches = {0x83A3EC: bytes.fromhex("ac000014"), 0x83A430: bytes.fromhex("9b000014"), 0x83A790: bytes.fromhex("51000014"), 0x83A7D4: bytes.fromhex("40000014")}
    if len(data) > 0x83A7D4:
        for off, val in patches.items():
            f.seek(off)
            f.write(val)
' "$so" 2>/dev/null || true
    fi
  done

  # Build new APK with specified output name
  java -jar APKEditor.jar b -framework-version 34 -i "$decompile_dir" -o "output/${base_name}_${suffix}_unsigned.apk"

  # Zipalign the APK
  echo "Zipaligning APK..."
  zipalign -v -p 4 "output/${base_name}_${suffix}_unsigned.apk" "output/${base_name}_${suffix}_aligned.apk"

  # Check if package is supported by ReVanced and apply patches if supported
  final_apk="output/${base_name}_${suffix}_aligned.apk"
  if [ "$no_revanced" = false ] && [ -f "revanced/revanced-cli.jar" ]; then
    echo "Checking if package $original_package is supported by ReVanced..."
    # List available patches and filter for app-specific ones
    available_patches=$(java -jar "revanced/revanced-cli.jar" list-patches -p "revanced/revanced-patches.rvp" -f "$original_package")
    if [ ! -z "$available_patches" ]; then
      echo "Found app-specific patches for $original_package:"
      echo "$available_patches"
      echo "Applying patches..."

      # Extract patch names and create enable arguments
      declare -a enable_args=()
      echo "Will apply the following patches:"
      current_name=""
      is_enabled=false

      while IFS= read -r line; do
        if [[ $line =~ ^[[:space:]]*Name:[[:space:]]*(.*) ]]; then
          current_name="${BASH_REMATCH[1]}"
          is_enabled=false
        elif [[ $line =~ ^[[:space:]]*Enabled:[[:space:]]*true ]]; then
          is_enabled=true
          if [ ! -z "$current_name" ]; then
            echo "  - $current_name"
            enable_args+=("--enable" "$current_name")
          fi
        fi
      done <<<"$available_patches"

      if [ ${#enable_args[@]} -eq 0 ]; then
        echo "No enabled patches found for $original_package"
        echo "Skipping ReVanced patching"
      else
        # Create patched version with all app-specific patches
        echo "Running patch command..."
        java -jar "revanced/revanced-cli.jar" \
          patch \
          -p "revanced/revanced-patches.rvp" \
          -o "output/${base_name}_${suffix}_revanced.apk" \
          --exclusive \
          "${enable_args[@]}" \
          "${final_apk}"

        if [ -f "output/${base_name}_${suffix}_revanced.apk" ]; then
          echo "Successfully patched APK with ReVanced"
          final_apk="output/${base_name}_${suffix}_revanced.apk"
        else
          echo "Failed to patch APK with ReVanced, will use unpatched version"
        fi
      fi
    else
      echo "No app-specific patches found for $original_package"
    fi
  fi

  # Sign the final APK (either patched or unpatched)
  echo "Signing final APK..."
  apksigner sign --ks output/debug.keystore \
    --ks-key-alias androiddebugkey \
    --ks-pass pass:android \
    --key-pass pass:android \
    --v1-signing-enabled true \
    --v2-signing-enabled true \
    --v3-signing-enabled true \
    --v4-signing-enabled true \
    --out "output/${base_name}_${suffix}_signed.apk" \
    "$final_apk"

  # Clean up intermediate files
  rm -f "output/${base_name}_${suffix}_unsigned.apk" "output/${base_name}_${suffix}_aligned.apk" \
    "output/${base_name}_${suffix}_revanced.apk" "$final_apk"
  # Clean up ReVanced temporary directories
  rm -rf "output/${base_name}_${suffix}_revanced-temporary-files"

  # Verify the signature
  echo "Verifying APK signature..."
  apksigner verify --verbose "output/${base_name}_${suffix}_signed.apk"

  # Restore original manifest
  mv "${manifest_file}.original" "$manifest_file"

  # Restore original strings.xml
  find "$decompile_dir" -name "strings.xml.original" | while read -r orig; do
    mv "$orig" "${orig%.original}"
  done
done

echo "All APKs created successfully"
