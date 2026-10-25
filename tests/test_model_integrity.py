"""mvp-3 K06: a tampered model pickle is refused, and nothing writes models at runtime."""

import builtins
import shutil
import uuid
from pathlib import Path

import pytest

import api.routes as routes
from belem_converse.classifiers import intent_classifier_TFIDF_simple as tfidf
from belem_converse.classifiers.intent_classifier_TFIDF_simple import SimpleTFIDFIntentClassifier

MODELS_DIR = Path(tfidf.__file__).parent / "models"


def classifier_over(directory):
    clf = SimpleTFIDFIntentClassifier()
    clf.model_dir = directory
    return clf


@pytest.fixture
def models_copy(tmp_path):
    shutil.copytree(MODELS_DIR, tmp_path / "models")
    return tmp_path / "models"


def pickle_in(directory):
    return next(directory.glob("*.pkl"))


def test_real_model_loads():
    assert classifier_over(MODELS_DIR)._load_models() is True


def test_tampered_pickle_is_refused(models_copy):
    pkl = pickle_in(models_copy)
    pkl.write_bytes(pkl.read_bytes() + b"\x00")

    with pytest.raises(tfidf.ModelIntegrityError):
        classifier_over(models_copy).train()


def test_pickle_without_a_checksum_is_refused(models_copy):
    checksum = pickle_in(models_copy).with_name(pickle_in(models_copy).name + ".sha256")
    checksum.unlink(missing_ok=True)

    with pytest.raises(tfidf.ModelIntegrityError):
        classifier_over(models_copy).train()


def test_training_does_not_write_models(tmp_path):
    clf = classifier_over(tmp_path)

    clf.train()

    assert clf.is_trained
    assert list(tmp_path.iterdir()) == []


def test_chat_writes_nothing_into_the_models_directory(client, monkeypatch):
    monkeypatch.setattr(routes, "_intent_classifier", None)
    monkeypatch.setattr(routes, "_query_planner", None)
    writes = []
    real_open = builtins.open

    def spy(file, mode="r", *args, **kwargs):
        if any(c in mode for c in "wax+") and MODELS_DIR in Path(file).resolve().parents:
            writes.append(str(file))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", spy)
    monkeypatch.setattr(Path, "write_bytes", lambda self, *a, **k: writes.append(str(self)))

    response = client.post(
        "/api/chat",
        json={"session_id": str(uuid.uuid4()), "message": "bares abertos agora", "language": "pt-BR"},
    )

    assert response.status_code == 200
    assert writes == []
