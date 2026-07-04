"""マイクからの録音を扱うモジュール(完全ローカル・プッシュトゥトーク方式)。"""
from __future__ import annotations

import numpy as np
import sounddevice as sd

# faster-whisperは16kHzモノラルのfloat32配列をそのまま受け付けられる
SAMPLE_RATE = 16000


def record_until_enter() -> np.ndarray:
    """Enterキーで録音を開始し、もう一度Enterキーを押すまで録音するプッシュトゥトーク方式。

    戻り値は16kHzモノラルのfloat32 numpy配列(1次元)。
    """
    frames: list[np.ndarray] = []
    recording = False

    def callback(indata: np.ndarray, frame_count: int, time_info, status) -> None:
        if recording:
            frames.append(indata.copy())

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=callback,
    )

    with stream:
        input("🎤 Enterキーを押すと録音を開始します...")
        recording = True
        input("🔴 録音中... 話し終わったらEnterキーを押してください...")
        recording = False

    if not frames:
        return np.zeros(0, dtype="float32")
    return np.concatenate(frames, axis=0).flatten()
