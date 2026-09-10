const assert = require('node:assert/strict');
const Core = require('../web/app.js');

function approximately(actual, expected, tolerance, label) {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${label}: ${actual} is not within ${tolerance} of ${expected}`);
}

const parsed = Core.parseCSV('time,main,reference\n0,1,2\n0.001,3,4\n');
assert.deepEqual(parsed.headers, ['time', 'main', 'reference']);
assert.equal(parsed.rows.length, 2);

const fs = 1000;
const frequency = 12;
const phase = Math.PI / 4;
const time = Array.from({ length: 2048 }, (_, index) => index / fs);
const main = time.map((value) => Math.sin(2 * Math.PI * frequency * value));
const reference = time.map((value) => Math.sin(2 * Math.PI * frequency * value - phase));
const rows = time.map((value, index) => ({ time: value, main: main[index], reference: reference[index] }));
const data = { headers: ['time', 'main', 'reference'], rows };
const series = Core.prepareSeries(data, 'time', 'main');
approximately(series.fs, fs, 1e-8, 'sampling frequency');

const stats = Core.statistics(main);
approximately(stats.rms, Math.SQRT1_2, 1e-3, 'RMS');
approximately(stats.peak, 1, 1e-3, 'peak');

const spectrum = Core.spectrum(series.detrended, series.fs, 'hann');
const dominant = Core.dominantIndex(spectrum.frequencies, spectrum.magnitude, fs / 2);
approximately(spectrum.frequencies[dominant], frequency, series.fs / spectrum.n + 1e-9, 'dominant frequency');

const envelope = Core.bandpassEnvelope(main, fs, 8, 20);
assert.equal(envelope.filtered.length, main.length);
assert.equal(envelope.envelope.length, main.length);
assert.ok(envelope.envelope.every(Number.isFinite));
assert.ok(envelope.envelope.reduce((sum, value) => sum + value, 0) / envelope.envelope.length > 0.8);

const phaseResult = Core.phaseAnalysis(main, reference, fs, 50, 'hann');
approximately(phaseResult.dominantFrequency, frequency, series.fs / spectrum.n + 1e-9, 'phase dominant frequency');
approximately(phaseResult.phaseDifference, phase * 180 / Math.PI, 2, 'phase difference');
approximately(phaseResult.correlation, Math.cos(phase), 0.01, 'time correlation');

const spectrogram = Core.spectrogram(main, fs, 256, 0.5, 100);
assert.ok(spectrogram.times.length > 5);
assert.ok(spectrogram.frequencies.length > 10);
assert.equal(spectrogram.matrix.length, spectrogram.frequencies.length);
assert.equal(spectrogram.matrix[0].length, spectrogram.times.length);
const spectrogramPeak = spectrogram.dominant[Math.floor(spectrogram.dominant.length / 2)];
approximately(spectrogramPeak.frequency, frequency, fs / 256 + 1e-9, 'spectrogram dominant frequency');

console.log('web core tests: PASS');
