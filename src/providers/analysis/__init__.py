from enum import Enum
from .base import AnalyzerBase, AnalyzerResult

class AnalyzerCategory(Enum):
    BPM = "BPM"
    KEY = "Key"
    FINGERPRINT = "Fingerprint"
    LOUDNESS = "Loudness"
