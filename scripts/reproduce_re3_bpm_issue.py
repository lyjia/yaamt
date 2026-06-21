
import sys
import os
import time
import numpy as np
import scipy.io.wavfile
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from providers.analysis.bpm.re3_bpm import RE3MultibandSpectralBPMAnalyzer
from models.media_file import MediaFile
from util.logging import configure_logger
from util.const import KEY_STREAM_INFO, KEY_LENGTH, KEY_VALUE

# Configure logging
configure_logger(log_level='debug')

def generate_test_audio(filename, duration_sec=30, bpm=120, sample_rate=44100):
    print(f"Generating {duration_sec}s audio at {bpm} BPM...")
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    
    # Create a beat every 60/bpm seconds
    beat_interval = 60.0 / bpm
    
    # Simple kick drum synthesis (sine sweep)
    audio = np.zeros_like(t)
    
    for i in range(int(duration_sec / beat_interval)):
        start_time = i * beat_interval
        start_idx = int(start_time * sample_rate)
        
        # 100ms kick
        kick_len = int(0.1 * sample_rate)
        if start_idx + kick_len > len(audio):
            break
            
        # Frequency sweep 150Hz -> 50Hz
        kt = np.linspace(0, 0.1, kick_len)
        freq = np.linspace(150, 50, kick_len)
        phase = 2 * np.pi * np.cumsum(freq) / sample_rate
        kick = np.sin(phase) * np.exp(-kt * 20) # Decay
        
        audio[start_idx:start_idx+kick_len] += kick

    # Normalize to 16-bit range (as expected by RE3 analyzer)
    audio = audio / np.max(np.abs(audio)) * 32000
    
    scipy.io.wavfile.write(filename, sample_rate, audio.astype(np.int16))
    print(f"Saved to {filename}")

def run_analysis(filename):
    print(f"Analyzing {filename}...")
    media_file = MediaFile(filename)
    
    # Manually inject duration since we just created it and MediaFile might need a full load
    # or the wav header might be simple
    media_file._combined_metadata[KEY_STREAM_INFO][KEY_LENGTH] = {
        KEY_VALUE: 30.0
    }
    
    # Mock options
    options = {
        'decimation_size': 64,
        'threshold_time': 60.0
    }
    
    analyzer = RE3MultibandSpectralBPMAnalyzer(media_file, options)
    
    start_time = time.time()
    result = analyzer.analyze()
    end_time = time.time()
    
    print(f"Analysis took {end_time - start_time:.4f} seconds")
    print(f"Result: {result.data if result.success else result.error}")
    
    return result

if __name__ == "__main__":
    filename = os.path.join(os.path.dirname(__file__), "test_120bpm.wav")
    generate_test_audio(filename, bpm=120)
    run_analysis(filename)
