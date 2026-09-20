:: --Manifest Cleanup--
lib\xml ed -L -d "manifest/uses-permission[@android:name='android.permission.ACCESS_NETWORK_STATE' or @android:name='com.google.android.gms.permission.AD_ID' or @android:name='android.permission.WAKE_LOCK' or @android:name='android.permission.FOREGROUND_SERVICE']" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/queries" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/service" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/receiver" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/meta-data[@android:name='com.google.android.gms.ads.APPLICATION_ID' or @android:name='com.google.android.gms.version']" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/provider/meta-data[@android:name='androidx.work.WorkManagerInitializer']" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/activity[@android:name='com.google.android.gms.ads.AdActivity' or @android:name='com.google.android.gms.version' or @android:name='com.google.android.gms.common.api.GoogleApiActivity' or @android:name='com.google.android.gms.ads.OutOfContextTestingActivity']" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/provider[@android:name='com.google.android.gms.ads.MobileAdsInitProvider']" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/activity/@android:preferMinimalPostProcessing" "4248\AndroidManifest.xml"
lib\xml ed -L -d "manifest/application/@android:extractNativeLibs" "4248\AndroidManifest.xml"

lib\xml ed -L -u "manifest/application/@android:label" -v "NetherSX2" "4248\AndroidManifest.xml"
lib\xml ed -L -u "manifest/application/activity[@android:label='AetherSX2']/@android:label" -v "NetherSX2" "4248\AndroidManifest.xml"
:: --End Manifest Cleanup--

:: --Main Activity Layout Cleanup--
lib\xml ed -L -d "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/RelativeLayout/FrameLayout/@android:layout_above" "4248\res\layout\activity_main.xml"
lib\xml ed -L -a "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/RelativeLayout/FrameLayout" -t attr -n "android:layout_alignParentBottom" -v "true" "4248\res\layout\activity_main.xml"
lib\xml ed -L -d "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/RelativeLayout/com.google.android.gms.ads.AdView" "4248\res\layout\activity_main.xml"
lib\xml ed -L -u "androidx.drawerlayout.widget.DrawerLayout/androidx.coordinatorlayout.widget.CoordinatorLayout/com.google.android.material.floatingactionbutton.FloatingActionButton/@android:layout_marginBottom" -v "16.0dip" "4248\res\layout\activity_main.xml"
:: --End Main Activity Layout Cleanup--

:: --Scale Multiplier--
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Native')]/item[1]" -t elem -n "item" -v "0.25x Native" "4248\res\values\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_values'][not(item='0.250000')]/item[1]" -t elem -n "item" -v "0.250000" "4248\res\values\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x الدقة')]/item[1]" -t elem -n "item" -v "0.25x الدقة" "4248\res\values-ar-rSA\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x کوالێتی گرافیک')]/item[1]" -t elem -n "item" -v "0.25x کوالێتی گرافیک" "4248\res\values-ckb-rIR\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Nativo')]/item[1]" -t elem -n "item" -v "0.25x Nativo" "4248\res\values-es-rES\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Neytib')]/item[1]" -t elem -n "item" -v "0.25x Neytib" "4248\res\values-fil-rPH\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Natif')]/item[1]" -t elem -n "item" -v "0.25x Natif" "4248\res\values-fr-rFR\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='Natív 0.25x')]/item[1]" -t elem -n "item" -v "Natív 0.25x" "4248\res\values-hu-rHU\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Resolusi')]/item[1]" -t elem -n "item" -v "0.25x Resolusi" "4248\res\values-in-rID\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Nativo')]/item[1]" -t elem -n "item" -v "0.25x Nativo" "4248\res\values-it-rIT\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x')]/item[1]" -t elem -n "item" -v "0.25x" "4248\res\values-ko-rKR\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Origineel')]/item[1]" -t elem -n "item" -v "0.25x Origineel" "4248\res\values-nl-rNL\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0,25x Nativa')]/item[1]" -t elem -n "item" -v "0,25x Nativa" "4248\res\values-pt-rBR\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x Nativo')]/item[1]" -t elem -n "item" -v "0.25x Nativo" "4248\res\values-pt-rPT\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x нативное')]/item[1]" -t elem -n "item" -v "0.25x нативное" "4248\res\values-ru-rRU\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0,25x natívne')]/item[1]" -t elem -n "item" -v "0,25x natívne" "4248\res\values-sk-rSK\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x จากความละเอียดดั้งเดิม (~120p)')]/item[1]" -t elem -n "item" -v "0.25x จากความละเอียดดั้งเดิม (~120p)" "4248\res\values-th-rTH\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25倍原生')]/item[1]" -t elem -n "item" -v "0.25倍原生" "4248\res\values-zh-rCN\arrays.xml"
lib\xml ed -L -i "resources/string-array[@name='gs_upscale_entries'][not(item='0.25x 原生')]/item[1]" -t elem -n "item" -v "0.25x 原生" "4248\res\values-zh-rTW\arrays.xml"
:: --End Scale Multiplier--

:: --Patch Native Library--
:: Patch signature checks
lib\hexalter 4248\lib\arm64-v8a\libemucore.so 0x838560=0x66,0x00,0x00,0x14 0x83B324=0x62,0x00,0x00,0x14
:: Patch BIOS type check
lib\hexalter 4248\lib\arm64-v8a\libemucore.so 0x829248=0x35,0x00,0x80,0x52
:: Scarface (SLUS_211.11) never got its hash sent to RA due to a bad zero-length check
lib\hexalter 4248\lib\arm64-v8a\libemucore.so 0x81b264=0x04,0x00,0x00,0x14

:: --Patch DEX--
:: Disable ads
lib\hexalter 4248\classes.dex 0x222264=0x0e,0x00 0x3C5B70=0x0e,0x00
:: Restore Launcher support
lib\hexalter 4248\classes.dex 0x3BDAA4=0x12,0x11 0x3BDAAA=0x04 0x3BDAAD=0x05 0x3BDAB2=0x15
lib\hexalter 4248\classes.dex 0x3BDAA6=0x6e,0x10,0x93,0x02,0x02,0x00,0x0c,0x03,0x71,0x20,0xb3,0x90,0x13,0x00
lib\hexalter 4248\classes.dex 0x3BDAB4=0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
:: Fix checksum
lib\hexalter 4248\classes.dex 0x8=0xdd,0xa2,0x21,0x3a
:: --End Patch Native Library--