import customtkinter as ctk
import time
import threading
import os
from os.path import join
import subprocess
from threading import Event, Thread
from ipdb import set_trace as ipst
from kivy.core.audio import SoundLoader
from faster_whisper import WhisperModel
import sounddevice as sd
from PIL import Image, ImageTk

import functions.rec2text as r2t # 音声収録処理の中身（マイク2本の場合=独立成分分析を行う場合）
import functions.rec2text_single as r2t_s # 音声収録処理の中身（マイク1本の場合）
import functions.playtwowaves as playww # 音源再生処理の中身
from ruamel.yaml import YAML
yaml = YAML()  
yaml.preserve_quotes = True  # クォートの保持
yaml.indent(mapping=2, sequence=4, offset=2)  # インデント調整

# load config
with open('functions/config.yaml', 'r') as f:
    data = yaml.load(f)
    version = data["version"]
    mic_double = data["mic_double"]
    default_win_ratio = data["default_win_ratio"]
    FONT_TYPE = data["font"]
    genre = data["genre"]
    color_pre = data['color_pre']
    # for debug
    start_stage = data["start_stage"]

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

scriptpath = f'{current_dir}/run.sh'

if start_stage < 2:
    model = WhisperModel("large-v3", device="cpu", compute_type="float32")
    print('WhisperModel Loaded.')

# メインウィンドウをAppにて作成する．
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        # 全画面表示
        self.attributes("-fullscreen", True)
        # 画面サイズ取得
        self.window_width, self.window_height = self.winfo_screenwidth(), self.winfo_screenheight()
        # デフォルト画面サイズ
        self.def_win_width, self.def_win_height = self.window_width * default_win_ratio, self.window_height * default_win_ratio

        ctk.set_appearance_mode("#333333")

        self.grid_rowconfigure(0, weight = 1)
        self.grid_columnconfigure(0, weight = 1)

        # 最初に呼び出される画面
        if start_stage == 0:
            self.show_home()
        elif start_stage == 1:
            self.show_rec()
        elif start_stage == 2:
            self.show_select()
        elif start_stage == 3:
            self.show_output()

    # ホーム画面呼び出し
    def show_home(self):
        print("--- st : show_home ---")
        if hasattr(self, "output_frame"): # output_frameが定義されていたら（=2周目以降なら）削除
            self.clear_frame_point(self.output_frame)
        self.home_frame = HomeFrame(self, width = self.def_win_width, height=self.def_win_height)
        self.home_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        print("--- ed : show_home---")

    # 録音画面呼び出し
    def show_rec(self):
        print("--- st : show_rec ---")
        if start_stage != 1:
            self.clear_frame_point(self.home_frame)
        # 録音画面初期化
        self.rec_frame = RecFrame(self, width = self.def_win_width, height=self.def_win_height)
        self.rec_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        updateConfig('recording', False)
        print("--- ed : show_rec ---")

    # ジャンル選択画面呼び出し
    def show_select(self):
        print("--- st : show_select ---")
        if start_stage != 2:
            self.clear_frame_point(self.rec_frame)
        # 楽曲ジャンル選択画面初期化
        self.select_frame = SelectFrame(self, width = self.def_win_width, height=self.def_win_height)
        self.select_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        print("--- ed : show_select ---")

    # 合成処理画面呼び出し
    def show_process(self):
        print("--- st : show_process ----")
        self.clear_frame_point(self.select_frame)
        # 合成中画面初期化
        self.process_frame = ProcessFrame(self, width = self.def_win_width, height=self.def_win_height)
        self.process_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        while self.process_frame.runscript_event.is_set() != True: # 裏で合成スクリプトが実行している間updateで描画更新。完了するまでこの行でループ。
            self.process_frame.update()
        print("--- ed : show_process ----")
        self.show_output()

    # 音源再生画面呼び出し
    def show_output(self):
        print("--- st : show_output ----")
        if start_stage != 3:
            self.clear_frame_point(self.process_frame)
        # 合成結果表示画面初期化
        self.output_frame = OutputFrame(self, width = self.def_win_width, height=self.def_win_height)
        self.output_frame.grid(row=0, column=0, padx=20, pady=10, sticky="nsew")
        print("--- ed : show_output ---")

    # 全てのフレームをクリアする
    # def clear_frames(self):
    #     print("Clear All Frames.")
    #     for CtkFrame in (self.select_frame, self.process_frame, self.output_frame1, self.output_frame2, self.thanks_frame):
    #         if CtkFrame != None:
    #             print(f"CtkFrame={CtkFrame}")
    #             CtkFrame.destroy()

    # 指定したフレームをクリアする
    def clear_frame_point(self, *obj_tuple):
        obj_list = list(obj_tuple)
        for obj in obj_list:
            if obj != None:
                obj.grid_forget()
                print(f"Clear {obj} frame.")

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        # ウィンドウ設定
        scr_width, scr_height = self.winfo_screenwidth(), self.winfo_screenheight()
        self.win_width, self.win_height = int(scr_width / 3), int(scr_height / 2)
        x = (scr_width - self.win_width) // 2
        y = (scr_height - self.win_height) // 2
        self.geometry(f"{self.win_width}x{self.win_height}+{x}+{y}") # 画面の半分のサイズのウィンドウを画面中央に配置
        self.overrideredirect(True) # OS標準のクローズボタン等を表示しない
        # 自動配置調整設定
        self.grid_columnconfigure((0, 1), weight=1)
        for i in range(7):
            self.rowconfigure(i, weight=1)
        # カラー取得
        self.color_pre, self.color_main, self.color_hover, self.color_bg, self.colors = getColors()

        # 入出力設定
        self.device_list_raw = sd.query_devices()
        self.dev_list = []
        self.indev_list = []
        self.outdev_list = []
        for dev in self.device_list_raw:
            self.dev_list.append(dev['name'])
            if dev['max_input_channels'] > 0:
                self.indev_list.append(dev['name'])
            if dev['max_output_channels'] > 0:
                self.outdev_list.append(dev['name'])

        self.parent = parent
        self.transient(parent)
        self.grab_set()

        # 親ウィンドウにウィンドウが開いていることを通知
        self.parent.settings_window = self
        
        self.setup_form()

    def setup_form(self):
        # タイトルラベル
        self.label_title = ctk.CTkLabel(self, text="-  設　定  -", font=(FONT_TYPE, self.win_width/15), height=self.win_height/10)
        self.label_title.grid(row=0, column=0, columnspan=2, padx=20, pady=10, sticky="wen")
        # Audio
        self.label_audio = ctk.CTkLabel(self, text="Audio", font=(FONT_TYPE, self.win_width/20, "bold"))
        self.label_audio.grid(row=1, column=0, padx=20, pady=10, sticky="wen")
        self.label_audioinput = ctk.CTkLabel(self, text="Input", font=(FONT_TYPE, self.win_width/20))
        self.label_audioinput.grid(row=2, column=0, padx=20, pady=10, sticky="wen")
        self.box_audioinput = ctk.CTkComboBox(self, values=[indev for indev in self.indev_list], width=self.win_width/3, height=50, font=(FONT_TYPE, 30), dropdown_font=(FONT_TYPE, 25), command=self.updateInDev)
        self.box_audioinput.grid(row=2, column=1, padx=20, pady=10, sticky="wen")
        self.box_audioinput.set(self.device_list_raw[sd.default.device[0]]['name'])
        self.label_audiooutput = ctk.CTkLabel(self, text="Output", font=(FONT_TYPE, self.win_width/20))
        self.label_audiooutput.grid(row=3, column=0, padx=20, pady=10, sticky="wen")
        self.box_audiooutput = ctk.CTkComboBox(self, values=[indev for indev in self.outdev_list], width=self.win_width/4, height=50, font=(FONT_TYPE, 30), dropdown_font=(FONT_TYPE, 25), command=self.updateOutDev)
        self.box_audiooutput.grid(row=3, column=1, padx=20, pady=10, sticky="wen")
        self.box_audiooutput.set(self.device_list_raw[sd.default.device[1]]['name'])
        # Design
        self.label_design = ctk.CTkLabel(self, text="Design", font=(FONT_TYPE, self.win_width/20, "bold"))
        self.label_design.grid(row=4, column=0, padx=20, pady=10, sticky="wen")
        self.label_color = ctk.CTkLabel(self, text="Color", font=(FONT_TYPE, self.win_width/20))
        self.label_color.grid(row=5, column=0, padx=20, pady=10, sticky="wen")
        self.box_color = ctk.CTkComboBox(self, values=[indev for indev in self.colors], width=self.win_width/3, height=50, font=(FONT_TYPE, 30), dropdown_font=(FONT_TYPE, 25), command=self.updateColor)
        self.box_color.grid(row=5, column=1, padx=20, pady=10, sticky="wen")
        self.box_color.set(self.color_pre)
        # Closeボタン
        self.close_button = ctk.CTkButton(self, text="Close", font=(FONT_TYPE, self.win_width/25), fg_color=self.color_main, hover_color=self.color_hover, command=self.close_win)
        self.close_button.grid(row=6, column=0, columnspan=2, padx=20, pady=10, sticky="wes")

    def updateInDev(self, value):
        dev_id = self.dev_list.index(value)
        with open('functions/config.yaml', 'r') as f:
            data = yaml.load(f)
        data['InOutSetup'][0] = dev_id
        with open('functions/config.yaml', 'w') as f:
            yaml.dump(data, f)

    def updateOutDev(self, value):
        dev_id = self.dev_list.index(value)
        with open('functions/config.yaml', 'r') as f:
            data = yaml.load(f)
        data['InOutSetup'][1] = dev_id
        with open('functions/config.yaml', 'w') as f:
            yaml.dump(data, f)

    def updateColor(self, color):
        # カラー更新
        updateConfig('color_pre', color)
        with open('functions/colorpreset.yaml', 'r') as f:
            data = yaml.load(f)
            self.color_main = data[color][0]
            self.color_hover = data[color][1]
        self.close_button.configure(fg_color=self.color_main, hover_color=self.color_hover)

    def close_win(self):
        # 入出力反映
        with open('functions/config.yaml', 'r') as f:
            data = yaml.load(f)
            sd.default.device = data['InOutSetup']
        """ ウィンドウを閉じる """
        app.home_frame.destroy()
        app.show_home()
        self.parent.settings_window = None  # 変数をリセット
        self.destroy()

class HomeFrame(ctk.CTkFrame):
    def __init__(self, *args, width, height, **kwargs):
        print("Init HomeFrame.")
        # カラー取得
        self.color_pre, self.color_main, self.color_hover, self.color_bg, self.colors = getColors()
        super().__init__(*args, width=width, height=height, fg_color=self.color_bg, **kwargs)
        # 画面サイズ取得
        self.scr_width, self.scr_height = self.winfo_screenwidth(), self.winfo_screenheight()

        for i in range(4):
            self.grid_rowconfigure(i, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.settings_window = None  # 設定ウィンドウの状態管理

        self.setup_form()

    def setup_form(self):
        # 余白調整用ラベル
        label_space = ctk.CTkLabel(self, text="", font=(FONT_TYPE, self.scr_height/10))
        label_space.grid(row=0, column=0, padx=20, pady=10, sticky="wes")
        # タイトルラベル
        label_title = ctk.CTkLabel(self, text="替え歌合成システム", font=(FONT_TYPE, self.scr_height/10))
        label_title.grid(row=1, column=0, padx=20, pady=10, sticky="wes")
        label_title2 = ctk.CTkLabel(self, text="TalSing", font=(FONT_TYPE, self.scr_height/6, "bold"))
        label_title2.grid(row=2, column=0, padx=20, pady=10, sticky="wen")
        # バージョンラベル
        label_version = ctk.CTkLabel(self, text=f"v.{version}", font=(FONT_TYPE, self.scr_height/30))
        label_version.grid(row=3, column=0, padx=30, pady=0, sticky='es')
        # デモ開始ボタン
        button_start = ctk.CTkButton(self, text="START", font=(FONT_TYPE, self.scr_height/5), fg_color=self.color_main, hover_color=self.color_hover, width=self.scr_width/2, height=self.scr_height/5, command=self.master.show_rec)
        button_start.grid(row=4, column=0, padx=10, pady=10, sticky='wes')
        # 設定ボタン
        button_config = ctk.CTkButton(self, text="⚙", font=(FONT_TYPE, self.scr_height/12), fg_color=self.color_main, hover_color=self.color_hover, width=self.scr_height/10, height=self.scr_height/10, command=self.open_settings)
        button_config.place(x=10, y=10)

    def open_settings(self):
        """ 設定ウィンドウを開く（重複防止） """
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
        
class RecFrame(ctk.CTkFrame): # 録音画面に関するクラス
    def __init__(self, *args, width, height, **kwargs):
        print("Init RecFrame.")
        # カラー取得
        self.color_pre, self.color_main, self.color_hover, self.color_bg, self.colors = getColors()
        super().__init__(*args, width=width, height=height, fg_color=self.color_bg, **kwargs)
        # 画面サイズ取得
        self.scr_width, self.scr_height = self.winfo_screenwidth(), self.winfo_screenheight()
        # 自動配置設定
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure((0, 1), weight=1)
        
        # スレッド準備
        if mic_double == True:
            self.rec_thread = threading.Thread(target=r2t.main)
            self.save_thread = threading.Thread(target=r2t.save_wav)
            self.separate_thread = threading.Thread(target=r2t.separate, args=(model, ))
        else:
            self.rec_thread = threading.Thread(target=r2t_s.main)
            self.save_thread = threading.Thread(target=r2t_s.save_wav)
            self.separate_thread = threading.Thread(target=r2t_s.separate, args=(model, ))
        self.recoreded_event = threading.Event()

        self.setup_form()

    def setup_form(self):
        # フレームのラベルを表示
        self.label_wait = ctk.CTkLabel(self, text="録音を開始してください", font=(FONT_TYPE, self.scr_width/20), fg_color="transparent", height=self.scr_height/3)
        self.label_wait.grid(row=0, column=0, columnspan=2, padx=20, pady=10, sticky="we")
        # 録音開始ボタン
        self.button_start = ctk.CTkButton(self, text="Start", font=(FONT_TYPE, self.scr_width/13), fg_color=self.color_main, hover_color=self.color_hover, width=self.scr_width/3, height=self.scr_height/3, command=self.start_rec)
        self.button_start.grid(row=1, column=0, padx=10, pady=10, sticky='wes')
        # 録音終了ボタン
        self.button_end = ctk.CTkButton(self, text="Stop", font=(FONT_TYPE, self.scr_width/13), fg_color='#333333', hover_color=self.color_hover, width=self.scr_width/3, height=self.scr_height/3, state="disabled")
        self.button_end.grid(row=1, column=1, padx=10, pady=10, sticky='wes')
        # 戻るボタン
        self.button_return = ctk.CTkButton(self, text="戻る", font=(FONT_TYPE, self.scr_width/25), fg_color=self.color_main, hover_color=self.color_hover, width=self.scr_width/10, height=self.scr_height/10, command=self.master.show_home)
        self.button_return.place(x=10, y=10)

    def start_rec(self):
        print('Rec Start.')
        updateConfig('recording', True)
        
        if self.recoreded_event.is_set(): # 再収録の場合（一度使用したスレッドは使えないのでまた作り直し）
            self.rec_thread.join()
            self.recoreded_event.clear()
            if mic_double == True:
                self.rec_thread = threading.Thread(target=r2t.main)
                self.save_thread = threading.Thread(target=r2t.save_wav)
            else:
                self.rec_thread = threading.Thread(target=r2t_s.main)
                self.save_thread = threading.Thread(target=r2t_s.save_wav)

        self.rec_thread.start()
        self.label_wait.configure(text='録音中...')
        self.button_return.configure(state='disabled', fg_color='#333333')
        self.button_start.configure(state='disabled', fg_color='#333333')
        self.button_end.configure(state='normal', fg_color=self.color_main, hover_color=self.color_hover, text='Stop', command=self.stop_rec)

    def stop_rec(self):
        print('Rec End.')
        updateConfig('recording', False)
        self.recoreded_event.set()
        self.save_thread.start()
        self.save_thread.join()
        self.label_wait.configure(text='録音しました')
        self.button_return.configure(state='normal', fg_color=self.color_main)
        self.button_start.configure(text='ReRec', state='normal', fg_color=self.color_main)
        self.button_end.configure(text='OK', command=self.go_next, fg_color='#ff4500', hover_color='#ff7f50')
    
    def go_next(self):
        self.separate_thread.start() # 音声認識開始
        self.master.show_select()

class SelectFrame(ctk.CTkFrame):
    def __init__(self, *args, width, height, **kwargs):
        print("Init HomeFrameSelect.")
        # カラー取得
        self.color_pre, self.color_main, self.color_hover, self.color_bg, self.colors = getColors()
        super().__init__(*args, width=width, height=height, fg_color=self.color_bg, **kwargs)
        # 画面サイズ取得
        self.scr_width, self.scr_height = self.winfo_screenwidth(), self.winfo_screenheight()

        self.width = width
        self.height = height

        self.setup_form()

        self.check_finRecognition()

    def setup_form(self):
        # ラベル
        self.label = ctk.CTkLabel(self, text="ジャンルを選択してください", font=(FONT_TYPE, self.scr_width/20))
        self.label.grid(row=0, column=0, padx=20, pady=10, sticky="w")
        # ジャンル選択ボックス
        self.combobox = ctk.CTkComboBox(self, values=genre, width=self.winfo_screenwidth()/3, height=100, font=(FONT_TYPE, self.scr_width/30), dropdown_font=(FONT_TYPE, self.scr_width/30), command=self.updateGenre)
        self.combobox.grid(row=1, column=0, padx=50, pady = 50, sticky='we')
        self.combobox.set('- 選択してください -')
        # 音源試聴ボタン
        self.referState = False
        self.referButton = ctk.CTkButton(self, text='▶︎', font=(FONT_TYPE, self.scr_width/25), fg_color=self.color_main, hover_color=self.color_hover, height=100, command=self.updateReferButton)
        self.referButton.grid(row=1, column=1, padx=50, pady = 50, sticky='w')

        self.grid_columnconfigure((0, 1), weight=1)
        self.grid_rowconfigure((0, 1), weight=1)

        # 歌声合成処理スタートボタン
        self.button = ctk.CTkButton(self, text="音声解析中。ちょっと待ってね。", font=(FONT_TYPE, self.scr_width/18), fg_color="#a9a9a9", border_color="#333333", border_width=2, width=self.width, height=self.height/4, command=self.goProcess, state="disabled")
        self.button.grid(row=2+len(genre)//2, column=0, padx=10, pady=10, sticky='nsew', columnspan=3)

    def updateGenre(self, value):
        if value != '- 選択してください -':
            updateConfig('score_no', "0" + str(genre.index(value) + 1))
            self.stopRefer()
            self.referButton.configure(text='▶︎')
            self.referState = False
            print(self.referState)

    def updateReferButton(self):
        if self.referState == False:
            self.referButton.configure(text='◻️')
            self.playRefer()
            self.referState = True
        else:
            self.referButton.configure(text='▶︎')
            self.stopRefer()
            self.referState = False

    def playRefer(self):
        with open('functions/config.yaml', 'r') as f:
            data = yaml.load(f)
            no = data['score_no']
            self.sound = SoundLoader.load(f'{current_dir}/forSynthesis/wav_refer/{no}.wav')
            if self.referState == False:
                self.sound.play()
                print('play')

    def stopRefer(self):
        if self.referState == True:
            self.sound.stop()
            print('stop')

    def check_finRecognition(self):
        with open('functions/config.yaml', 'r') as f:
            data = yaml.load(f)
            if data['recognition'] == True:
                # ボタンのステータスをnormalに
                self.button.configure(state='normal')
                self.button.configure(fg_color=self.color_main, hover_color=self.color_hover)
                self.button.configure(text='解析完了！歌声合成を始めよう！')
            else:
                self.after(1000, self.check_finRecognition) # 1秒おきに音声認識処理が終わっているか確認する

    def goProcess(self):
        self.stopRefer()
        app.show_process()

class ProcessFrame(ctk.CTkFrame): # 合成処理中画面に関するクラス
    def __init__(self, *args, width, height, **kwargs):
        print("Init ProcessFrame.")
        # カラー取得
        self.color_pre, self.color_main, self.color_hover, self.color_bg, self.colors = getColors()
        super().__init__(*args, width=width, height=height, fg_color=self.color_bg, **kwargs)
        # 画面サイズ取得
        self.scr_width, self.scr_height = self.winfo_screenwidth(), self.winfo_screenheight()
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # # 背景
        # self.background = ctk.CTkLabel(self, text="", fg_color=self.color_main, width=self.scr_width, height=self.scr_height)
        # self.background.place(x=0, y=0)
        # "合成中ラベル"
        self.label = ctk.CTkLabel(self, text="合成中.  ", font=(FONT_TYPE, self.scr_width/10))
        self.label.grid(row=0, column=0, sticky='wens')
        # 画像準備
        self.img_logo = Image.open("images/logo.png").convert("RGBA")  # 画像ファイルを指定
        self.angle = 0  # 回転角度
        # 画像ラベルを作成
        self.image_label = ctk.CTkLabel(self, text="")
        self.image_label.grid(row=1, column=0, pady=0, sticky='wens')

        self.disp_count = 0 # 合成中ラベルカウント
        self.runscript_event = threading.Event() # 合成処理中のフラグ

        self.label_update() # 合成中ラベル更新
        self.rotate_img() # ロゴ更新

        self.runscript_thread = threading.Thread(target=self.run1) # 替え歌楽譜作成~歌声合成を行うNNSVSを動かすためのスレッド
        self.after(1, self.runscript_thread.start) # 理由はわからないけど何故かafterをかまさないとdisplay_threadが実行されず

    def label_update(self):
        if self.disp_count % 3 == 0:
            self.label.configure(text="合成中.  ")
        elif self.disp_count % 3 == 1:
            self.label.configure(text="合成中.. ")
        elif self.disp_count % 3 == 2:
            self.label.configure(text="合成中...")
        self.disp_count += 1
        # run1が完了していないなら0.5秒後に再度display()
        if self.runscript_event.is_set() != True: 
            self.after(500, self.label_update)
    
    def rotate_img(self):
        self.angle += 10  # 角度を変更（10度ずつ回転）
        rotated = self.img_logo.rotate(self.angle, resample=Image.BICUBIC)  # 回転
        self.tk_image = ImageTk.PhotoImage(rotated)  # CTk用に変換
        self.image_label.configure(image=self.tk_image)  # ラベルを更新
        # run1が完了していないなら50ms後に再びrotate_image()
        if self.runscript_event.is_set() != True: 
            self.after(50, self.rotate_img)

    # 替え歌合成処理部
    def run1(self):
        print("Start shell processing.")
        print(f"Running shell thread : {threading.current_thread().name}")
        with open('functions/config.yaml', 'r') as f:
            config = yaml.load(f)
            no = config['score_no']
            if start_stage != 0:
                text = 'ジャンル選択画面から始めたときのデバッグ専用テキストだようまくいけてるかないけていて欲しいなお願いだから'
            else:
                text = config['extracted_text'] # yamlに保存された、録音部で認識されたテキストを取得
        # 別スレッドでシェルスクリプトを実行
        subprocess.run([scriptpath, '--stage', '100', '--stop-stage', '100', no, text])

        self.runscript_event.set() # 合成処理が終了したらフラグをTrueに
        print('Finish runscript.')

class OutputFrame(ctk.CTkFrame): # 合成音声再生画面に関するクラス
    def __init__(self, *args, width, height, **kwargs):
        # カラー取得
        self.color_pre, self.color_main, self.color_hover, self.color_bg, self.colors = getColors()
        super().__init__(*args, width=width, height=height, fg_color=self.color_bg, **kwargs)
        # 画面サイズ取得
        self.scr_width, self.scr_height = self.winfo_screenwidth(), self.winfo_screenheight()
        # フラグ準備
        self.playing_event = threading.Event()
        self.playend_event = threading.Event()
        
        self.play_count = 0
        self.setup_form()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def setup_form(self):
        # ラベル
        self.grid_columnconfigure(0, weight=1)
        self.label = ctk.CTkLabel(self, text="合成完了！ボタンを押して再生してみよう！", font=(FONT_TYPE, self.scr_width/20))
        self.label.grid(row=0, column=0, pady=10, sticky="nsew")
        # 再生ボタン
        self.playsound_button = ctk.CTkButton(self, text="PLAY", font=(FONT_TYPE, self.scr_width/20), fg_color=self.color_main, hover_color=self.color_hover, width=self.scr_height/3, height=self.scr_height/3, command=self.play_button_func)
        self.playsound_button.grid(row=1, column=0, padx=10, pady=30, sticky="s")

    def label_update(self):
        if self.playend_event.is_set() != True: # 音源再生中
            if self.play_count % 3 == 0:
                self.label.configure(text="Now Playing.  ")
            elif self.play_count % 3 == 1:
                self.label.configure(text="Now Playing.. ")
            else:
                self.label.configure(text="Now Playing...")
            self.label.grid(row=0, column=0, pady=10)
            self.play_count += 1

            self.after(500, self.label_update) # 0.5秒後に再度ラベル更新
        else: # 音源再生済み
            self.label.configure(text="再生終了！ありがとうございました！")
            self.playsound_button.configure(text='RePLAY')
            self.gohome_button = ctk.CTkButton(self, text="ホームヘ戻る", font=(FONT_TYPE, self.scr_width/30), fg_color=self.color_main, hover_color=self.color_hover, width=self.scr_width/8, height=self.scr_height/8, command=app.show_home)
            self.gohome_button.grid(row=2, column=0, pady=10, sticky='s')
    
    # PLAYボタンを押したときに呼び出される関数
    def play_button_func(self):
        self.playwav_thread = threading.Thread(target=self.play_audio)
        self.playwav_thread.start()
        self.playsound_button.configure(state='disabled')
        self.playend_event.clear()
        self.label_update()
    
    # 音源再生部（合成歌声と伴奏の2音源）
    def play_audio(self):
        if start_stage == 3: # デバッグ用
            wav1 = 'forSynthesis/result/forDebug/geNzainagareteiruoNg_01.wav'
            wav2 = 'forSynthesis/wav_refer/forDebug/01.wav'
        else:
            with open('functions/config.yaml', 'r') as f:
                data = yaml.load(f)
                wav1 = join(f"forSynthesis/result", f"{data['lyric_name']}_{data['score_no']}.wav")
                wav2 = join(f"forSynthesis/wav_refer", f"{data['score_no']}.wav")
        self.playing_event.set()
        playww.playdouble(wav1, wav2)
        self.playend_event.set()
        self.playsound_button.configure(state='normal')

# yaml更新用関数
def updateConfig(key, value):
    with open('functions/config.yaml', 'r', encoding="utf-8") as f:
        data = yaml.load(f)

    data[key] = value

    with open('functions/config.yaml', 'w', encoding="utf-8") as f:
        yaml.dump(data, f)

# カラー取得関数
def getColors():
    with open('functions/config.yaml', 'r') as f:
        data = yaml.load(f)
        color_pre = data['color_pre']
    with open('functions/colorpreset.yaml', 'r') as f:
        data = yaml.load(f)
        color_main = data[color_pre][0]
        color_hover = data[color_pre][1]
        color_bg = data[color_pre][2]
        colors = list(data)

    return color_pre, color_main, color_hover, color_bg, colors
    
if __name__ == "__main__":
    app = App()
    app.mainloop()