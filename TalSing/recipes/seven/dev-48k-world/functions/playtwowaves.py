from pydub import AudioSegment
from pydub.playback import play
# from kivy.core.audio import SoundLoader

def playdouble(audio1, audio2):
    sound1 = AudioSegment.from_mp3(audio1)
    sound2 = AudioSegment.from_mp3(audio2)

    combined = sound1.overlay(sound2, position=65) # positionでインスト音源とのずれを補正
    play(combined)

# def playrefer(genreList):
#     soundList = [SoundLoader.load(f'forSynth/refer_wav/{genre}.wav' for genre in genreList)]