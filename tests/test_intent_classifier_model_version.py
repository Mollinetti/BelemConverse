"""CI gate for the intent classifier's pickled model artifact.

The classifier's :data:`SimpleTFIDFIntentClassifier.MODEL_VERSION` constant
and the pickled model file under ``belem_converse/classifiers/models/`` MUST
move in lockstep:

- Bumping the code constant without checking in a freshly trained pickle
  causes every consumer to retrain on first import — slow, non-deterministic
  if training data shifts mid-process, and a confusing surprise in CI.
- Checking in a stale pickle (older than the constant) causes the loader to
  silently fall through to retraining; same downsides.
- Checking in a pickle ahead of the constant means dead bytes in the repo.

These tests catch all three cases at PR time, before merge.

This file is intentionally lightweight: no model training, no inference,
no scikit-learn import beyond what the loader already needs. It's pure
file-existence and version-string assertions, so it runs in well under a
second and never depends on a cached model being present at test time.

Per open question #1 in
``docs/spec/12-intent-classifier-improvement-plan.md`` (answered "yes").
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from belem_converse.classifiers.intent_classifier_TFIDF_simple import (
    SimpleTFIDFIntentClassifier,
)


_MODELS_DIR = Path(__file__).parent.parent / "belem_converse" / "classifiers" / "models"


def _expected_pickle_path() -> Path:
    return _MODELS_DIR / f"simple_tfidf_models_v{SimpleTFIDFIntentClassifier.MODEL_VERSION}.pkl"


def test_pickled_model_for_current_version_exists():
    """A pickle at the version named by ``MODEL_VERSION`` must be checked in.

    If this fails, regenerate via:

        python -c "from belem_converse.classifiers.intent_classifier_TFIDF_simple \\
            import SimpleTFIDFIntentClassifier; SimpleTFIDFIntentClassifier().train()"

    and commit the resulting ``.pkl``.
    """
    expected = _expected_pickle_path()
    assert expected.exists(), (
        f"No pickled model found for MODEL_VERSION={SimpleTFIDFIntentClassifier.MODEL_VERSION!r}. "
        f"Expected file: {expected}. "
        "Either regenerate and commit it, or revert the MODEL_VERSION bump."
    )


def test_pickled_model_version_matches_code():
    """The version field stored inside the pickle must match the code constant.

    A mismatch means the file on disk is from a different code revision —
    loading it would silently trigger a retrain in production code.
    """
    expected = _expected_pickle_path()
    if not expected.exists():
        pytest.skip("Pickle missing — covered by test_pickled_model_for_current_version_exists")

    with expected.open("rb") as f:
        model_data = pickle.load(f)

    file_version = model_data.get("version")
    assert file_version == SimpleTFIDFIntentClassifier.MODEL_VERSION, (
        f"Pickle reports version={file_version!r} but code says "
        f"MODEL_VERSION={SimpleTFIDFIntentClassifier.MODEL_VERSION!r}. "
        f"File: {expected}. Regenerate the pickle so the two agree."
    )


def test_no_orphan_model_pickles_in_repo():
    """No pickled models for OTHER versions should be checked in.

    Old version pickles are dead weight (the loader ignores them via the
    version check) and waste disk in clones. If you really want to keep
    one for rollback purposes, exempt it explicitly here with a comment
    explaining why — don't just relax the test.
    """
    if not _MODELS_DIR.exists():
        pytest.skip("Models directory does not exist yet")

    current_pkl = _expected_pickle_path().name
    pickles = sorted(p.name for p in _MODELS_DIR.glob("simple_tfidf_models_v*.pkl"))
    orphans = [p for p in pickles if p != current_pkl]

    assert not orphans, (
        f"Orphan model pickles found in {_MODELS_DIR}: {orphans}. "
        f"Current MODEL_VERSION is {SimpleTFIDFIntentClassifier.MODEL_VERSION!r}, "
        f"so only {current_pkl!r} should be present. Delete the orphans."
    )
