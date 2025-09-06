import sounddevice as sd
import numpy as np
import threading
import soundfile as sf
import scipy.signal as sp
from scipy.io.wavfile import write, read
from sklearn.decomposition import FastICA
from speechbrain.pretrained import SpectralMaskEnhancement
import torchaudio
import sys
from pathlib import Path
import alkana
from ipdb import set_trace as ipst
from sudachipy import Dictionary
from ruamel.yaml import YAML
yaml = YAML()  
yaml.preserve_quotes = True  # クォートの保持
yaml.indent(mapping=2, sequence=4, offset=2)  # インデント調整

# from functions import config
import functions.ica_sep as ica

sys.path.append(str(Path(__file__).resolve().parent.parent))
# import nnsvs_gui

# load config
with open('functions/config.yaml', 'r', encoding="utf-8") as f:
    data = yaml.load(f)
    ica_type = data["ica_type"]

alphabet = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', 'x', 'y', 'z', \
            'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
alp_kana = ['えー', 'びー', 'しー', 'でぃー', 'いー', 'えふ', 'じー', 'えいち', 'あい', 'じぇー', 'けー', 'える', 'えむ', 'えぬ', 'おー', 'ぴー', 'きゅー', 'あーる', 'えす', 'てぃー', 'ゆー', 'ぶい', 'だぶりゅー', 'えっくす', 'わい', 'じー']

# downsample = 10
# length = int(1000 * 44100 / (1000 * downsample))

# plotdata = np.zeros(length)
plotdata = []

# コールバック関数（マイクから入力される度に呼び出される）
def callback(indata, frames, time, status):
    # indata.shape=(n_samples, n_channels)
    global plotdata
    # plotdata = np.append(plotdata, indata.T)
    plotdata.append(indata.copy())

def main():
    updateConfig('recognition', False)

    # 前回のデータが残っているためplotdataをリセット。
    global plotdata
    # plotdata = np.zeros(length)
    plotdata = []

    with open('functions/config.yaml', 'r', encoding="utf-8") as f:
        flag = yaml.load(f)

        # デバイスのリストを取得し、デフォルトデバイスを設定
        device_list = sd.query_devices()
        sd.default.device = flag['InOutSetup'] # 使用したいデバイスの読み込み（Input, Outputそれぞれ）
        print(device_list)

        if flag['recording'] == True:
            # ストリームの設定とプロットの開始
            stream = sd.InputStream(
                samplerate=44100,
                channels=1, # マイク1本の場合は1
                dtype='float32',
                callback=callback # コールバック関数呼び出し
            )

    rec_flag_copy = True
    with stream:
        while rec_flag_copy: # recordingがTrueであるかぎりstreamが開かれ続ける
            with open('functions/config.yaml', 'r', encoding="utf-8") as f:
                rec_flag_copy = yaml.load(f)['recording']

def save_wav():
    print('Saving.')
    filename = "rec_raw_single.wav"
    audio_data = np.concatenate(plotdata, axis=0)
    sf.write(filename, audio_data, 44100, subtype='PCM_24')
    print('Saved.')

def separate(model):
    print('Start Text Recognition.')
    voice = "rec_raw_single.wav"
    voice_removed = "rec_removed_single.wav"

    # ノイズ除去
    enhancer = SpectralMaskEnhancement.from_hparams(
        source="speechbrain/metricgan-plus-voicebank",
        savedir="pretrained_models/metricgan-plus-voicebank"
    )

    # ノイズ除去の実行
    enhanced = enhancer.enhance_file(voice)
    # 出力ファイルの保存（16bit PCM）
    torchaudio.save(voice_removed, enhanced.unsqueeze(0), 16000)

    # voice recognition
    segments, info = model.transcribe(voice, beam_size=5, language="ja") # 現状は日本語で固定
    print('Finish Text Recognition.')
    print("Detected language '%s' with probability %f" % (info.language, info.language_probability))
    result = ''
    for segment in segments:
        print("[%.2fs -> %.2fs] %s" % (segment.start, segment.end, segment.text))
        result += segment.text
    result = result.replace(' ', '')
    result = result.replace('　', '')
    result = result.replace('、', '')
    result = result.replace('。', '')
    result = result.replace('?', '')
    result = result.replace('!', '')

    # # Sudachiで形態素解析（カタカナ変換）
    # tokenizer = Dictionary().create()
    # tokens = tokenizer.tokenize(result)

    # # すべての単語をカタカナに変換
    # katakana_text = "".join(token.reading_form() if token.reading_form() != "*" else token.surface() for token in tokens)

    # stock = ''
    # result_fin = ''
    # for s in result:
    #     if s in alphabet:
    #         stock += s
    #     else:
    #         if stock != '':
    #             stock = alkana.get_kana(stock)
    #             print(f'Add {stock}')
    #             result_fin += stock
    #             stock = ''
    #         print(f'Add {s}')
    #         result_fin += s

    print(f"result={result}")
    updateConfig('extracted_text', result)
    updateConfig('recognition', True)

# yaml更新用関数
def updateConfig(key, value):
    with open('functions/config.yaml', 'r', encoding="utf-8") as f:
        data = yaml.load(f)

    data[key] = value

    with open('functions/config.yaml', 'w', encoding="utf-8") as f:
        yaml.dump(data, f)
