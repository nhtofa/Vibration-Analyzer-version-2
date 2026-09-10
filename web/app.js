(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.VibrationAnalyzer = factory();
  }
}(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function parseCSV(text) {
    const rows = [];
    let row = [];
    let field = '';
    let quoted = false;
    for (let i = 0; i < text.length; i += 1) {
      const char = text[i];
      const next = text[i + 1];
      if (char === '"') {
        if (quoted && next === '"') { field += '"'; i += 1; }
        else { quoted = !quoted; }
      } else if (!quoted && (char === ',' || char === '\t')) {
        row.push(field.trim()); field = '';
      } else if (!quoted && (char === '\n' || char === '\r')) {
        if (char === '\r' && next === '\n') i += 1;
        row.push(field.trim()); field = '';
        if (row.some((value) => value !== '')) rows.push(row);
        row = [];
      } else {
        field += char;
      }
    }
    row.push(field.trim());
    if (row.some((value) => value !== '')) rows.push(row);
    if (rows.length < 2) throw new Error('The file must contain a header and at least one data row.');
    const width = rows[0].length;
    const headers = [];
    rows[0].forEach((raw, index) => {
      let header = raw || `Column ${index + 1}`;
      let candidate = header;
      let suffix = 2;
      while (headers.includes(candidate)) { candidate = `${header} (${suffix})`; suffix += 1; }
      headers.push(candidate);
    });
    const data = rows.slice(1).map((values) => {
      const item = {};
      headers.forEach((header, index) => { item[header] = values[index] === undefined ? '' : values[index]; });
      return item;
    });
    return { headers, rows: data };
  }

  function fromMatrix(matrix) {
    if (!matrix || matrix.length < 2) throw new Error('The workbook must contain a header and at least one data row.');
    const headers = [];
    (matrix[0] || []).forEach((raw, index) => {
      const base = String(raw ?? '').trim() || `Column ${index + 1}`;
      let header = base; let suffix = 2;
      while (headers.includes(header)) { header = `${base} (${suffix})`; suffix += 1; }
      headers.push(header);
    });
    const rows = matrix.slice(1).filter((values) => values && values.some((value) => value !== null && value !== undefined && String(value) !== ''))
      .map((values) => {
        const item = {};
        headers.forEach((header, index) => { item[header] = values[index] ?? ''; });
        return item;
      });
    return { headers, rows };
  }

  function numericColumn(data, name) {
    return data.rows.map((row) => Number(row[name]));
  }

  function prepareSeries(data, timeName, signalName) {
    const time = []; const signal = [];
    data.rows.forEach((row) => {
      const t = Number(row[timeName]); const value = Number(row[signalName]);
      if (Number.isFinite(t) && Number.isFinite(value)) { time.push(t); signal.push(value); }
    });
    if (time.length < 8) throw new Error('At least eight valid numeric samples are required.');
    const positive = [];
    for (let i = 1; i < time.length; i += 1) if (time[i] > time[i - 1]) positive.push(time[i] - time[i - 1]);
    if (!positive.length) throw new Error('The time column must increase between samples.');
    return { time, signal, detrended: detrend(signal), fs: 1 / median(positive), dt: median(positive) };
  }

  function median(values) {
    const sorted = Array.from(values).sort((a, b) => a - b);
    const middle = Math.floor(sorted.length / 2);
    return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  }

  function mean(values) { return values.reduce((sum, value) => sum + value, 0) / values.length; }
  function detrend(values) { const average = mean(values); return values.map((value) => value - average); }

  function statistics(values) {
    const average = mean(values);
    const centered = values.map((value) => value - average);
    const variance = mean(centered.map((value) => value * value));
    const std = Math.sqrt(variance);
    const rms = Math.sqrt(mean(values.map((value) => value * value)));
    const peak = Math.max(...values.map((value) => Math.abs(value)));
    const skewness = std ? mean(centered.map((value) => (value / std) ** 3)) : 0;
    const kurtosis = std ? mean(centered.map((value) => (value / std) ** 4)) - 3 : 0;
    return {
      mean: average, standardDeviation: std, peak, minimum: Math.min(...values), maximum: Math.max(...values),
      rms, peakToPeak: Math.max(...values) - Math.min(...values),
      crestFactor: rms ? peak / rms : 0, skewness, kurtosis,
    };
  }

  function nextPowerOfTwo(value) { let result = 1; while (result < value) result *= 2; return result; }

  function fft(real, imaginary, inverse) {
    const n = real.length;
    for (let i = 1, j = 0; i < n; i += 1) {
      let bit = n >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) {
        [real[i], real[j]] = [real[j], real[i]];
        [imaginary[i], imaginary[j]] = [imaginary[j], imaginary[i]];
      }
    }
    for (let length = 2; length <= n; length <<= 1) {
      const angle = (inverse ? 2 : -2) * Math.PI / length;
      const wReal = Math.cos(angle); const wImag = Math.sin(angle);
      for (let start = 0; start < n; start += length) {
        let currentReal = 1; let currentImag = 0; const half = length >> 1;
        for (let offset = 0; offset < half; offset += 1) {
          const even = start + offset; const odd = even + half;
          const productReal = currentReal * real[odd] - currentImag * imaginary[odd];
          const productImag = currentReal * imaginary[odd] + currentImag * real[odd];
          const evenReal = real[even]; const evenImag = imaginary[even];
          real[even] = evenReal + productReal; imaginary[even] = evenImag + productImag;
          real[odd] = evenReal - productReal; imaginary[odd] = evenImag - productImag;
          const nextReal = currentReal * wReal - currentImag * wImag;
          currentImag = currentReal * wImag + currentImag * wReal; currentReal = nextReal;
        }
      }
    }
    if (inverse) for (let i = 0; i < n; i += 1) { real[i] /= n; imaginary[i] /= n; }
    return { real, imaginary };
  }

  function transform(values) {
    const n = nextPowerOfTwo(values.length);
    const real = new Float64Array(n); const imaginary = new Float64Array(n);
    values.forEach((value, index) => { real[index] = value; });
    fft(real, imaginary, false);
    return { real, imaginary, n };
  }

  function windowValues(name, length) {
    const values = new Float64Array(length);
    if (name === 'none') { values.fill(1); return values; }
    for (let i = 0; i < length; i += 1) {
      const phase = 2 * Math.PI * i / Math.max(1, length - 1);
      if (name === 'hamming') values[i] = 0.54 - 0.46 * Math.cos(phase);
      else if (name === 'blackman') values[i] = 0.42 - 0.5 * Math.cos(phase) + 0.08 * Math.cos(2 * phase);
      else if (name === 'flattop') values[i] = 0.21557895 - 0.41663158 * Math.cos(phase) + 0.277263158 * Math.cos(2 * phase) - 0.083578947 * Math.cos(3 * phase) + 0.006947368 * Math.cos(4 * phase);
      else values[i] = 0.5 * (1 - Math.cos(phase));
    }
    return values;
  }

  function spectrum(values, fs, windowName = 'hann') {
    const window = windowValues(windowName, values.length);
    const weighted = values.map((value, index) => value * window[index]);
    const transformed = transform(weighted); const count = transformed.n;
    const bins = Math.floor(count / 2) + 1; const frequencies = []; const magnitude = []; const phase = [];
    const scale = 2 / Math.max(1e-12, window.reduce((sum, value) => sum + value, 0));
    for (let index = 0; index < bins; index += 1) {
      frequencies.push(index * fs / count);
      let amplitude = Math.hypot(transformed.real[index], transformed.imaginary[index]) * scale;
      if (index === 0 || (count % 2 === 0 && index === count / 2)) amplitude /= 2;
      magnitude.push(amplitude); phase.push(Math.atan2(transformed.imaginary[index], transformed.real[index]) * 180 / Math.PI);
    }
    return { frequencies, magnitude, phase, real: transformed.real, imaginary: transformed.imaginary, n: count };
  }

  function dominantIndex(frequencies, magnitude, maxFrequency) {
    let best = 0;
    for (let i = 1; i < magnitude.length; i += 1) {
      if (frequencies[i] <= maxFrequency && magnitude[i] > magnitude[best]) best = i;
    }
    return best;
  }

  function bandpassEnvelope(values, fs, low, high) {
    const transformed = transform(detrend(values));
    for (let index = 0; index < transformed.n; index += 1) {
      const frequency = (index <= transformed.n / 2 ? index : transformed.n - index) * fs / transformed.n;
      if (frequency < low || frequency > high) { transformed.real[index] = 0; transformed.imaginary[index] = 0; }
    }
    fft(transformed.real, transformed.imaginary, true);
    const filtered = Array.from(transformed.real.slice(0, values.length));
    const analytic = transform(filtered);
    for (let index = 1; index < analytic.n / 2; index += 1) { analytic.real[index] *= 2; analytic.imaginary[index] *= 2; }
    for (let index = analytic.n / 2 + 1; index < analytic.n; index += 1) { analytic.real[index] = 0; analytic.imaginary[index] = 0; }
    fft(analytic.real, analytic.imaginary, true);
    const envelope = Array.from({ length: values.length }, (_, index) => Math.hypot(analytic.real[index], analytic.imaginary[index]));
    const envelopeSpectrum = spectrum(detrend(envelope), fs, 'hann');
    return { filtered, envelope, spectrum: envelopeSpectrum };
  }

  function correlation(a, b) {
    const n = Math.min(a.length, b.length); const aa = a.slice(0, n); const bb = b.slice(0, n);
    const ma = mean(aa); const mb = mean(bb); let numerator = 0; let da = 0; let db = 0;
    for (let i = 0; i < n; i += 1) { const x = aa[i] - ma; const y = bb[i] - mb; numerator += x * y; da += x * x; db += y * y; }
    return da && db ? numerator / Math.sqrt(da * db) : 0;
  }

  function phaseAnalysis(mainValues, referenceValues, fs, maxFrequency, windowName = 'hann') {
    const n = Math.min(mainValues.length, referenceValues.length);
    const main = spectrum(mainValues.slice(0, n), fs, windowName);
    const reference = spectrum(referenceValues.slice(0, n), fs, windowName);
    const crossPhase = main.frequencies.map((_, index) => {
      const crossReal = main.real[index] * reference.real[index] + main.imaginary[index] * reference.imaginary[index];
      const crossImag = main.imaginary[index] * reference.real[index] - main.real[index] * reference.imaginary[index];
      return Math.atan2(crossImag, crossReal) * 180 / Math.PI;
    });
    const index = dominantIndex(main.frequencies, main.magnitude, maxFrequency);
    return { main, reference, crossPhase, dominantFrequency: main.frequencies[index], phaseDifference: crossPhase[index], correlation: correlation(mainValues, referenceValues), index };
  }

  function spectrogram(values, fs, segmentLength, overlap, maxFrequency) {
    const step = Math.max(1, Math.floor(segmentLength * (1 - overlap)));
    const times = []; const columns = []; let start = 0; let frequencies = [];
    while (start < values.length) {
      const segment = values.slice(start, Math.min(start + segmentLength, values.length));
      if (segment.length < Math.min(16, segmentLength / 2)) break;
      const item = spectrum(segment, fs, 'hann');
      if (!frequencies.length) frequencies = item.frequencies.filter((frequency) => frequency <= maxFrequency);
      const limit = frequencies.length; columns.push(item.magnitude.slice(0, limit));
      times.push((start + segment.length / 2) / fs); start += step;
    }
    const matrix = frequencies.map((_, row) => columns.map((column) => column[row] || 0));
    const dominant = columns.map((column) => {
      let index = 0; for (let i = 1; i < column.length; i += 1) if (column[i] > column[index]) index = i;
      return { frequency: frequencies[index] || 0, magnitude: column[index] || 0 };
    });
    return { frequencies, times, matrix, dominant, frequencyResolution: fs / nextPowerOfTwo(segmentLength), timeResolution: step / fs };
  }

  return { parseCSV, fromMatrix, numericColumn, prepareSeries, statistics, median, detrend, transform, spectrum, dominantIndex, bandpassEnvelope, phaseAnalysis, spectrogram, windowValues };
}));

(function () {
  if (typeof document === 'undefined' || !window.VibrationAnalyzer) return;
  const Core = window.VibrationAnalyzer;
  const state = { data: null, series: null, lastRender: null };
  const $ = (id) => document.getElementById(id);
  const controls = ['data-controls', 'analysis-controls', 'envelope-controls', 'spectrogram-controls'];

  function show(id, visible) { $(id).hidden = !visible; }
  function escapeHtml(value) { return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char])); }
  function format(value, digits = 3) { return Number.isFinite(value) ? Number(value).toFixed(digits) : '—'; }
  function addMetric(label, value) { return `<div class="metric"><div class="metric-label">${escapeHtml(label)}</div><div class="metric-value">${escapeHtml(value)}</div></div>`; }
  function setSummary(items) { $('summary').innerHTML = items.map(([label, value]) => addMetric(label, value)).join(''); }
  function card(title, wide = false, short = false) {
    const wrapper = document.createElement('article'); wrapper.className = `plot-card${wide ? ' wide' : ''}`;
    const heading = document.createElement('h3'); heading.textContent = title; wrapper.appendChild(heading);
    const canvas = document.createElement('canvas'); if (short) canvas.className = 'short'; wrapper.appendChild(canvas); $('plots').appendChild(wrapper); return canvas;
  }
  function tableCard(title, headers, rows) {
    const wrapper = document.createElement('article'); wrapper.className = 'plot-card';
    wrapper.innerHTML = `<h3>${escapeHtml(title)}</h3><div class="table-wrap"><table><thead><tr>${headers.map((header) => `<th>${escapeHtml(header)}</th>`).join('')}</tr></thead><tbody>${rows.map((row) => `<tr>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    $('plots').appendChild(wrapper);
  }

  function canvasSize(canvas) {
    const width = Math.max(300, canvas.getBoundingClientRect().width || 600); const height = Math.max(180, canvas.clientHeight || 280); const ratio = window.devicePixelRatio || 1;
    canvas.width = width * ratio; canvas.height = height * ratio; const ctx = canvas.getContext('2d'); ctx.setTransform(ratio, 0, 0, ratio, 0, 0); return { ctx, width, height };
  }
  function drawLines(canvas, datasets, options = {}) {
    const { ctx, width, height } = canvasSize(canvas); const pad = { left: 55, right: 15, top: 15, bottom: 34 }; const plotWidth = width - pad.left - pad.right; const plotHeight = height - pad.top - pad.bottom;
    const x = datasets[0].x; const allY = datasets.flatMap((dataset) => dataset.y.filter(Number.isFinite)); let minX = Math.min(...x); let maxX = Math.max(...x); let minY = Math.min(...allY); let maxY = Math.max(...allY);
    if (minX === maxX) maxX = minX + 1; if (minY === maxY) { minY -= 1; maxY += 1; } const margin = (maxY - minY) * 0.08; minY -= margin; maxY += margin;
    ctx.clearRect(0, 0, width, height); ctx.fillStyle = '#111a2e'; ctx.fillRect(0, 0, width, height); ctx.strokeStyle = '#273653'; ctx.fillStyle = '#94a3bf'; ctx.font = '11px system-ui';
    for (let tick = 0; tick <= 4; tick += 1) { const py = pad.top + plotHeight * tick / 4; ctx.beginPath(); ctx.moveTo(pad.left, py); ctx.lineTo(width - pad.right, py); ctx.stroke(); const value = maxY - (maxY - minY) * tick / 4; ctx.fillText(format(value, 2), 4, py + 4); }
    ctx.beginPath(); ctx.strokeStyle = '#526783'; ctx.moveTo(pad.left, pad.top); ctx.lineTo(pad.left, height - pad.bottom); ctx.lineTo(width - pad.right, height - pad.bottom); ctx.stroke();
    datasets.forEach((dataset, datasetIndex) => { ctx.beginPath(); ctx.strokeStyle = dataset.color || (datasetIndex ? '#55d6a0' : '#55c2ff'); ctx.lineWidth = 1.6; dataset.y.forEach((value, index) => { const px = pad.left + ((dataset.x[index] - minX) / (maxX - minX)) * plotWidth; const py = pad.top + ((maxY - value) / (maxY - minY)) * plotHeight; if (index === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py); }); ctx.stroke(); });
    ctx.fillStyle = '#94a3bf'; ctx.fillText(options.xLabel || 'x', width / 2 - 10, height - 8); ctx.save(); ctx.translate(13, height / 2 + 22); ctx.rotate(-Math.PI / 2); ctx.fillText(options.yLabel || 'amplitude', 0, 0); ctx.restore();
  }
  function drawHeatmap(canvas, result) {
    const { ctx, width, height } = canvasSize(canvas); const pad = { left: 55, right: 15, top: 15, bottom: 34 }; const plotWidth = width - pad.left - pad.right; const plotHeight = height - pad.top - pad.bottom; const rows = result.matrix.length; const cols = result.times.length; ctx.clearRect(0, 0, width, height); ctx.fillStyle = '#111a2e'; ctx.fillRect(0, 0, width, height);
    let peak = 0; result.matrix.forEach((row) => row.forEach((value) => { if (value > peak) peak = value; })); peak = peak || 1;
    for (let y = 0; y < rows; y += 1) for (let x = 0; x < cols; x += 1) { const intensity = Math.sqrt((result.matrix[y][x] || 0) / peak); const r = Math.floor(20 + 180 * intensity); const g = Math.floor(35 + 130 * intensity); const b = Math.floor(90 + 150 * (1 - intensity)); ctx.fillStyle = `rgb(${r},${g},${b})`; ctx.fillRect(pad.left + x * plotWidth / cols, pad.top + (rows - y - 1) * plotHeight / rows, Math.ceil(plotWidth / cols) + 1, Math.ceil(plotHeight / rows) + 1); }
    ctx.strokeStyle = '#526783'; ctx.strokeRect(pad.left, pad.top, plotWidth, plotHeight); ctx.fillStyle = '#94a3bf'; ctx.font = '11px system-ui'; ctx.fillText('time (s)', width / 2 - 15, height - 8); ctx.save(); ctx.translate(13, height / 2 + 22); ctx.rotate(-Math.PI / 2); ctx.fillText('frequency (Hz)', 0, 0); ctx.restore();
  }

  function refreshColumns() {
    const timeSelect = $('time-column'); const signalSelect = $('signal-column'); const referenceSelect = $('reference-column'); const headers = state.data.headers;
    const preferredTime = headers.find((header) => /time|seconds?|sec/i.test(header)) || headers[0];
    timeSelect.innerHTML = headers.map((header) => `<option>${escapeHtml(header)}</option>`).join(''); timeSelect.value = preferredTime;
    const signals = headers.filter((header) => header !== timeSelect.value && Core.numericColumn(state.data, header).filter(Number.isFinite).length >= 8);
    signalSelect.innerHTML = signals.map((header) => `<option>${escapeHtml(header)}</option>`).join('');
    referenceSelect.innerHTML = `<option value="">None</option>${signals.map((header) => `<option>${escapeHtml(header)}</option>`).join('')}`;
    if (signals.length) { signalSelect.value = signals[0]; referenceSelect.value = ''; }
    timeSelect.onchange = refreshColumns;
    show('data-controls', true); show('analysis-controls', true); render();
  }

  function updateFrequencyControl() {
    const fs = state.series.fs; const slider = $('frequency-max'); const maximum = Math.max(0.1, fs / 2); const previous = Number(slider.value); const newSeries = slider.dataset.fs !== String(fs); slider.max = maximum; slider.step = maximum > 20 ? 0.1 : Math.max(0.01, maximum / 100); slider.value = newSeries || !slider.dataset.ready ? Math.min(maximum, Math.max(10, maximum)) : (Number.isFinite(previous) && previous > 0 ? Math.min(maximum, previous) : maximum); slider.dataset.fs = String(fs); slider.dataset.ready = '1'; $('frequency-output').value = `${format(Number(slider.value), 2)} Hz`;
    slider.oninput = () => { $('frequency-output').value = `${format(Number(slider.value), 2)} Hz`; render(); };
  }
  function selectedMaxFrequency() { return Number($('frequency-max').value) || state.series.fs / 2; }
  function renderTime(series) {
    const stats = Core.statistics(series.signal); setSummary([['Samples', String(series.signal.length)], ['Sampling frequency', `${format(series.fs, 2)} Hz`], ['Peak', format(stats.peak, 4)], ['RMS', format(stats.rms, 4)], ['Peak-to-peak', format(stats.peakToPeak, 4)], ['Crest factor', format(stats.crestFactor, 3)], ['Skewness', format(stats.skewness, 3)], ['Kurtosis', format(stats.kurtosis, 3)]]);
    const canvas = card('Time-domain waveform', true); drawLines(canvas, [{ x: series.time, y: series.signal }], { xLabel: 'time', yLabel: 'amplitude' });
    tableCard('Statistics', ['Metric', 'Value'], [['Mean', format(stats.mean, 5)], ['Minimum', format(stats.minimum, 5)], ['Maximum', format(stats.maximum, 5)], ['Standard deviation', format(stats.standardDeviation, 5)]]);
  }
  function renderFrequency(series) {
    const item = Core.spectrum(series.detrended, series.fs, $('window-select').value); const max = selectedMaxFrequency(); const index = Core.dominantIndex(item.frequencies, item.magnitude, max); setSummary([['Sampling frequency', `${format(series.fs, 2)} Hz`], ['Dominant frequency', `${format(item.frequencies[index], 3)} Hz`], ['Dominant amplitude', format(item.magnitude[index], 5)], ['Resolution', `${format(series.fs / item.n, 4)} Hz`], ['Window', $('window-select').selectedOptions[0].text]]);
    const visible = item.frequencies.map((frequency, i) => i).filter((i) => item.frequencies[i] <= max); const canvas = card('Frequency spectrum', true); drawLines(canvas, [{ x: visible.map((i) => item.frequencies[i]), y: visible.map((i) => item.magnitude[i]) }], { xLabel: 'frequency (Hz)', yLabel: 'amplitude' });
  }
  function renderEnvelope(series) {
    const nyquist = series.fs / 2; const low = Math.max(0.01, Number($('envelope-low').value)); const high = Math.min(nyquist * 0.98, Number($('envelope-high').value));
    if (!(low < high)) throw new Error(`Envelope low cut-off must be below high cut-off and Nyquist (${format(nyquist, 2)} Hz).`);
    const result = Core.bandpassEnvelope(series.signal, series.fs, low, high); const max = selectedMaxFrequency(); const index = Core.dominantIndex(result.spectrum.frequencies, result.spectrum.magnitude, max); setSummary([['Filter band', `${format(low, 2)}–${format(high, 2)} Hz`], ['Envelope dominant', `${format(result.spectrum.frequencies[index], 3)} Hz`], ['Envelope amplitude', format(result.spectrum.magnitude[index], 5)], ['Sampling frequency', `${format(series.fs, 2)} Hz`]]);
    drawLines(card('Band-pass filtered signal', true), [{ x: series.time, y: result.filtered }], { xLabel: 'time', yLabel: 'amplitude' }); drawLines(card('Hilbert envelope', true), [{ x: series.time, y: result.envelope, color: '#55d6a0' }], { xLabel: 'time', yLabel: 'envelope' });
    const visible = result.spectrum.frequencies.map((frequency, i) => i).filter((i) => result.spectrum.frequencies[i] <= max); drawLines(card('Envelope spectrum', true), [{ x: visible.map((i) => result.spectrum.frequencies[i]), y: visible.map((i) => result.spectrum.magnitude[i]), color: '#7c6cff' }], { xLabel: 'frequency (Hz)', yLabel: 'amplitude' });
  }
  function renderPhase(series) {
    const referenceName = $('reference-column').value; const max = selectedMaxFrequency();
    if (!referenceName) {
      const item = Core.spectrum(series.detrended, series.fs, $('window-select').value); const index = Core.dominantIndex(item.frequencies, item.magnitude, max); setSummary([['Dominant frequency', `${format(item.frequencies[index], 3)} Hz`], ['Phase at dominant', `${format(item.phase[index], 2)}°`], ['Resolution', `${format(series.fs / item.n, 4)} Hz`], ['Reference', 'None']]); const visible = item.frequencies.map((frequency, i) => i).filter((i) => item.frequencies[i] <= max); drawLines(card('Phase spectrum', true), [{ x: visible.map((i) => item.frequencies[i]), y: visible.map((i) => item.phase[i]) }], { xLabel: 'frequency (Hz)', yLabel: 'phase (degrees)' }); return;
    }
    const reference = Core.prepareSeries(state.data, $('time-column').value, referenceName); const result = Core.phaseAnalysis(series.detrended, reference.detrended, series.fs, max, $('window-select').value); setSummary([['Measured signal', $('signal-column').value], ['Reference signal', referenceName], ['Dominant frequency', `${format(result.dominantFrequency, 3)} Hz`], ['Phase difference', `${format(result.phaseDifference, 2)}°`], ['Time correlation', format(result.correlation, 4)]]);
    const n = Math.min(series.time.length, reference.time.length, result.main.frequencies.length); drawLines(card('Measured vs reference waveform', true), [{ x: series.time.slice(0, n), y: series.detrended.slice(0, n) }, { x: series.time.slice(0, n), y: reference.detrended.slice(0, n), color: '#55d6a0' }], { xLabel: 'time', yLabel: 'amplitude' }); const visible = result.main.frequencies.map((frequency, i) => i).filter((i) => result.main.frequencies[i] <= max); drawLines(card('Cross-phase spectrum', true), [{ x: visible.map((i) => result.main.frequencies[i]), y: visible.map((i) => visible.map((j) => result.crossPhase[j])[visible.indexOf(i)]) }], { xLabel: 'frequency (Hz)', yLabel: 'phase difference (degrees)' });
  }
  function renderSpectrogram(series) {
    const segment = Number($('spectrogram-segment').value); const overlap = Number($('spectrogram-overlap').value) / 100; const max = selectedMaxFrequency(); const result = Core.spectrogram(series.detrended, series.fs, segment, overlap, max); if (!result.times.length || !result.frequencies.length) throw new Error('Not enough samples for the selected spectrogram segment.');
    const peak = result.dominant.reduce((best, item, index) => item.magnitude > best.magnitude ? { ...item, index } : best, { magnitude: -Infinity, frequency: 0, index: 0 }); setSummary([['Peak frequency', `${format(peak.frequency, 3)} Hz`], ['Peak time', `${format(result.times[peak.index], 3)} s`], ['Peak magnitude', format(peak.magnitude, 5)], ['Frequency resolution', `${format(result.frequencyResolution, 3)} Hz`], ['Time resolution', `${format(result.timeResolution * 1000, 1)} ms`]]);
    drawHeatmap(card('Spectrogram (time · frequency · magnitude)', true), result); drawLines(card('Dominant frequency over time'), [{ x: result.times, y: result.dominant.map((item) => item.frequency), color: '#55d6a0' }], { xLabel: 'time (s)', yLabel: 'frequency (Hz)' }); drawLines(card('Vibration energy over time'), [{ x: result.times, y: result.dominant.map((item) => item.magnitude ** 2), color: '#7c6cff' }], { xLabel: 'time (s)', yLabel: 'energy' });
  }
  function render() {
    if (!state.data) return; $('empty-state').hidden = true; $('dashboard').hidden = false; $('plots').innerHTML = ''; const timeName = $('time-column').value; const signalName = $('signal-column').value;
    try { state.series = Core.prepareSeries(state.data, timeName, signalName); updateFrequencyControl(); const analysis = $('analysis-select').value; show('envelope-controls', analysis === 'envelope'); show('spectrogram-controls', analysis === 'spectrogram'); if (analysis === 'time') renderTime(state.series); else if (analysis === 'frequency') renderFrequency(state.series); else if (analysis === 'envelope') renderEnvelope(state.series); else if (analysis === 'phase') renderPhase(state.series); else renderSpectrogram(state.series); state.lastRender = analysis; } catch (error) { setSummary([['Status', 'Unable to analyze file']]); $('plots').innerHTML = `<article class="plot-card wide"><h3>Input error</h3><p class="muted">${escapeHtml(error.message)}</p></article>`; }
  }

  async function loadFile(file) {
    $('file-status').textContent = `Reading ${file.name}…`;
    try {
      let parsed;
      if (/\.xlsx?$/i.test(file.name)) { if (!window.XLSX) throw new Error('Excel support is not bundled. Use CSV or rebuild the vendor assets.'); const workbook = window.XLSX.read(await file.arrayBuffer(), { type: 'array' }); const first = workbook.Sheets[workbook.SheetNames[0]]; parsed = Core.fromMatrix(window.XLSX.utils.sheet_to_json(first, { header: 1, raw: true })); }
      else parsed = Core.parseCSV(await file.text());
      state.data = parsed; $('file-status').textContent = `${file.name} · ${parsed.rows.length} rows · ${parsed.headers.length} columns`; refreshColumns();
    } catch (error) { state.data = null; $('file-status').textContent = error.message; $('dashboard').hidden = true; $('empty-state').hidden = false; controls.forEach((id) => show(id, false)); }
  }

  $('file-input').addEventListener('change', (event) => { if (event.target.files[0]) loadFile(event.target.files[0]); });
  $('signal-column').addEventListener('change', render); $('reference-column').addEventListener('change', render); $('analysis-select').addEventListener('change', render); $('window-select').addEventListener('change', render); $('envelope-low').addEventListener('input', render); $('envelope-high').addEventListener('input', render); $('spectrogram-overlap').addEventListener('input', () => { $('overlap-output').value = `${$('spectrogram-overlap').value}%`; render(); });
  $('spectrogram-segment').innerHTML = [64, 128, 256, 512, 1024, 2048].map((value) => `<option value="${value}">${value}</option>`).join(''); $('spectrogram-segment').value = '256'; $('spectrogram-segment').addEventListener('change', render);
}());
