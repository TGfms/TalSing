# from pydub import AudioSegment
# from pydub.playback import play
# # from kivy.core.audio import SoundLoader

# def playdouble(audio1, audio2):
#     sound1 = AudioSegment.from_mp3(audio1)
#     sound2 = AudioSegment.from_mp3(audio2)

#     combined = sound1.overlay(sound2, position=65) # positionでインスト音源とのずれを補正
#     play(combined)

# # def playrefer(genreList):
# #     soundList = [SoundLoader.load(f'forSynth/refer_wav/{genre}.wav' for genre in genreList)]

# from pydub import AudioSegment
# from pydub.playback import play
# import tempfile
# import os
# from pathlib import Path

import numpy as np
from scipy.io import wavfile
import sounddevice as sd
from ipdb import set_trace as ipst

def playdouble(wav1, wav2):
    sr1, data1 = wavfile.read(wav1)
    sr2, data2 = wavfile.read(wav2)
    assert sr1 == sr2 # サンプリングレート確認

    # 長さ揃え（短い方に合わせる）
    min_len = min(len(data1), len(data2))
    data1 = data1[:min_len]
    data2 = data2[:min_len]

    # wav1の音量を上げる
    gain1 = 1.5
    data2 = (data2.astype(np.float32) * gain1).astype(data2.dtype)

    # ステレオ化
    data_stereo = [data1, data2]
    # for id, data_raw in enumerate([data1, data2]):
    #     if data_raw.ndim == 1:
    #         data_stereo[id] = np.stack([data_raw, data_raw], axis=-1)
    for id, data_raw in enumerate([data1, data2]):
        if data_raw.ndim == 1:
            data_stereo[id] = np.stack([data_raw, data_raw], axis=-1)


    # 合成（オーバーレイ）
    combined = data_stereo[0].astype(np.int32) + data_stereo[1].astype(np.int32)

    # クリップ（16bitの場合）
    combined = np.clip(combined, -32768, 32767).astype(np.int16)

    # 保存
    wavfile.write("combined.wav", sr1, combined)

    # 再生
    sd.play(combined, sr1)
    sd.wait()