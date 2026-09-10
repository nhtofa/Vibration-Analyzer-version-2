# Vibration Analyzer

Streamlit-based vibration signal analysis tool for CSV and Excel data.

## Features

- Time-domain waveform and statistical metrics
- Frequency-domain FFT spectrum
- Hilbert-transform envelope analysis
- Single-channel phase analysis
- Reference-channel phase analysis with cross-phase and coherence
- Configurable measurable and reference signals/windows
- Time-frequency spectrogram analysis

## Run locally

```bash
pip install -r requirements.txt
streamlit run vibration_analizer-2.py
```

Upload a CSV or Excel file containing a time column and one or more vibration-signal columns. Under **Phase Analysis**, the measurable signal can be compared with a reference signal from the same file or a separate file.
