#! /usr/bin/env python

import pysinsy
import sys
import os
import yaml

sinsy = pysinsy.Sinsy()

input_filename=sys.argv[1]
output_dir = sys.argv[2]
output_filepath = os.path.join(output_dir, input_filename.rsplit('/', 1)[1].split('.')[0] + '.lab')
# Set language to Japanese
assert sinsy.setLanguages("j", pysinsy.get_default_dic_dir())
assert sinsy.loadScoreFromMusicXML(input_filename)

is_mono = False
labels = sinsy.createLabelData(is_mono, 1, 1).getData()

with open(output_filepath, "w") as f:
    f.write("\n".join(labels))

sinsy.clearScore()