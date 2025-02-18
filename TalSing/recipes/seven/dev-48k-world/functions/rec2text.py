import sounddevice as sd
import numpy as np
import threading
import soundfile as sf
import scipy.signal as sp
from scipy.io.wavfile import write, read
from sklearn.decomposition import FastICA
from faster_whisper import WhisperModel
import sys
from pathlib import Path
import alkana
from ipdb import set_trace as ipst
from sudachipy import Dictionary
from ruamel.yaml import YAML
yaml = YAML()  
yaml.preserve_quotes = True  # クォートの保持
yaml.indent(mapping=2, sequence=4, offset=2)  # インデント調整

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

downsample = 10
length = int(1000 * 44100 / (1000 * downsample))

plotdata_L = np.zeros(length)
plotdata_R = np.zeros(length)

# コールバック関数（マイクから入力される度に呼び出される）
def callback(indata, frames, time, status):
    # indata.shape=(n_samples, n_channels)
    global plotdata_L, plotdata_R
    plotdata_L = np.append(plotdata_L, indata.T[0])
    plotdata_R = np.append(plotdata_R, indata.T[1])

def main():
    updateConfig('recognition', False)

    # 前回のデータが残っているためplotdataをリセット。
    global plotdata_L, plotdata_R
    plotdata_L = np.zeros(length)
    plotdata_R = np.zeros(length)
    with open('functions/flag.yaml', 'r') as f:
        flag = yaml.load(f)

        # デバイスのリストを取得し、デフォルトデバイスを設定
        device_list = sd.query_devices()
        sd.default.device = flag['InOutSetup'] # 使用したいデバイスの読み込み（Input, Outputそれぞれ）（設定はflag.yamlから）
        print(device_list)

        if flag['recording'] == True:
            # ストリームの設定とプロットの開始
            stream = sd.InputStream(
                channels=2, # マイク1本の場合は1
                dtype='float32',
                callback=callback # コールバック関数呼び出し
            )

    rec_flag_copy = True
    with stream:
        while rec_flag_copy: # recordingがTrueであるかぎりstreamが開かれ続ける
            with open('functions/config.yaml', 'r') as f:
                rec_flag_copy = yaml.load(f)['recording']

def save_wav():
    print('saving.')
    filename_L = "rec_raw_L.wav"
    filename_R = "rec_raw_R.wav"
    sf.write(filename_L, plotdata_L, 44100, subtype='PCM_24')
    sf.write(filename_R, plotdata_R, 44100, subtype='PCM_24')
    print('saved.')

def separate(model):
    # 音源（雑音）分離 1:（ICA）
    if ica_type == 0:
        X = np.c_[plotdata_L,  plotdata_R]

        X /= X.std(axis=0) #standardize data
        print((X.T).shape)

        #短時間フーリエ変換を行う
        f,t,stft_data=sp.stft(X.T,fs=44100,window="hann",nperseg=1024)

        #ICAの繰り返し回数
        n_ica_iterations=200

        #ICAの分離フィルタを初期化
        n_sources=2
        N=1024
        Nk=int(N/2+1)
        Wica=np.zeros(shape=(Nk,n_sources,n_sources),dtype=np.complex128)
        Wica=Wica+np.eye(n_sources)[None,...]

        Wica,s_ica,cost_buff=ica.execute_natural_gradient_ica(stft_data,Wica,mu=0.1,n_ica_iterations=n_ica_iterations,is_use_non_holonomic=False)

        permutation_index_result=ica.solver_inter_frequency_permutation(s_ica)

        y_ica=ica.projection_back(s_ica,Wica)

        for k in range(Nk):
            y_ica[:,:,k,:]=y_ica[:,permutation_index_result[k],k,:]

        t,y_ica=sp.istft(y_ica[0,...],fs=44100,window="hann",nperseg=N)

        write("ica_1.wav", rate=44100, data=(y_ica[0,:]* 32767 / max(np.absolute(y_ica[0,:]))).astype(np.int16))
        write("ica_2.wav", rate=44100, data=(y_ica[1,:]* 32767 / max(np.absolute(y_ica[1,:]))).astype(np.int16))

    
    # 音源（雑音）分離 2: (FastICA)
    elif ica_type == 1:
        X = np.c_[plotdata_L,  plotdata_R]

        ica = FastICA(n_components=2)
        S_=ica.fit_transform(X)

        write("sep_1.wav",rate=44100,data=(S_[:,0] * 32767 / max(np.absolute(S_[:,0]))).astype(np.int16))
        write("sep_2.wav",rate=44100,data=(S_[:,1] * 32767 / max(np.absolute(S_[:,1]))).astype(np.int16))


    # ターゲットデータの推定
    if ica_type == 0:
        audio_file = ["ica_1.wav","ica_2.wav"]
    else:
        audio_file = ["sep_1.wav","sep_2.wav"]
    voice = []
    rms = 0
    for f in audio_file:
        sr, audio = read(f)
        # 音量レベルの計測 & 比較
        if rms < np.sqrt(np.mean(np.square(audio))):
            rms = np.sqrt(np.mean(np.square(audio)))
            voice = f
    print(f"Target wav : {voice}")

    # voice recognition
    segments, info = model.transcribe(voice, beam_size=5)
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

    # Sudachiで形態素解析（カタカナ変換）
    tokenizer = Dictionary().create()
    tokens = tokenizer.tokenize(result)

    # すべての単語をカタカナに変換
    katakana_text = "".join(token.reading_form() if token.reading_form() != "*" else token.surface() for token in tokens)

    stock = ''
    result_fin = ''
    for s in result:
        if s in alphabet:
            stock += s
        else:
            if stock != '':
                stock = alkana.get_kana(stock)
                print(f'Add {stock}')
                result_fin += stock
                stock = ''
            print(f'Add {s}')
            result_fin += s

    print(f"result={katakana_text}")
    updateConfig('extracted_text', katakana_text)
    updateConfig('recognition', True)

# yaml更新用関数
def updateConfig(key, value):
    with open('functions/config.yaml', 'r', encoding="utf-8") as f:
        data = yaml.load(f)

    data[key] = value

    with open('functions/config.yaml', 'w', encoding="utf-8") as f:
        yaml.dump(data, f)