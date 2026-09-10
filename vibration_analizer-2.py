import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from scipy.fft import rfft, rfftfreq
from scipy.signal import butter, sosfiltfilt, get_window, hilbert, spectrogram, coherence
from scipy.stats import skew, kurtosis

st.set_page_config(page_title='Vibration Analyzer version-2', page_icon= "📈", layout= 'wide')
st.title('Welcome to Vibration Analizer', text_alignment='center')
st.subheader('Upload your vibration data and perform\n, Waveform analysis, Frequency domain Analysis,'
             'Envelope Analysis, Phase Analysis, Spectrogram Analysis', text_alignment='center')

def load_data(uploaded_file):
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    elif uploaded_file.name.endswith('.xlsx'):
        df = pd.read_excel(uploaded_file)
    else:
        st.error('Please upload CSV or excel file')
        return None
    return df

def select_columns(df):
    st.sidebar.subheader('Data Selection')
    columns = df.columns.tolist()
    time_column = st.sidebar.selectbox("Select Time Column", columns)
    vibration_columns = [column for column in columns if column != time_column]
    vibration = st.sidebar.selectbox('Select Vibration Column', vibration_columns)
    return time_column, vibration

def window_type(vibration_column):
    window_name = st.sidebar.selectbox('Select Window',
                                       ['No window', 'Hann', 'Hamming', 'Blackman', 'Flattop'])
    if window_name == 'No window':
        window = np.ones(len(vibration_column))
    else:
        window = get_window(window_name.lower(), len(vibration_column))
    return window

def signal_preparation(df,  time_column, vibration ):
    time = pd.to_numeric(df[time_column], errors='coerce')
    vibration = pd.to_numeric(df[vibration], errors= 'coerce')
    valid = time.notna() & vibration.notna()
    time = time[valid].to_numpy()
    vibration = vibration[valid].to_numpy()
    vibration_detrended = vibration - np.mean(vibration)
    return time,vibration, vibration_detrended

def sampling_frequency(time):
    dt = np.median(np.diff(time))
    fs = 1 / dt
    return dt, fs

def time_domain_analysis(time, vibration_column):
    st.header('Time Domain Analysis')

    peak = np.max(np.abs(vibration_column))
    minimum = np.min(vibration_column)
    rms = np.sqrt(np.mean(vibration_column ** 2))
    peak_to_peak = np.ptp(vibration_column)
    crest_factor = peak / rms if rms != 0 else 0
    skewness = skew(vibration_column)
    kurt = kurtosis(vibration_column)

    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)

    col1.metric('Peak',f'{peak:.2f}')
    col2.metric('Minimum', f'{minimum:.2f}')
    col3.metric('Rms', f'{rms:.2f}')
    col4.metric('Peak to Peak', f'{peak_to_peak:.2f}')
    col5.metric('Crest Factor', f'{crest_factor:.2f}')
    col6.metric('Skewness', f'{skewness:.2f}')
    col7.metric('Kurtosis', f'{kurt:.2f}')

    fig, ax = plt.subplots(figsize = (12, 5))
    ax.plot(time, vibration_column)
    ax.set_xlabel('Time')
    ax.set_ylabel('Vibration amplitude')
    ax.set_title('Time Domain Waveform')
    st.pyplot(fig)

def frequency_domain_analysis(vibration_detrended, window, dt, fs):
    st.header('Frequency Domain Analysis')
    fmax = st.slider('Select frequency range',
                     min_value=0.0, max_value=float(fs/2), value=min(50.0, float(fs/2)))
    windowed_signal = vibration_detrended * window
    frequency_resolution = fs / len(windowed_signal)
    fft_values = rfft(windowed_signal)
    frequency = rfftfreq(len(windowed_signal), dt)
    magnitude = (2 / len(windowed_signal)) * np.abs(fft_values)
    magnitude = magnitude / np.mean(window)
    mask = frequency <=fmax
    mask_frequency = frequency[mask]
    mask_amplitude = magnitude[mask]
    if len(mask_amplitude) > 1:
        peak_index = np.argmax(mask_amplitude[1:])+1
        dominant_frequency = mask_frequency[peak_index]
        dominant_amplitude = mask_amplitude[peak_index]

    else:
        dominant_frequency = 0
        dominant_amplitude = 0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Sampling Frequency",f"{fs:.2f} Hz")
    col2.metric("Dominant Frequency",f"{dominant_frequency:.2f} Hz")
    col3.metric("Dominant Amplitude",f"{dominant_amplitude:.4f}")
    col4.metric("Frequency Resolution", f"{frequency_resolution:.2f}")

    fig, ax = plt.subplots(figsize = (12,6))
    ax.plot(frequency[mask], magnitude[mask])
    ax.set_xlabel('Frequency')
    ax.set_ylabel('Amplitude')
    ax.set_title('Frequency Spectrum')
    ax.grid(True)
    st.pyplot(fig)

def envelope_analysis(time, vibration, fs, window):
    st.header('Envelope Analysis')
    st.sidebar.subheader('Envelope Filter Setting')

    low_cut = st.sidebar.number_input('Low cut-off frequency (HZ)', min_value=1.0,
                                     max_value=float((fs/2)-1), value=min(60.0, float((fs/2)-1)))
    high_cut = st.sidebar.number_input("High Cut-off Frequency (Hz)", min_value=10.0,
                                       max_value=float((fs/2)-1), value=min(100.0, float((fs/2)-1)))
    filter_order = st.sidebar.slider('Select filter order', min_value=2, max_value=16, value=4)

    nyquist_frequency = fs / 2
    if high_cut >= nyquist_frequency:
        st.error('High cut-off frequency must be lower than Nyquist frequency')
        return
    if low_cut >= high_cut:
        st.error('Low cut-off frequency must be lower than high cut-off frequency')
        return

    sos = butter(filter_order, [low_cut, high_cut], btype='bandpass', analog=False, fs=fs, output='sos')
    filtered_signal = sosfiltfilt(sos, vibration)
    analytic_signal = hilbert(filtered_signal)
    envelope = np.abs(analytic_signal)
    envelope_ac = envelope - np.mean(envelope)
    windowed_envelope = envelope_ac * window
    envelope_fft = rfft(windowed_envelope)
    envelope_frequency = rfftfreq(len(windowed_envelope), 1/fs)
    envelope_magnitude =(2 / np.sum(window)) * np.abs(envelope_fft)

    fmax = st.slider('Select frequency', min_value=0.0, max_value=float(nyquist_frequency), value=200.00)
    mask = envelope_frequency <= fmax
    mask_frequency = envelope_frequency[mask]
    mask_amplitude = envelope_magnitude[mask]

    if len(mask_amplitude) > 1:
        peak_index = np.argmax(mask_amplitude[1:]) + 1
        dominant_envelope_magnitude = mask_amplitude[peak_index]
        dominant_envelope_frequency = mask_frequency[peak_index]
    else:
        dominant_envelope_magnitude = 0
        dominant_envelope_frequency = 0

    st.subheader("Band-pass Filtered Signal")
    fig1, ax1 = plt.subplots(figsize=(12, 4))
    ax1.plot(time, filtered_signal)
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("Amplitude")
    ax1.set_title(f"Band-pass Filter: {low_cut:.0f} - {high_cut:.0f} Hz")
    ax1.grid(True)
    st.pyplot(fig1)

    st.subheader("Extracted Envelope")
    fig2, ax2 = plt.subplots(figsize=(12, 4))
    ax2.plot(time, envelope)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Envelope Amplitude")
    ax2.set_title("Hilbert Envelope")
    ax2.grid(True)
    st.pyplot(fig2)

    st.subheader("Envelope Spectrum")
    fig3, ax3 = plt.subplots(figsize=(12, 6))
    ax3.plot(envelope_frequency[mask], envelope_magnitude[mask])
    ax3.set_xlabel("Frequency (Hz)")
    ax3.set_ylabel("Amplitude")
    ax3.set_title("Envelope Spectrum")
    ax3.grid(True)
    st.pyplot(fig3)

    col1, col2, col3 = st.columns(3)
    col1.metric("Filter Range",f"{low_cut:.0f} - {high_cut:.0f} Hz")
    col2.metric("Dominant Envelope Frequency",f"{dominant_envelope_frequency:.2f} Hz")
    col3.metric("Dominant Envelope Magnitude", f"{dominant_envelope_magnitude:.4f}")

def get_window_by_name(window_name, length):
    if window_name == 'No window':
        return np.ones(length)
    return get_window(window_name.lower(), length)

def prepare_reference_signal(df, time_column, vibration, main_length):
    st.sidebar.subheader('Reference Signal Setting')
    use_reference = st.sidebar.checkbox('Use Reference Signal', value=False)
    if not use_reference:
        return None

    reference_source = st.sidebar.radio('Reference source', ['Same file', 'Separate file'])
    reference_window_name = st.sidebar.selectbox('Select Reference Window',
                                                 ['No window', 'Hann', 'Hamming', 'Blackman', 'Flattop'],
                                                 index=1)
    if reference_source == 'Same file':
        columns = df.columns.tolist()
        reference_columns = [column for column in columns if column not in (time_column, vibration)]
        if not reference_columns:
            st.error('No extra column available for reference signal in this file.')
            return None
        reference_name = st.sidebar.selectbox('Select Reference Column', reference_columns)
        reference = pd.to_numeric(df[reference_name], errors='coerce')
        reference = reference[reference.notna()].to_numpy()
    else:
        reference_file = st.sidebar.file_uploader('Upload Reference data', type=['csv', 'xlsx'],
                                                  key='reference_file')
        if reference_file is None:
            st.info('Upload a reference signal file to enable reference phase analysis.')
            return None
        reference_df = load_data(reference_file)
        if reference_df is None:
            return None
        reference_columns = reference_df.columns.tolist()
        reference_name = st.sidebar.selectbox('Select Reference Column', reference_columns)
        reference = pd.to_numeric(reference_df[reference_name], errors='coerce')
        reference = reference[reference.notna()].to_numpy()

    if len(reference) < 8:
        st.error('Reference signal is too short.')
        return None
    if len(reference) < main_length:
        st.warning(f'Reference signal shorter than vibration signal. Truncated to {len(reference)} samples.')

    reference_detrended = reference - np.mean(reference)
    reference_window = get_window_by_name(reference_window_name, len(reference_detrended))
    return reference_detrended, reference_window, reference_name

def phase_analysis(time, vibration_detrended, window, dt, fs, df, time_column, vibration_name):
    st.header('Phase Analysis')
    st.sidebar.subheader('Phase Analysis Setting')

    fmax = st.slider('Select frequency range for phase',
                     min_value=0.0, max_value=float(fs/2), value=min(50.0, float(fs/2)))
    threshold_percent = st.sidebar.slider('Magnitude threshold (% of dominant peak)',
                                          min_value=0, max_value=100, value=10)

    reference = prepare_reference_signal(df, time_column, vibration_name, len(vibration_detrended))

    if reference is not None:
        reference_detrended, reference_window, reference_name = reference

        # measurable (main) signal options
        st.sidebar.subheader('Measurable Signal Setting')
        measurable_name = vibration_name
        if df is not None:
            measurable_columns = [column for column in df.columns.tolist()
                                  if column != time_column and column != reference_name]
            if measurable_columns:
                measurable_name = st.sidebar.selectbox('Select Measurable Signal', measurable_columns,
                                                       index=measurable_columns.index(vibration_name)
                                                       if vibration_name in measurable_columns else 0)
                measurable = pd.to_numeric(df[measurable_name], errors='coerce')
                measurable = measurable[measurable.notna()].to_numpy()
                measurable_detrended = measurable - np.mean(measurable)
            else:
                measurable_detrended = vibration_detrended
        else:
            measurable_detrended = vibration_detrended
        measurable_window_name = st.sidebar.selectbox('Select Measurable Window',
                                                      ['No window', 'Hann', 'Hamming', 'Blackman', 'Flattop'],
                                                      index=1)
        measurable_window = get_window_by_name(measurable_window_name, len(measurable_detrended))

        n = min(len(measurable_detrended), len(reference_detrended))
        main_segment = measurable_detrended[:n] * measurable_window[:n]
        reference_segment = reference_detrended[:n] * reference_window[:n]
        time_segment = time[:n]

        fft_main = rfft(main_segment)
        fft_reference = rfft(reference_segment)
        frequency = rfftfreq(n, dt)
        frequency_resolution = fs / n
        magnitude_main = (2 / n) * np.abs(fft_main) / np.mean(measurable_window[:n])
        magnitude_reference = (2 / n) * np.abs(fft_reference) / np.mean(reference_window[:n])

        # cross-spectrum: phase of main signal relative to reference
        cross_spectrum = fft_main * np.conj(fft_reference)
        cross_phase = np.degrees(np.angle(cross_spectrum))

        mask = frequency <= fmax
        mask_frequency = frequency[mask]
        mask_magnitude_main = magnitude_main[mask]
        mask_magnitude_reference = magnitude_reference[mask]
        mask_cross_phase = cross_phase[mask]

        if len(mask_magnitude_main) > 1:
            peak_index = np.argmax(mask_magnitude_main[1:]) + 1
            dominant_frequency = mask_frequency[peak_index]
            phase_difference = mask_cross_phase[peak_index]
        else:
            dominant_frequency = 0
            phase_difference = 0

        # significance: bin must be strong in BOTH channels
        peak_main = np.max(magnitude_main) if np.max(magnitude_main) > 0 else 1
        peak_reference = np.max(magnitude_reference) if np.max(magnitude_reference) > 0 else 1
        threshold = threshold_percent / 100
        significant = ((mask_magnitude_main / peak_main) >= threshold) & \
                      ((mask_magnitude_reference / peak_reference) >= threshold)

        # coherence between the two channels
        nperseg = min(1024, n // 4) if n >= 8 else n
        coherence_frequency, coherence_values = coherence(measurable_detrended[:n],
                                                          reference_detrended[:n],
                                                          fs=fs, nperseg=nperseg)
        coherence_mask = coherence_frequency <= fmax
        if dominant_frequency > 0:
            coherence_at_dominant = coherence_values[np.argmin(np.abs(coherence_frequency - dominant_frequency))]
        else:
            coherence_at_dominant = 0

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Measurable vs Reference", f"{measurable_name} / {reference_name}")
        col2.metric("Dominant Frequency", f"{dominant_frequency:.2f} Hz")
        col3.metric("Phase Difference at Dominant Freq", f"{phase_difference:.2f} °")
        col4.metric("Coherence at Dominant Freq", f"{coherence_at_dominant:.2f}")

        st.subheader("Measurable vs Reference Waveform")
        fig1, ax1 = plt.subplots(figsize=(12, 4))
        ax1.plot(time_segment, main_segment, label=f'Measurable: {measurable_name}')
        ax1.plot(time_segment, reference_segment, label=f'Reference: {reference_name}', alpha=0.8)
        ax1.set_xlabel('Time (s)')
        ax1.set_ylabel('Amplitude')
        ax1.set_title('Measurable vs Reference (Windowed)')
        ax1.grid(True)
        ax1.legend()
        st.pyplot(fig1)

        st.subheader("Amplitude Spectra of Both Channels")
        fig2, ax2 = plt.subplots(figsize=(12, 5))
        ax2.plot(mask_frequency, mask_magnitude_main, label=f'Measurable: {measurable_name}')
        ax2.plot(mask_frequency, mask_magnitude_reference, label=f'Reference: {reference_name}', alpha=0.8)
        ax2.set_xlabel('Frequency (Hz)')
        ax2.set_ylabel('Amplitude')
        ax2.set_title('Amplitude Spectra')
        ax2.grid(True)
        ax2.legend()
        st.pyplot(fig2)

        st.subheader("Cross-Phase Spectrum (Measurable relative to Reference)")
        fig3, ax3 = plt.subplots(figsize=(12, 6))
        ax3.plot(mask_frequency, mask_cross_phase, color='lightgray', label='All bins (noise included)')
        ax3.scatter(mask_frequency[significant], mask_cross_phase[significant], color='tab:blue', s=12,
                    label=f'Significant bins (>= {threshold_percent}% of peak in both channels)')
        ax3.axhline(0, color='black', linewidth=0.5)
        ax3.set_xlabel('Frequency (Hz)')
        ax3.set_ylabel('Phase Difference (degrees)')
        ax3.set_title('Cross-Phase Spectrum')
        ax3.set_ylim(-180, 180)
        ax3.grid(True)
        ax3.legend()
        st.pyplot(fig3)

        st.subheader("Coherence between Measurable and Reference")
        fig4, ax4 = plt.subplots(figsize=(12, 4))
        ax4.plot(coherence_frequency[coherence_mask], coherence_values[coherence_mask])
        ax4.set_xlabel('Frequency (Hz)')
        ax4.set_ylabel('Coherence')
        ax4.set_title('Magnitude-Squared Coherence')
        ax4.set_ylim(0, 1.05)
        ax4.grid(True)
        st.pyplot(fig4)
        return

    windowed_signal = vibration_detrended * window
    frequency_resolution = fs / len(windowed_signal)
    fft_values = rfft(windowed_signal)
    frequency = rfftfreq(len(windowed_signal), dt)
    magnitude = (2 / len(windowed_signal)) * np.abs(fft_values)
    magnitude = magnitude / np.mean(window)
    phase = np.degrees(np.angle(fft_values))

    mask = frequency <= fmax
    mask_frequency = frequency[mask]
    mask_amplitude = magnitude[mask]
    mask_phase = phase[mask]

    if len(mask_amplitude) > 1:
        peak_index = np.argmax(mask_amplitude[1:]) + 1
        dominant_frequency = mask_frequency[peak_index]
        dominant_amplitude = mask_amplitude[peak_index]
        dominant_phase = mask_phase[peak_index]
    else:
        dominant_frequency = 0
        dominant_amplitude = 0
        dominant_phase = 0

    # hide phase of bins that are just noise
    threshold = (threshold_percent / 100) * np.max(magnitude) if np.max(magnitude) > 0 else 0
    significant = mask_amplitude >= threshold
    significant_frequency = mask_frequency[significant]
    significant_phase = mask_phase[significant]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Sampling Frequency", f"{fs:.2f} Hz")
    col2.metric("Dominant Frequency", f"{dominant_frequency:.2f} Hz")
    col3.metric("Phase at Dominant Frequency", f"{dominant_phase:.2f} °")
    col4.metric("Frequency Resolution", f"{frequency_resolution:.2f}")

    st.subheader("Phase Spectrum")
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(mask_frequency, mask_phase, color='lightgray', label='All bins (noise included)')
    ax1.scatter(significant_frequency, significant_phase, color='tab:blue', s=12,
                label=f'Significant bins (>= {threshold_percent}% of peak)')
    ax1.axhline(0, color='black', linewidth=0.5)
    ax1.set_xlabel('Frequency (Hz)')
    ax1.set_ylabel('Phase (degrees)')
    ax1.set_title('Phase Spectrum')
    ax1.set_ylim(-180, 180)
    ax1.grid(True)
    ax1.legend()
    st.pyplot(fig1)

    st.subheader("Instantaneous Phase (Hilbert Transform)")
    analytic_signal = hilbert(vibration_detrended)
    instantaneous_phase = np.unwrap(np.angle(analytic_signal))
    instantaneous_phase_deg = np.degrees(instantaneous_phase)
    instantaneous_frequency = np.diff(instantaneous_phase) * fs / (2 * np.pi)

    fig2, ax2 = plt.subplots(figsize=(12, 4))
    ax2.plot(time, instantaneous_phase_deg)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Phase (degrees)')
    ax2.set_title('Instantaneous Phase (Unwrapped)')
    ax2.grid(True)
    st.pyplot(fig2)

    st.subheader("Instantaneous Frequency")
    fig3, ax3 = plt.subplots(figsize=(12, 4))
    ax3.plot(time[1:], instantaneous_frequency)
    ax3.set_xlabel('Time (s)')
    ax3.set_ylabel('Frequency (Hz)')
    ax3.set_title('Instantaneous Frequency')
    ax3.grid(True)
    st.pyplot(fig3)

def spectrogram_analysis(time, vibration_detrended, fs):
    st.header('Spectrogram Analysis')
    st.sidebar.subheader('Spectrogram Setting')

    fmax = st.slider('Select frequency range for spectrogram',
                     min_value=0.0, max_value=float(fs/2), value=min(100.0, float(fs/2)))
    nperseg = st.sidebar.slider('Segment length (samples)', min_value=64,
                                max_value=min(4096, len(vibration_detrended)),
                                value=min(256, len(vibration_detrended)), step=64)
    overlap_percent = st.sidebar.slider('Overlap (%)', min_value=0, max_value=95, value=75)
    cmap = st.sidebar.selectbox('Colormap', ['viridis', 'inferno', 'magma', 'jet', 'turbo', 'plasma'])

    noverlap = int(nperseg * overlap_percent / 100)
    frequency_resolution = fs / nperseg
    time_resolution = (nperseg - noverlap) / fs

    frequencies, times, Sxx = spectrogram(vibration_detrended, fs=fs, nperseg=nperseg,
                                          noverlap=noverlap, scaling='spectrum', mode='magnitude')

    mask = frequencies <= fmax
    mask_frequencies = frequencies[mask]
    mask_Sxx = Sxx[mask, :]

    if mask_Sxx.size > 0:
        peak_index = np.unravel_index(np.argmax(mask_Sxx), mask_Sxx.shape)
        peak_frequency = mask_frequencies[peak_index[0]]
        peak_time = times[peak_index[1]]
        peak_magnitude = mask_Sxx[peak_index]
    else:
        peak_frequency = 0
        peak_time = 0
        peak_magnitude = 0

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Peak Frequency", f"{peak_frequency:.2f} Hz")
    col2.metric("Peak Time", f"{peak_time:.3f} s")
    col3.metric("Peak Magnitude", f"{peak_magnitude:.4f}")
    col4.metric("Freq / Time Resolution", f"{frequency_resolution:.2f} Hz / {time_resolution*1000:.1f} ms")

    st.subheader("Spectrogram (Time - Frequency - Magnitude)")
    fig1, ax1 = plt.subplots(figsize=(12, 6))
    pcm = ax1.pcolormesh(times, mask_frequencies, mask_Sxx, shading='auto', cmap=cmap)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Frequency (Hz)')
    ax1.set_title(f'Spectrogram (segment={nperseg}, overlap={overlap_percent}%)')
    fig1.colorbar(pcm, ax=ax1, label='Magnitude')
    st.pyplot(fig1)

    st.subheader("Dominant Frequency over Time")
    dominant_index = np.argmax(mask_Sxx, axis=0)
    dominant_frequency_track = mask_frequencies[dominant_index]
    dominant_magnitude_track = mask_Sxx[dominant_index, np.arange(mask_Sxx.shape[1])]

    fig2, ax2 = plt.subplots(figsize=(12, 4))
    ax2.plot(times, dominant_frequency_track)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Frequency (Hz)')
    ax2.set_title('Dominant Frequency over Time')
    ax2.grid(True)
    st.pyplot(fig2)

    st.subheader("Total Vibration Energy over Time")
    energy = np.sum(mask_Sxx ** 2, axis=0)
    fig3, ax3 = plt.subplots(figsize=(12, 4))
    ax3.plot(times, energy)
    ax3.set_xlabel('Time (s)')
    ax3.set_ylabel('Energy')
    ax3.set_title('Total Vibration Energy over Time')
    ax3.grid(True)
    st.pyplot(fig3)

st.sidebar.title('Control Panel of Vibration analyzer', text_alignment= 'center')
uploaded_file = st.sidebar.file_uploader('Upload Your Vibration data', type= ['csv', 'xlsx'])
if uploaded_file is not None:
    df = load_data(uploaded_file)
    if df is not None:
        st.success('File uploaded Successfully')
        with st.expander("View Uploaded Data"):
            st.dataframe(df.head(20), use_container_width= True)

        time_column, vibration = select_columns(df)
        time, vibration_raw, vibration_detrended = signal_preparation(df, time_column, vibration)
        try:
            dt, fs = sampling_frequency(time)
        except Exception:
            st.error("Unable to calculate sampling frequency.")
            st.stop()
        window = window_type(vibration_raw)

        st.sidebar.subheader('Select Analysis')
        analysis = st.sidebar.radio('Select your analysis',
                                    ['Time Domain Analysis', 'Frequency domain Analysis',
                                     'Envelope Analysis', 'Phase Analysis', 'Spectrogram Analysis'])

        if analysis == 'Time Domain Analysis':
            time_domain_analysis(time, vibration_raw)
        elif analysis == 'Frequency domain Analysis':
            frequency_domain_analysis(vibration_detrended, window, dt, fs)
        elif analysis == 'Envelope Analysis':
            envelope_analysis(time, vibration_raw, fs, window)
        elif analysis == 'Phase Analysis':
            phase_analysis(time, vibration_detrended, window, dt, fs, df, time_column, vibration)
        elif analysis == 'Spectrogram Analysis':
            spectrogram_analysis(time, vibration_detrended, fs)
else:
    st.info("Please upload a CSV or Excel vibration data file.")
