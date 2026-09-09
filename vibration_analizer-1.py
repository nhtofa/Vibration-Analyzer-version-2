import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from scipy.fft import rfft, rfftfreq
from scipy.signal import butter, sosfiltfilt, get_window, hilbert
from scipy.stats import skew, kurtosis

st.set_page_config(page_title='Vibration Analyzer version-1', page_icon= "📈", layout= 'wide')
st.title('Welcome to Vibration Analizer', text_alignment='center')
st.subheader('Upload your vibration data and perform\n, Waveform analysis, Frequency domain Analysis,'
             'Envelope Analysis', text_alignment='center')

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
    vibration_column = df[vibration].to_numpy()
    return time_column, vibration, vibration_column

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

st.sidebar.title('Control Panel of Vibration analyzer', text_alignment= 'center')
uploaded_file = st.sidebar.file_uploader('Upload Your Vibration data', type= ['csv', 'xlsx'])
if uploaded_file is not None:
    df = load_data(uploaded_file)
    if df is not None:
        st.success('File uploaded Successfully')
        with st.expander("View Uploaded Data"):
            st.dataframe(df.head(20), use_container_width= True)

        time_column, vibration, vibration_column = select_columns(df)
        time,vibration, vibration_detrended = signal_preparation(df, time_column, vibration)
        try:
            dt, fs = sampling_frequency(time)
        except Exception:
            st.error("Unable to calculate sampling frequency.")
            st.stop()
        window = window_type(vibration_column)

        st.sidebar.subheader('Select Analysis')
        analysis = st.sidebar.radio('Select your analysis',
                                    ['Time Domain Analysis', 'Frequency domain Analysis', 'Envelope Analysis'])

        if analysis == 'Time Domain Analysis':
            time_domain_analysis(time, vibration_column)
        elif analysis == 'Frequency domain Analysis':
            frequency_domain_analysis(vibration_detrended, window, dt, fs)
        elif analysis == 'Envelope Analysis':
            envelope_analysis(time, vibration, fs, window)
else:
    st.info("Please upload a CSV or Excel vibration data file.")


