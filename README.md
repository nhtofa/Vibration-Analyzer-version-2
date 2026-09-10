# Vibration Analyzer

Vibration signal analysis for CSV and Excel measurements. The repository contains the original Streamlit application and portable Android/Windows builds that run the same offline JavaScript analysis core.

## Analysis features

- Time-domain waveform and statistical metrics
- Frequency-domain FFT spectrum with configurable window
- Hilbert-transform envelope analysis with band-pass filtering
- Single-channel phase analysis
- Reference-channel phase comparison and time correlation
- Time-frequency spectrogram with dominant-frequency tracking

## Streamlit version

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
streamlit run vibration_analizer-2.py
```

Upload a CSV or Excel file containing a numeric time column and one or more vibration-signal columns. The Streamlit version supports the full original workflow and can compare a measurable signal with a reference signal from the same file or a separate file.

## Portable app

The `web/` application is offline-first and processes CSV/XLSX files locally. No measurement data is uploaded. It is wrapped for Android with Capacitor and for Windows with a small Go launcher that opens the embedded app in an Edge app window.

### Build the Android app

Requirements: Node.js, Android SDK, and JDK 17. The checked-in project uses Capacitor 6.2.1 and compiles against Android SDK 35.

```bash
cd native
npm install
printf 'sdk.dir=/usr/lib/android-sdk\n' > android/local.properties
npx cap sync android
cd android
./gradlew assembleDebug
```

The debug APK is written to `native/android/app/build/outputs/apk/debug/app-debug.apk`.

For a signed release build, keep the keystore outside the repository and pass its properties to Gradle:

```bash
cd native/android
./gradlew assembleRelease \
  -PreleaseStoreFile=/absolute/path/vibration-analyzer-release.jks \
  -PreleaseStorePassword='YOUR_STORE_PASSWORD' \
  -PreleaseKeyAlias=vibration-analyzer \
  -PreleaseKeyPassword='YOUR_KEY_PASSWORD'
```

Verify the signed artifact:

```bash
$ANDROID_HOME/build-tools/34.0.0/apksigner verify --verbose --print-certs \
  app/build/outputs/apk/release/app-release.apk
```

### Build the Windows app

Requirements: Go 1.23+ (cross-compilation from Linux is supported).

```bash
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 \
  go build -trimpath -ldflags='-s -w -H windowsgui' \
  -o dist/Vibration-Analyzer-v2-windows-amd64.exe .
```

The launcher embeds `web/`, starts a loopback HTTP server, opens Microsoft Edge in app mode, and shuts its server down when the app window closes. It falls back to the default browser if Edge cannot be found.

## Tests

```bash
node tests/web_app.test.js
node --check web/app.js
go test ./...
```

The JavaScript test suite covers CSV parsing, sample-rate detection, statistics, FFT peak detection, envelope processing, reference phase, correlation, and spectrogram output. Go tests verify that all web assets are embedded in the Windows binary.

## Release artifacts

The signed Android APK and Windows executable are published on the GitHub Releases page for this repository. The signing keystore is intentionally not committed or published; keep it safe if future Android updates must preserve the same signing identity.
