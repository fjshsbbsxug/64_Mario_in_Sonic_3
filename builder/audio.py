"""
Mario's voice clips: decoded from the ROM and written as Ogg Vorbis files.

Ogg Vorbis encoding uses the "soundfile" Python package if it's installed,
otherwise the "ffmpeg" command line tool if it's available.
"""

import os
import shutil
import subprocess
import tempfile
import wave

import numpy as np

import rom as romdata


OUTPUT_RATE = 48000


def _resample(samples, rate_in, rate_out):
    x_in = np.arange(len(samples)) / rate_in
    n_out = int(round(len(samples) * rate_out / rate_in))
    x_out = np.arange(n_out) / rate_out
    return np.interp(x_out, x_in, samples.astype(np.float64))


def _write_ogg_soundfile(path, pcm):
    import soundfile
    soundfile.write(path, pcm.astype(np.float32) / 32768.0, OUTPUT_RATE, format="OGG", subtype="VORBIS")


def _write_ogg_ffmpeg(path, pcm, ffmpeg):
    fd, wav_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(OUTPUT_RATE)
            w.writeframes(np.clip(pcm, -32768, 32767).astype("<i2").tobytes())
        subprocess.check_call([ffmpeg, "-v", "error", "-y", "-i", wav_path, "-c:a", "libvorbis", "-q:a", "5", path])
    finally:
        os.remove(wav_path)


def find_encoder():
    """Returns a function (path, pcm) -> None writing Ogg Vorbis, or None if no encoder is available."""
    try:
        import soundfile
        if "OGG" in soundfile.available_formats():
            return _write_ogg_soundfile
    except Exception:
        pass
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return lambda path, pcm: _write_ogg_ffmpeg(path, pcm, ffmpeg)
    return None


def write_voices(rom, audio_dir, encoder):
    os.makedirs(audio_dir, exist_ok=True)
    names = sorted(romdata.VOICE_SAMPLES)
    for name in names:
        pcm = romdata.load_voice(rom, name)
        pcm = _resample(pcm, romdata.VOICE_SAMPLE_RATE, OUTPUT_RATE)
        encoder(os.path.join(audio_dir, name + ".ogg"), pcm)
    with open(os.path.join(audio_dir, "audio_replacements.json"), "w") as f:
        f.write("{\n" + ",\n".join('\t"%s": { "File": "%s.ogg", "Type": "Sound" }' % (n, n) for n in names) + "\n}\n")
