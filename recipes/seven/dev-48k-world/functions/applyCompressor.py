import os
from os.path import join
import librosa
import soundfile as sf
from scipy.signal import lfilter
import numpy as np
# from MyLib.orgsvs2 import OrgWaves
import sys

inwav_path = sys.argv[1]

def PyComp(y, sr, threshold_db=-20.0, ratio=4.0, attack_ms=10.0, release_ms=100.0):
    """
    シンプルなRMSベースのオーディオコンプレッサ。
    """
    # パラメータ設定
    frame_size = int(sr * 0.01)  # 10msごとの処理
    attack_coeff = np.exp(-1.0 / (sr * (attack_ms / 1000.0)))
    release_coeff = np.exp(-1.0 / (sr * (release_ms / 1000.0)))

    envelope = np.zeros_like(y)
    gain = np.ones_like(y)

    # 信号の振幅 envelope を推定
    for i in range(1, len(y)):
        rectified = abs(y[i])
        if rectified > envelope[i - 1]:
            envelope[i] = attack_coeff * envelope[i - 1] + (1 - attack_coeff) * rectified
        else:
            envelope[i] = release_coeff * envelope[i - 1] + (1 - release_coeff) * rectified

    # dBスケールに変換してしきい値で圧縮
    envelope_db = 20 * np.log10(np.maximum(envelope, 1e-8))
    over_threshold_db = np.maximum(envelope_db - threshold_db, 0)
    gain_db = -over_threshold_db * (1 - 1 / ratio)
    gain = 10 ** (gain_db / 20.0)

    # ゲインを適用
    y_compressed = y * gain

    return y_compressed

if __name__ == '__main__':
    # --- 音声読み込み ---
    y, sr = librosa.load(inwav_path, sr=None)

    # --- 圧縮処理 ---
    y_compressed = PyComp(y, sr)

    # --- 音量の正規化（オプション） ---
    y_compressed = y_compressed / np.max(np.abs(y_compressed)) * 0.99

    # --- 書き出し ---
    sf.write(inwav_path, y_compressed, sr)

    print(f"コンプレッサー適用済み音声を保存しました: {inwav_path}")

    # w1 = OrgWaves()
    # w2 = OrgWaves()
    # w1.analyzeWave(wav_bef_path)
    # w2.analyzeWave(wav_aft_path)
    # w1.dispWave("w1.png")
    # w2.dispWave("w2.png")