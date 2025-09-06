
from ipdb import set_trace as ipst
import customtkinter as ctk
import tkinter as tk
from PIL import Image, ImageTk
import math

ctk.set_appearance_mode("Dark")

class ImageDialApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Image Dial")
        self.geometry("300x350")

        self.dial_size = 200
        self.center = (self.dial_size // 2, self.dial_size // 2)
        self.angle = 0

        frame = ctk.CTkFrame(self)
        frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Canvas for displaying the dial
        self.canvas = tk.Canvas(frame, width=self.dial_size, height=self.dial_size, bg="black", highlightthickness=0)
        self.canvas.grid(row=0, column=0)

        # Load images
        self.base_img = Image.open("functions/dial_base.png").resize((self.dial_size, self.dial_size))
        self.needle_img = Image.open("functions/dial_needle.png").resize((self.dial_size, self.dial_size))

        self.base_tk = ImageTk.PhotoImage(self.base_img)
        self.needle_tk = ImageTk.PhotoImage(self.needle_img)

        self.canvas.create_image(self.center, image=self.base_tk)

        # Place needle and keep reference
        self.needle_canvas_id = self.canvas.create_image(self.center, image=self.needle_tk)

        # Bind mouse events
        self.canvas.bind("<Button-1>", self.set_angle)
        self.canvas.bind("<B1-Motion>", self.set_angle)

        # Label to show angle
        self.value_label = ctk.CTkLabel(frame, text="角度: 0°")
        self.value_label.grid(row=1, column=0)

    def set_angle(self, event):
        dx = event.x - self.center[0]
        dy = self.center[1] - event.y  # Y反転（上が正方向）
        angle = math.degrees(math.atan2(dy, dx))

        # Normalize angle to 0–360°
        self.angle = (angle + 360) % 360

        # Update needle image
        rotated = self.needle_img.rotate(-self.angle, resample=Image.BICUBIC)
        self.needle_tk = ImageTk.PhotoImage(rotated)
        self.canvas.itemconfig(self.needle_canvas_id, image=self.needle_tk)

        # Update label
        self.value_label.configure(text=f"角度: {int(self.angle)}°")

if __name__ == "__main__":
    app = ImageDialApp()
    app.mainloop()




# import os
# from os.path import join
# import librosa
# import soundfile as sf
# from scipy.signal import lfilter
# import numpy as np
# from MyLib.orgsvs2 import OrgWaves

# ### config ###
# wav_bef_path = "/mnt/c/research/yamamoto/TalSing/TalSing/recipes/seven/dev-48k-world/forSynthesis/result/saatekoNshuunosazaes_01.wav"
# wav_aft_path = f"/mnt/c/research/yamamoto/TalSing/TalSing/recipes/seven/dev-48k-world/forSynthesis/result_comp/comp_{os.path.basename(wav_bef_path)}"
# ##############

# def PyComp(y, sr, threshold_db=-20.0, ratio=4.0, attack_ms=10.0, release_ms=100.0):
#     """
#     シンプルなRMSベースのオーディオコンプレッサ。
#     """
#     # パラメータ設定
#     frame_size = int(sr * 0.01)  # 10msごとの処理
#     attack_coeff = np.exp(-1.0 / (sr * (attack_ms / 1000.0)))
#     release_coeff = np.exp(-1.0 / (sr * (release_ms / 1000.0)))

#     envelope = np.zeros_like(y)
#     gain = np.ones_like(y)

#     # 信号の振幅 envelope を推定
#     for i in range(1, len(y)):
#         rectified = abs(y[i])
#         if rectified > envelope[i - 1]:
#             envelope[i] = attack_coeff * envelope[i - 1] + (1 - attack_coeff) * rectified
#         else:
#             envelope[i] = release_coeff * envelope[i - 1] + (1 - release_coeff) * rectified

#     # dBスケールに変換してしきい値で圧縮
#     envelope_db = 20 * np.log10(np.maximum(envelope, 1e-8))
#     over_threshold_db = np.maximum(envelope_db - threshold_db, 0)
#     gain_db = -over_threshold_db * (1 - 1 / ratio)
#     gain = 10 ** (gain_db / 20.0)

#     # ゲインを適用
#     y_compressed = y * gain

#     return y_compressed

# if __name__ == '__main__':
#     # --- 音声読み込み ---
#     y, sr = librosa.load(wav_bef_path, sr=None)

#     # --- 圧縮処理 ---
#     y_compressed = PyComp(y, sr)

#     # --- 音量の正規化（オプション） ---
#     y_compressed = y_compressed / np.max(np.abs(y_compressed)) * 0.99

#     # --- 書き出し ---
#     sf.write(wav_aft_path, y_compressed, sr)

#     print(f"コンプレッサー適用済み音声を保存しました: {wav_aft_path}")

#     w1 = OrgWaves()
#     w2 = OrgWaves()
#     w1.analyzeWave(wav_bef_path)
#     w2.analyzeWave(wav_aft_path)
#     w1.dispWave("w1.png")
#     w2.dispWave("w2.png")