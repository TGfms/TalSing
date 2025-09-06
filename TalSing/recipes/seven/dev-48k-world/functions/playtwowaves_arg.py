from pydub import AudioSegment
from pydub.playback import play
import sys

#Load an audio file
audio1 = sys.argv[1]
audio2 = sys.argv[2]

sound1 = AudioSegment.from_mp3(audio1)
sound2 = AudioSegment.from_mp3(audio2)

combined = sound1.overlay(sound2, position=65) # positionでインスト音源とのずれを補正
play(combined)