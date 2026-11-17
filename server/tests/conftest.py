import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="kontho-test-")
os.environ.update({
    "KONTHO_DATA_DIR": _tmp,
    "KONTHO_TTS_ENGINE": "mock",
    "KONTHO_STT_ENGINE": "mock",
    "KONTHO_SFX_ENGINE": "mock",
    "KONTHO_ISOLATION_ENGINE": "mock",
    "KONTHO_TRANSLATE_ENGINE": "mock",
    "KONTHO_WEB_DIR": str(Path(_tmp) / "noweb"),
})

from fastapi.testclient import TestClient  # noqa: E402

from kontho.main import create_app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(create_app())


@pytest.fixture(scope="session")
def speech_wav(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("media") / "speech.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
                    "-ar", "24000", str(path)], check=True)
    return path


@pytest.fixture(scope="session")
def video_file(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("media") / "clip.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:d=5",
                    "-f", "lavfi", "-i", "sine=frequency=300:duration=5", "-shortest", "-c:v", "libx264",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path


def wait_job(client, dub_id, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        d = client.get(f"/v1/dubbing/{dub_id}").json()
        if d["status"] in ("dubbed", "failed"):
            return d
        time.sleep(0.2)
    raise TimeoutError(dub_id)
