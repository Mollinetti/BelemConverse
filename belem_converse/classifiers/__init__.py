"""
Classifiers module for BelemConverse.

Contains intent detection and category classification components.
"""

from .intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

__all__ = [
    'SimpleTFIDFIntentClassifier'
]


