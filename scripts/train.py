"""
train.py — Train a text classifier on labelled emails and save the model.

Uses TF-IDF to turn email text into numbers, then trains a Logistic
Regression classifier to predict the label. Simple, fast, and explainable.

Usage:
    python train.py              # train on all labelled emails
    python train.py --min 50     # only train if at least 50 labelled examples exist

Output:
    ml/model.pkl        — the trained classifier
    ml/vectorizer.pkl   — the TF-IDF vectorizer (must ship with the model)
"""

import json
import pickle
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.model_selection import cross_val_score
    from sklearn.metrics import classification_report
    import numpy as np
except ImportError:
    print("scikit-learn not installed. Run: pip install scikit-learn numpy --user")
    sys.exit(1)

import argparse

DATA_FILE = Path(__file__).parent / "emails.jsonl"
ML_DIR = Path(__file__).parent.parent / "ml"
MODEL_FILE = ML_DIR / "model.pkl"
VECTORIZER_FILE = ML_DIR / "vectorizer.pkl"


def load_labelled():
    """Return (texts, labels) for all emails with a human_label."""
    if not DATA_FILE.exists():
        print("emails.jsonl not found. Run fetch_training_data.py first.")
        sys.exit(1)

    texts, labels = [], []
    with open(DATA_FILE, encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            label = e.get("human_label")
            if not label:
                continue
            # Combine subject and body as the input text
            text = e.get("subject", "") + " " + e.get("body", "")
            texts.append(text)
            labels.append(label)

    return texts, labels


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min", type=int, default=20,
                        help="Minimum labelled examples required to train (default: 20)")
    args = parser.parse_args()

    texts, labels = load_labelled()
    print(f"Labelled examples: {len(texts)}")

    if len(texts) < args.min:
        print(f"Not enough labelled data (need {args.min}, have {len(texts)}).")
        print("Run label.py to add more labels first.")
        sys.exit(1)

    # Show class distribution
    counts = Counter(labels)
    print("\nLabel distribution:")
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {label}: {count}")

    # Warn if any class has very few examples
    for label, count in counts.items():
        if count < 5:
            print(f"\nWarning: '{label}' has only {count} examples — results may be unreliable.")

    print("\nTraining...")

    # TF-IDF: turns words into weighted numbers based on how often they appear
    # sublinear_tf dampens very frequent words; ngram_range captures short phrases
    vectorizer = TfidfVectorizer(
        sublinear_tf=True,
        ngram_range=(1, 2),
        max_features=10000,
        min_df=2,
    )
    X = vectorizer.fit_transform(texts)

    # Logistic Regression: a simple, fast classifier that works well for text
    # class_weight='balanced' compensates for unequal class sizes
    model = LogisticRegression(
        max_iter=1000,
        class_weight="balanced",
        C=1.0,
    )

    # Cross-validation: train on 80% and test on 20%, 5 times
    # This gives a more honest accuracy estimate than a single train/test split
    if len(texts) >= 10:
        cv_folds = min(5, len(texts) // max(counts.values(), 1) + 1) if len(texts) < 50 else 5
        cv_folds = max(2, cv_folds)
        scores = cross_val_score(model, X, labels, cv=cv_folds, scoring="f1_weighted")
        print(f"\nCross-validation F1 ({cv_folds}-fold): {scores.mean():.2f} ± {scores.std():.2f}")
        if scores.mean() < 0.6:
            print("Warning: accuracy is low. Add more labelled examples and try again.")

    # Train on the full dataset for the final model
    model.fit(X, labels)

    # Save
    ML_DIR.mkdir(exist_ok=True)
    with open(MODEL_FILE, "wb") as f:
        pickle.dump(model, f)
    with open(VECTORIZER_FILE, "wb") as f:
        pickle.dump(vectorizer, f)

    print(f"\nModel saved to {MODEL_FILE}")
    print(f"Vectorizer saved to {VECTORIZER_FILE}")

    # Show the top words driving each class
    print("\nTop words per class:")
    feature_names = vectorizer.get_feature_names_out()
    for label in model.classes_:
        idx = list(model.classes_).index(label)
        top = np.argsort(model.coef_[idx])[-8:][::-1]
        words = [feature_names[i] for i in top]
        print(f"  {label}: {', '.join(words)}")

    print('\nRun "python gmail_test.py" to see the model in action.')


if __name__ == "__main__":
    main()
