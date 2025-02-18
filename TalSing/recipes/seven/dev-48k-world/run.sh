#!/bin/bash

# Set bash to 'debug' mode, it will exit on :
# -e 'error', -u 'undefined variable', -o ... 'error in pipeline', -x 'print commands',
set -e
set -u
set -o pipefail

function xrun () {
    set -x
    $@
    set +x
}

refer=$5
refer_tex=$6

script_dir=$(cd $(dirname ${BASH_SOURCE:-$0}); pwd)
NNSVS_ROOT=$script_dir/../../../
NNSVS_COMMON_ROOT=$NNSVS_ROOT/recipes/_common/spsvs
. $NNSVS_ROOT/utils/yaml_parser.sh || exit 1;

FOR_SYNTHESIS_DIR=$script_dir/forSynthesis
FUNCTIONS_DIR=$script_dir/functions
ORIGINAL_FUNC_ROOT=$script_dir/../../../original_func

eval $(parse_yaml "./config.yaml" "")

train_set="train_no_dev"
dev_set="dev"
eval_set="eval"
gene_set="gene"
datasets=($train_set $dev_set $eval_set)
testsets=($dev_set $eval_set)
genesets=$gene_set

dumpdir=dump

dump_org_dir=$dumpdir/$spk/org
dump_norm_dir=$dumpdir/$spk/norm

stage=0
stop_stage=0

. $NNSVS_ROOT/utils/parse_options.sh || exit 1;

# exp name
if [ -z ${tag:=} ]; then
    expname=${spk}
else
    expname=${spk}_${tag}
fi
expdir=exp/$expname

if [ ${stage} -le -1 ] && [ ${stop_stage} -ge -1 ]; then
    if [ ! -d downloads/PJS_corpus_ver1.1 ]; then
        echo "stage -1: Downloading PJS"
        echo "run `pip install gdown` if you don't have it locally"
        mkdir -p downloads && cd downloads
        gdown "https://drive.google.com/uc?id=1hPHwOkSe2Vnq6hXrhVtzNskJjVMQmvN_"
        unzip PJS_corpus_ver1.1.zip
        cd -
    fi
fi

if [ ${stage} -le 0 ] && [ ${stop_stage} -ge 0 ]; then
    echo "stage 0: Data preparation"
    python $NNSVS_ROOT/recipes/_common/db/seven/data_prep.py SEVEN_DATABASE data/

    echo "train/dev/eval split"
    mkdir -p data/list
    # exclude utts that are not strictly aligned
    find data/acoustic/ -type f -name "*.wav" -exec basename {} .wav \; \
        | grep -v 030 | sort > data/list/utt_list.txt
    grep 01 data/list/utt_list.txt > data/list/$eval_set.list
    grep 02 data/list/utt_list.txt > data/list/$dev_set.list
    grep -v 01 data/list/utt_list.txt | grep -v 01 > data/list/$train_set.list
fi

# Run the rest of the steps
# Please check the script file for more details
. $NNSVS_COMMON_ROOT/run_common_steps_dev.sh
