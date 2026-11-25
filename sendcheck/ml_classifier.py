"""
ml_classifier.py — ML-based email classifier.

Loads the trained model from ml/model.pkl and uses it to classify emails.
Falls back to None if the model hasn't been trained yet — checker.py
handles the fallback to pattern-based classification in that case.
"""

import pickle
from pathlib import Path

# Paths relative to this file
_ML_DIR = Path(__file__).parent.parent / "ml"
_MODEL_FILE = _ML_DIR / "model.pkl"
_VECTORIZER_FILE = _ML_DIR / "vectorizer.pkl"

# Cache the loaded model so we only read the file once
_model = None
_vectorizer = None


def _load():
    """Load model and vectorizer from disk (once)."""
    global _model, _vectorizer
    if _model is not None:
        return True
    if not _MODEL_FILE.exists() or not _VECTORIZER_FILE.exists():
        return False
    try:
        with open(_MODEL_FILE, "rb") as f:
            _model = pickle.load(f)
        with open(_VECTORIZER_FILE, "rb") as f:
            _vectorizer = pickle.load(f)
        return True
    except Exception:
        return False


def classify(subject: str, body: str) -> dict | None:
    """
    Classify an email using the trained ML model.

    Returns a dict like {"type": "marketing", "confidence": 0.91}
    or None if no model is available.
    """
    if not _load():
        return None

    text = subject + " " + body
    X = _vectorizer.transform([text])
    label = _model.predict(X)[0]

    # predict_proba gives confidence scores for each class
    proba = _model.predict_proba(X)[0]
    confidence = float(max(proba))

    return {
        "type": label,
        "confidence": round(confidence, 3),
        "source": "ml",
    }


def model_available() -> bool:
    """Return True if a trained model exists on disk."""
    return _MODEL_FILE.exists() and _VECTORIZER_FILE.exists()
