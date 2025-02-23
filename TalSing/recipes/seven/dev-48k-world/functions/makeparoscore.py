# import musicxml
# from musicxml.parser.parser import parse_musicxml
import xml.etree.ElementTree as ET
import pyopenjtalk
import jaconv
from janome.tokenizer import Tokenizer
import MeCab
import ipadic
import jamorasep
import sys
import os
from os.path import join
import copy
import re
import json
from tqdm import tqdm
from ipdb import set_trace as ipst
from ruamel.yaml import YAML
yaml = YAML()  
yaml.preserve_quotes = True  # クォートの保持
yaml.indent(mapping=2, sequence=4, offset=2)  # インデント調整

# load config
with open('functions/config.yaml', 'r') as f:
    data = yaml.load(f)
    editmode = data["editmode"]
    splitmode = data["splitmode"]
    force_enbed_with_la = data["force_enbed_with_la"]
    use_continuous_vowel = data["use_continuous_vowel"]

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

small_list = ["ャ", "ュ", "ョ", "ァ", "ィ", "ゥ", "ェ", "ォ", "ッ", "ゃ", "ゅ", "ょ", "ぁ", "ぃ", "ぅ", "ぇ", "ぉ", "っ"]
type_list = ["64th", "32nd", "16th", "eighth", "quarter", "half", "whole"]
oct_scale = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
phoneme_dict = open(join(current_dir, 'phoneme_dict.json'), 'r')
phoneme_list = json.load(phoneme_dict)
vowels = ["a", "i", "u", "e", "o", "N", "cl"]

xml_path = sys.argv[1]
textfile_path = sys.argv[2]
text = sys.argv[3]

class xmlinfo:
    def __init__(self):
        self.num_part = 0 # パート数（特に使用しない）
        self.num_measure = 0 # 小節数
        self.num_note = 0 # ノート数（タイで繋がったノートもカウント）
        self.num_pitch = 0 # ピッチ保有ノート数
        self.num_mora = 0 # モーラ数（歌詞が対応するノートのみカウント）
        self.durations_mora = [] # デフォルト楽譜のノートのduration値
        self.durations_mora_splitable = [] # ↑そのうち分割可能な(上げ弓記号がついていない)ノート
        self.new_durations_mora = [] # 入力テキストのモーラ数対応後のduration値
        self.breathbatch = [] # ブレス記号で分けられた各区間のノート（モーラ）数
        self.breathbatch_start_measure = [] # 各breathbatchの最初のノートが存在する小節番号
        self.accent_core = [] # アクセント核（現状不使用）

    def showinfo(self):
        print(f"Part: {self.num_part}, \
              Measure: {self.num_measure}, \
              Note: {self.num_note}, \
              Pitch: {self.num_pitch}, \
              Mora: {self.num_mora}, \
              Len of durations_mora: {len(self.durations_mora)}, \
              Len of durations_mora_splitable: {len(self.durations_mora_splitable)}, \
              Breathbatch : {self.breathbatch} \
              Start measure of breathbach : {self.breathbatch_start_measure} \
              Accent core : {self.accent_core}")
        
    def get_noteinfo(note):
        step = note.find('pitch').find('step')
        octave = note.find('pitch').find('octave')
        dur = note.find('duration')
        voice = note.find('voice')
        type = note.find('type')
        if note.find('dot') != None: dot = True
        else: dot = False
        stem = note.find('stem')
        ly_num = note.find('lyric').get('number')
        syl = note.find('lyric').find('syllabic')

        return step, octave, dur, voice, type, dot, stem, ly_num, syl
    
    def copy_note(note): # not used
        new_note = ET.Element('note')
        for iter in note:
            note_param = ET.SubElement(new_note, iter.tag)
            note_param.text = iter.text 

        return new_note

    def revise_xml(self, xml, text, num_over): # 長いノートから
        # 不足しているモーラ数だけノートを分割
        self.new_durations_mora = copy.copy(self.durations_mora) # モーラごとのdurationを格納した配列をコピー
        for i in range(num_over):
            max_dur_index = self.new_durations_mora.index(max(self.new_durations_mora)) # この時点でのdurationが一番長いモーラが先頭から何番目か
            notecount = 0 # ターゲットとなるnote（lyricがあるものだけカウント）
            for part in xml.findall('part'):
                for measure in part.findall('measure'):
                    if measure.find('print') != None:
                        pri_flag = True
                    else:
                        pri_flag = False
                    for note in measure.findall('note'):
                        for index, lyric in enumerate(note.findall('lyric')):
                            if notecount == max_dur_index:
                                # <note>要素を編集
                                if note.find('dot') != None: # 付点ノートの場合
                                    note.remove(note.find('dot')) # まず付点を取り除く
                                    new_note = copy.deepcopy(note) # noteを複製し、
                                    new_note.find('duration').text = str(int(int(note.find('duration').text) * 2 / 3)) # 複製したnoteのdurationを元の2/3倍にする
                                    self.new_durations_mora.insert(max_dur_index, int(max(self.new_durations_mora) * 2 / 3)) # 新しいモーラ長リストに追加
                                    note.find('duration').text = str(int(int(note.find('duration').text) / 3)) # 元のnoteのdurationを1/3倍にする
                                    self.new_durations_mora[max_dur_index + 1] = int(max(self.new_durations_mora) / 3) # 新しいモーラ長リストの値を1/3倍に書き換える
                                    note.find('type').text = type_list[type_list.index(note.find('type').text) - 1] # note(new_noteではない)のタイプをtype_listの一つ小さな値にする Ex) 4分音符->8分音符
                                else: # 付点ノートでない場合
                                    note.find('duration').text = str(int(int(note.find('duration').text) / 2)) # noteのdurationを1/2倍にする
                                    self.new_durations_mora.insert(max_dur_index, int(max(self.new_durations_mora) / 2)) # 新しいモーラ長リストに1/2倍の値を追加
                                    self.new_durations_mora[max_dur_index + 1] = int(max(self.new_durations_mora) / 2) # 新しいモーラ長リストの値を1/2倍に書き換える
                                    note.find('type').text = type_list[type_list.index(note.find('type').text) - 1] # noteのタイプをtype_listの一つ小さな値にする Ex) 4分音符->8分音符
                                    new_note = copy.deepcopy(note) # 上記の変更を適用したnoteを複製

                                # 新しい<note>要素を追加
                                if pri_flag == True:
                                    measure.insert(index + 1, new_note) # printブロックがmeasureの子要素リストの先頭にある場合+1
                                else:
                                    measure.insert(index, new_note) # printブロックがmeasureの子要素リストの先頭にない場合+1しない
                                print(f"Note durations : {self.new_durations_mora}")
                                
                                break
                            notecount += 1
                        else:
                            continue
                        break
                    else:
                        continue
                    break
                else:
                    continue
                break

        self.replace_lyric(xml, text)

    # 足りないモーラ数だけノートを分割
    def split_notes(self, xml, start_note_id, bunsetsu, breath):
        num_over = len(get_moralist(bunsetsu)) - breath # 足りないモーラ数
        print(f"Split num : {num_over} (Input notes : {len(get_moralist(bunsetsu))}, Original notes : {breath})")
        tar_dur_list = copy.copy(self.durations_mora_splitable[start_note_id : start_note_id + breath]) # duration値を格納したリスト

        # ノート分割処理
        revise_num = 0
        while revise_num < num_over:
            print(f"Current durations list : {tar_dur_list}")
            tar_dur_id = tar_dur_list.index(max(tar_dur_list))
            print(f"The index of max duration : {tar_dur_id}")
            notecount = 0
            for part in xml.findall('part'):
                    for measure in part.findall('measure'):
                        if measure.find('print') != None:
                            pri_flag = True
                        else:
                            pri_flag = False
                        for index, note in enumerate(measure.findall('note')):
                            if note.find('lyric') != None:
                                if notecount == tar_dur_id + start_note_id:
                                    if note.find('dot') != None:
                                        note.remove(note.find('dot')) # まず付点を取り除く
                                        new_note = copy.deepcopy(note) # noteを複製し、
                                        new_note.find('duration').text = str(int(int(note.find('duration').text) * 2 / 3)) # 複製したnoteのdurationを元の2/3倍にする
                                        tar_dur_list.insert(tar_dur_id, int(max(tar_dur_list) * 2 / 3)) # 新しいモーラ長リストに追加
                                        note.find('duration').text = str(int(int(note.find('duration').text) / 3)) # 元のnoteのdurationを1/3倍にする
                                        tar_dur_list[tar_dur_id + 1] = int(max(tar_dur_list) / 3) # 新しいモーラ長リストの値を1/3倍に書き換える
                                        note.find('type').text = type_list[type_list.index(note.find('type').text) - 1] # note(new_noteではない)のタイプをtype_listの一つ小さな値にする Ex) 4分音符->8分音符
                                    else: # 付点ノートでない場合
                                        note.find('duration').text = str(int(int(note.find('duration').text) / 2)) # noteのdurationを1/2倍にする
                                        tar_dur_list.insert(tar_dur_id, int(max(tar_dur_list) / 2)) # 新しいモーラ長リストに1/2倍の値を追加
                                        tar_dur_list[tar_dur_id + 1] = int(max(tar_dur_list) / 2) # 新しいモーラ長リストの値を1/2倍に書き換える
                                        note.find('type').text = type_list[type_list.index(note.find('type').text) - 1] # noteのタイプをtype_listの一つ小さな値にする Ex) 4分音符->8分音符
                                        new_note = copy.deepcopy(note) # 上記の変更を適用したnoteを複製

                                    # 新しい<note>要素を追加
                                    if pri_flag == True:
                                        measure.insert(index + 1, new_note) # printブロックがmeasureの子要素リストの先頭にある場合+1
                                    else:
                                        measure.insert(index, new_note) # printブロックがmeasureの子要素リストの先頭にない場合+1しない
                                    revise_num += 1
                                    break
                                notecount += 1
                        else:
                            continue
                        break
                    else:
                        continue
                    break
            print(f"Split was done. ({revise_num}/{num_over})")

        # Update self.new_durations_mora
        del self.new_durations_mora[start_note_id : start_note_id + breath]
        del self.durations_mora_splitable[start_note_id : start_note_id + breath]
        for i in range(len(get_moralist(bunsetsu))):
            self.new_durations_mora.insert(start_note_id + i, tar_dur_list[i])
            self.durations_mora_splitable.insert(start_note_id + i, tar_dur_list[i])

        # 最後に歌詞を入れ替え
        self.replace_lyric_partial(xml, get_moralist(bunsetsu), start_note_id)

        return xml
    
    # 余ったノートを結合（使わない）
    def joint_notes(self, xml, start_note_id, bunsetsu_id, bunsetsu):
        breath = self.breathbatch[bunsetsu_id]
        start_measure = self.breathbatch_start_measure[bunsetsu_id]
        num_less = breath - len(get_moralist(bunsetsu))
        print(f"Joint num : {num_less} (Input notes : {len(get_moralist(bunsetsu))}, Original notes : {breath})")
        tar_dur_list = copy.copy(self.new_durations_mora[start_note_id : start_note_id + breath])
        tar_measure = start_measure
        wait_joint = False
        done_joint = 0
        while num_less > done_joint:
            print(f"- Current durations list : {tar_dur_list}")
            notecount = 0 # 通過した歌詞付きのノート
            min_dur = min(tar_dur_list)
            for part in xml.findall('part'):
                    for measure_id, measure in enumerate(part.findall('measure')):
                        if tar_measure <= measure_id:
                            for note_id, note in enumerate(measure.findall('note')):
                                if note.find('lyric') != None:
                                    print(f"Dur of now : {note.find('duration').text}, Min of list : {str(min_dur)}")
                                    print(f"Target measure : {tar_measure}")
                                    if wait_joint:
                                        if measure.findall('note')[note_id].find('duration').text == measure.findall('note')[note_id - 1].find('duration').text: # 前のノートと今のノートのdurationが同じなら
                                            print("Remove behind note.")
                                            print(f"Dur(before)={measure.findall('note')[note_id - 1].find('duration').text}, Type(before)={measure.findall('note')[note_id - 1].find('type').text}")
                                            measure.findall('note')[note_id - 1].find('duration').text = str(int(measure.findall('note')[note_id - 1].find('duration').text) * 2) # durationを2倍
                                            measure.findall('note')[note_id - 1].find('type').text = type_list[type_list.index(measure.findall('note')[note_id - 1].find('type').text) + 1] # typeを一つ大きく
                                            print(f"Dur(after)={measure.findall('note')[note_id - 1].find('duration').text}, Type(after)={measure.findall('note')[note_id - 1].find('type').text}")
                                            measure.remove(measure.findall('note')[note_id]) # 現在のノートを削除
                                        else: # 2つのdurationが異なる場合
                                            # ひとつ前/現在のノートにタイ（start/stop）をつける
                                            print("Connect two notes with tie.")
                                            notations_start = ET.SubElement(measure.findall('note')[note_id - 1], 'notations')
                                            tie_start = ET.SubElement(notations_start, 'tied')
                                            tie_start.set('type', 'start')

                                            notations_stop = ET.SubElement(note, 'notations')
                                            tie_stop = ET.SubElement(notations_stop, 'tied')
                                            tie_stop.set('type', 'stop')
                                            note.remove(note.find('lyric'))
                                            measure.findall('note')[note_id].find('pitch').find('step').text = measure.findall('note')[note_id - 1].find('pitch').find('step').text # 後のノートの音高を前と同じ音高に
                                            measure.findall('note')[note_id].find('pitch').find('octave').text = measure.findall('note')[note_id - 1].find('pitch').find('octave').text # 後のノートのオクターブを前と同じオクターブに
                                        wait_joint = False
                                        tar_dur_list[notecount] = tar_dur_list[notecount] + tar_dur_list[notecount - 1]
                                        del tar_dur_list[notecount - 1]
                                        print(f"notecount : {notecount}")

                                        done_joint += 1
                                        print(f"Joint was done. ({done_joint}/{num_less})")
                                        break
                                    elif note.find('duration').text == str(min_dur):
                                        # if note.find('dot') != None:
                                        print(f"target : {note.find('lyric').find('text').text}")
                                        add_duration = note.find('duration').text
                                        wait_joint = True
                                        tar_note_id = note_id
                                    notecount += 1
                        
                        else:
                            continue
                        break
                    else:
                         # tar_measure以降にmin_durが存在しなかったらtar_measureをリセット
                        print('Reset target measure.')
                        tar_measure = start_measure - 1
                    break
            tar_measure += 1

        return xml
    
    # 余ったノート分だけ歌詞列に母音を追加
    def add_vowels(self, xml, start_note_id, bunsetsu_id, bunsetsu):
        breath = self.breathbatch[bunsetsu_id]
        num_less = breath - len(get_moralist(bunsetsu))
        print(f"Add num : {num_less} (Input notes : {len(get_moralist(bunsetsu))}, Original notes : {breath})")

        new_bunsetsu = copy.copy(get_moralist(bunsetsu)) # 最終的に歌詞となるモーラを格納
        add_vowel_list = [[]] # bunsetsuの母音を格納する，1周するごとに中のリストを増やす
        lap = 0 # bunsetsuのすべてのモーラの母音を取得するごとに+1

        # add_vowel_list（追加する母音を格納したリスト）を作成
        for i in range(num_less):
            vowel_roma = jamorasep.parse(get_moralist(bunsetsu)[i % len(get_moralist(bunsetsu))], output_format = 'simple-ipa')[0][-1] # bunsetsuのi(% (bunsetsuのモーラ数))番目のモーラの母音を取得
            vowel_kana = jaconv.alphabet2kana(vowel_roma) # ひらがなに変換
            if vowel_kana == 'N':
                vowel_kana = 'ん'
            if i % len(get_moralist(bunsetsu)) == 0 and i > 1:
                add_vowel_list.append([])
                lap += 1
            add_vowel_list[lap].append(vowel_kana)

        for id, component in enumerate(add_vowel_list):
            for j in range(len(component)):
                new_bunsetsu.insert((j+1) * (id+2) - 1, add_vowel_list[id][j])

        # 作成した歌詞を反映
        self.replace_lyric_partial(xml, new_bunsetsu, start_note_id)
        
        return xml
    
    # 文節区切りの編集モード
    def revise_xml2(self, xml, text):
        # BreathBatch数（ブレスによって分割されるノートの集合）に合わせて新たな文節リストを作成する
        tar_bunsetsu = 0
        for index, num in enumerate(self.breathbatch):
            if len(text.bunsetsu_list) <= tar_bunsetsu:
                break
            text.connected_bunsetsu_list.append(text.bunsetsu_list[tar_bunsetsu])
            tar_bunsetsu += 1
            while len(text.connected_bunsetsu_list[index]) < num \
                    and len(text.bunsetsu_list) > tar_bunsetsu \
                    and len(text.connected_bunsetsu_list[index]) + len(text.bunsetsu_list[tar_bunsetsu]) <= num*2:
                text.connected_bunsetsu_list[index] += text.bunsetsu_list[tar_bunsetsu]
                tar_bunsetsu += 1
        print(f"連結文節長 : {[len(s) for s in text.connected_bunsetsu_list]}")
        print(f"連結済み文節 : {text.connected_bunsetsu_list}")

        # text.connected_bunsetsu_listそれぞれについてi)モーラが足りない場合　とii)モーラが余る場合で割り当て考える
        self.new_durations_mora = copy.copy(self.durations_mora) # モーラごとのdurationを格納した配列をコピー
        print(f"New durations mora(init) : {self.new_durations_mora}(len:{len(self.new_durations_mora)})")
        start_note_id = 0 # 処理の対象となるノートが（歌詞を含むノートのうち）始めから何番目か
        for index, bunsetsu in enumerate(text.connected_bunsetsu_list):
            if len(get_moralist(bunsetsu)) > self.breathbatch[index]: # 元の歌詞よりモーラ数が長い場合
                print("- Mode: Split Notes. -")
                xml = self.split_notes(xml, start_note_id, text.connected_bunsetsu_list[index], self.breathbatch[index]) # 不足しているモーラ数だけノートを分割
                print(f"New durations mora: {self.new_durations_mora}(len:{len(self.new_durations_mora)})")
                start_note_id += len(get_moralist(text.connected_bunsetsu_list[index]))
            elif len(get_moralist(bunsetsu)) < self.breathbatch[index]: # 元の歌詞よりモーラ数が短い場合
                print("- Mode: Add Vowels. -")
                xml = self.add_vowels(xml, start_note_id, index, text.connected_bunsetsu_list[index]) # 歌詞に対し余分なノートに母音を追加
                print(f"New durations mora: {self.new_durations_mora}(len:{len(self.new_durations_mora)})")
                start_note_id += self.breathbatch[index]
            else: # 元の歌詞と同じモーラ数の場合
                print("- Mode: Replace Lyric Only. -")
                self.replace_lyric_partial(xml, get_moralist(bunsetsu), start_note_id) # 歌詞を入れ替えるだけ
                print("Replace was done.")
                start_note_id += self.breathbatch[index]

        # self.replace_lyric(xml, text)
    
    # 全ての歌詞を入れ替える
    def replace_lyric(self, xml, text):
        now_mora = 0
        for part in xml.findall('part'):
            for measure in part.findall('measure'):
                for note in measure.findall('note'):
                    if note.find('lyric') != None:
                        note.find('lyric').find('text').text = text[now_mora]
                        now_mora += 1

    # 部分的に歌詞を入れ替える
    def replace_lyric_partial(self, xml, text, start_note_num):
        now_mora = 0
        replace_mora = 0
        print(f"start note num : {start_note_num}")
        # print(f"vowel added text={text}")1
        for part in xml.findall('part'):
            for measure in part.findall('measure'):
                for note in measure.findall('note'):
                    if note.find('lyric') != None:
                        if now_mora == start_note_num + replace_mora:
                            note.find('lyric').find('text').text = text[replace_mora]
                            replace_mora += 1
                            if replace_mora == len(text):
                                break
                        now_mora += 1
                else:
                    continue
                break
            else:
                continue
            break

class textinfo:
    def __init__(self):
        self.kanatext = '' # カタカナの入力テキスト
        self.mora_list = [] # モーラごとに格納したリスト
        self.bunsetsu_list = [] # 文節ごとに格納したリスト
        self.bunsetsu_list_num = [] # 各文節のモーラ数
        self.connected_bunsetsu_list = [] # breathbatch数（ブレス記号で区切られた区間のモーラ数）以上に連結させた文節リスト

    def showinfo(self):
        print(f"Text: {self.kanatext}, \
              モーラ: {self.mora_list}, \
              文節: {self.bunsetsu_list}, \
              文節モーラ数: {self.bunsetsu_list_num}")

# モーラごとのリスト作成  Ex) 'ごひゃく' -> ['ご', 'ひゃ', 'く']
def get_moralist(text):
    result = []
    for t in text:
        if t in small_list:
            result[-1] = result[-1] + t
        else:
            result.append(t)

    return result

# 入力文章を文節で区切ったリストに変換
def split_bunsetsu(text):
    m = MeCab.Tagger(ipadic.MECAB_ARGS)
    m_result = m.parse(text).splitlines()
    m_result = m_result[:-1] #最後の1行は不要な行なので除く
    break_pos = ['名詞','動詞','接頭詞','副詞','感動詞','形容詞','形容動詞','連体詞'] #文節の切れ目を検出するための品詞リスト
    wakachi = [''] #分かち書きのリスト
    afterPrepos = False #接頭詞の直後かどうかのフラグ
    afterSahenNoun = False #サ変接続名詞の直後かどうかのフラグ
    for v in m_result:
        if '\t' not in v: continue
        surface = v.split('\t')[0] #表層系
        pos = v.split('\t')[1].split(',') #品詞など
        pos_detail = ','.join(pos[1:4]) #品詞細分類（各要素の内部がさらに'/'で区切られていることがあるので、','でjoinして、inで判定する)
        #この単語が文節の切れ目とならないかどうかの判定
        noBreak = pos[0] not in break_pos
        noBreak = noBreak or '接尾' in pos_detail
        noBreak = noBreak or (pos[0]=='動詞' and 'サ変接続' in pos_detail)
        noBreak = noBreak or '非自立' in pos_detail #非自立な名詞、動詞を文節の切れ目としたい場合はこの行をコメントアウトする
        noBreak = noBreak or afterPrepos
        noBreak = noBreak or (afterSahenNoun and pos[0]=='動詞' and pos[4]=='サ変・スル')
        if noBreak == False:
            wakachi.append("")
        wakachi[-1] += surface
        afterPrepos = pos[0]=='接頭詞'
        afterSahenNoun = 'サ変接続' in pos_detail
    if wakachi[0] == '': wakachi = wakachi[1:] #最初が空文字のとき削除する

    return wakachi

def numeric_feature_by_regex(regex, s):
    match = re.search(regex, s)
    # 未定義 (xx) の場合、コンテキストの取りうる値以外の適当な値
    if match is None:
        return -50
    return int(match.group(1))

# 入力文章をアクセント句区切りのリストに変換
def pp_symbols(labels, drop_unvoiced_vowels=True):
    PP = []
    N = len(labels)
    # 各音素毎に順番に処理
    for n in range(N):
        lab_curr = labels[n]
        # 当該音素
        p3 = re.search(r"\-(.*?)\+", lab_curr).group(1)
        # 無声化母音を通常の母音として扱う
        if drop_unvoiced_vowels and p3 in "AEIOU":
            p3 = p3.lower()
        # 先頭と末尾の sil のみ例外対応
        if p3 == "sil":
            assert n == 0 or n == N - 1
            if n == 0:
                PP.append("^")
            elif n == N - 1:
                # 疑問系かどうか
                e3 = numeric_feature_by_regex(r"!(\d+)_", lab_curr)
                if e3 == 0:
                    PP.append("$")
                elif e3 == 1:
                    PP.append("?")
            continue
        elif p3 == "pau":
            PP.append("_")
            continue
        else:
            PP.append(p3)
        # アクセント型および位置情報（前方または後方）
        a1 = numeric_feature_by_regex(r"/A:([0-9\-]+)\+", lab_curr)
        a2 = numeric_feature_by_regex(r"\+(\d+)\+", lab_curr)
        a3 = numeric_feature_by_regex(r"\+(\d+)/", lab_curr)
        # アクセント句におけるモーラ数
        f1 = numeric_feature_by_regex(r"/F:(\d+)_", lab_curr)
        a2_next = numeric_feature_by_regex(r"\+(\d+)\+", labels[n + 1])
        # アクセント句境界
        if a3 == 1 and a2_next == 1:
            PP.append("#")
        # ピッチの立ち下がり（アクセント核）
        elif a1 == 0 and a2_next == a2 + 1 and a2 != f1:
            PP.append("]")
        # ピッチの立ち上がり
        elif a2 == 1 and a2_next == 2:
            PP.append("[")

    return PP

def main():
    xml = ET.parse(xml_path)
    root = xml.getroot()

    print(f"Input text to mekaparoscore.py = {text}")

    aboutxml = xmlinfo() # xmlに関するクラス初期化

    # 1) 入力xmlについての情報取得
    print("--- Analyzing xml file. ---")
    wait_adding = True
    for part in xml.findall('part'):
        aboutxml.num_part += 1 # パート数をカウント（使わない）
        breathbatch = 0 # ブレス記号で区切られた区間のノート数をカウント
        for measure_id, measure in enumerate(part.findall('measure')):
            aboutxml.num_measure += 1 # 小節数をカウント
            lastpitch = 0 # 直前のピッチ（整数値）
            downward = False # ピッチが下方遷移中
            for note in measure.findall('note'):
                aboutxml.num_note += 1 # ノート（音符）の数をカウント
                for pitch in note.findall('pitch'):
                    aboutxml.num_pitch += 1 # ピッチの数をカウント（使わない）
                    # if pitch != None:
                    #     pass
                # aboutxml.durations.append(note.find('duration').text) # ノートのduration値を記録
                for lyric in note.findall('lyric'):
                    if lyric != None:
                        aboutxml.num_mora += 1
                        aboutxml.durations_mora.append(note.find('duration').text) # ノートのduration値を記録
                        aboutxml.durations_mora_splitable.append(note.find('duration').text) # ノートのduration値を記録
                        if note.find('notations') != None:
                            if note.find('notations').find('technical') != None:
                                aboutxml.durations_mora_splitable[-1] = -1 # 上げ弓記号がついているノートのdurationは-1とする（長いdurationのノートから分割されるため）
                        breathbatch += 1
                        if wait_adding:
                            # 各breathbatchの最初のノートがある小節番号を記録
                            aboutxml.breathbatch_start_measure.append(measure_id)
                            wait_adding = False
                        nowpitch = int(oct_scale.index(note.find('pitch').find('step').text)) + int(note.find('pitch').find('octave').text) * 12
                        # ピッチの上下動でアクセントを求めようとした残骸（現状不使用）
                        if nowpitch < lastpitch and downward == False:
                            aboutxml.accent_core.append(len(aboutxml.durations_mora) - 2)
                            downward = True
                        elif nowpitch >= lastpitch:
                            downward = False
                        lastpitch = nowpitch
                # ブレス関係の情報記録
                for notation in note.findall('notations'):
                    for articulations in notation.findall('articulations'):
                        if articulations.find('breath-mark') != None:
                            if articulations.find('breath-mark').text == 'comma':
                                aboutxml.breathbatch.append(breathbatch)
                                breathbatch = 0
                                wait_adding = True
        aboutxml.breathbatch.append(breathbatch)

    aboutxml.durations_mora = [int(d) for d in aboutxml.durations_mora] # モーラごとのdurations値
    aboutxml.durations_mora_splitable = [int(d) for d in aboutxml.durations_mora_splitable] # 分割可能な（上げ弓記号がない）モーラごとのdurations値
    aboutxml.showinfo()

    # 2) 入力テキストの変換
    print("--- Analizing text file. ---")
    abouttext = textinfo() # テキストに関するクラス初期化
    abouttext.kanatext = pyopenjtalk.g2p(text, kana=True) # 入力テキストをカタカナに変換
    abouttext.mora_list = get_moralist(abouttext.kanatext) # モーラごとのリストに変換
    abouttext.mora_list = [jaconv.kata2hira(s) for s in abouttext.mora_list] # ひらがなに変換

    # 入力モーラ数が楽譜ノートに対し足りなかったら"ら"を強制的に入れる
    if force_enbed_with_la:
        if len(abouttext.mora_list) < len(aboutxml.durations_mora):
            while len(abouttext.mora_list) <= len(aboutxml.durations_mora):
                abouttext.mora_list.append('ら')
    else:
        assert len(abouttext.mora_list) >= len(aboutxml.durations_mora), f"入力モーラ数が{len(aboutxml.durations_mora) - len(abouttext.mora_list)}不足しています"
    
    if splitmode == 0: # 文節区切り
        bunsetsu_list_kata = [pyopenjtalk.g2p(bunsetsu, kana=True) for bunsetsu in split_bunsetsu(text)]

    elif splitmode == 1: # アクセント句区切り
        labels = pyopenjtalk.extract_fullcontext(text, run_marine=True)
        phoneme_accent = pp_symbols(labels) # 音素・アクセント列作成
        print(f"音素・アクセント列 : {''.join(phoneme_accent)}")
        ph_stock, bs_stock, bunsetsu_list_kata = [], [], []
        lastvowel = ""
        # bunsetsu_list（文節ではなくアクセント区切り）作成
        for phoneme in tqdm(phoneme_accent):
            if phoneme in vowels:
                if ph_stock == [] and phoneme == lastvowel:
                    if use_continuous_vowel:
                        bs_stock.append(phoneme_list["".join(phoneme)])
                    else:
                        pass
                else:
                    ph_stock.append(phoneme)
                    bs_stock.append(phoneme_list["".join(ph_stock)])
                    ph_stock = []
                    lastvowel = phoneme
            elif phoneme in ['#', "?", "$"]:
                if bs_stock != []:
                    bunsetsu_list_kata.append("".join(bs_stock))
                bs_stock = []
                lastvowel = ''
            elif phoneme in ["[", "]", "$", "^"]:
                pass
            else:
                ph_stock.append(phoneme)
                lastvowel = ""
    abouttext.bunsetsu_list =  [jaconv.kata2hira(s) for s in bunsetsu_list_kata] # ひらがなに変換
    # 未知の単語等により文節の頭が小さい文字になってしまった場合の処理
    for id, bunsetsu in enumerate(abouttext.bunsetsu_list):
        if bunsetsu[0] in small_list:
            abouttext.bunsetsu_list[id - 1] += bunsetsu
            del abouttext.bunsetsu_list[abouttext.bunsetsu_list.index(bunsetsu)]
    abouttext.bunsetsu_list_num = [len(get_moralist(bunsetsu)) for bunsetsu in abouttext.bunsetsu_list]
    abouttext.showinfo()

    # 3) xmlファイル作成
    print("--- Editing xml file. ---")
    if editmode == 0: # 長いノートから順に切る編集モード
        if len(abouttext.mora_list) == len(aboutxml.durations_mora): # 入力テキストのモーラ数と元の楽譜のノート数が同じ場合
            xmlinfo.replace_lyric(aboutxml, root, abouttext.mora_list) # テキストを入れ替えるだけ
        elif len(abouttext.mora_list) > len(aboutxml.durations_mora): # 元の楽譜のノート数より入力テキストのモーラ数が多い場合
            num_over = len(abouttext.mora_list) - len(aboutxml.durations_mora) # どれだけ多いか
            xmlinfo.revise_xml(aboutxml, root, abouttext.mora_list, num_over)
    
    elif editmode == 1: # 文節区切りの編集モード
        xmlinfo.revise_xml2(aboutxml, root, abouttext)
    else:
        print(f"Error : Not exist the edit mode {editmode}")
        exit()

    # 歌詞の先頭数文字をファイル名とする
    lyric_name = pyopenjtalk.g2p(text, kana=False).replace(' ', '')[:20]
    updateConfig('lyric_name', lyric_name)
    outfile_path = join(textfile_path.rsplit('/', 1)[0], f'xml_paro/{lyric_name}.xml')
    xml.write(outfile_path, encoding='utf-8', xml_declaration=True) # 保存

    print("--- Completed All. ---")

# yaml更新用関数
def updateConfig(key, value):
    with open('functions/config.yaml', 'r', encoding="utf-8") as f:
        data = yaml.load(f)

    data[key] = value

    with open('functions/config.yaml', 'w', encoding="utf-8") as f:
        yaml.dump(data, f)

if __name__ == "__main__":
    main()
