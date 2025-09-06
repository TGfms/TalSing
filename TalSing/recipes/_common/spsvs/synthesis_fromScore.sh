# NOTE: the script is supposed to be used called from nnsvs recipes.
# Please don't try to run the shell script directory.

if [ -d conf/synthesis ]; then
    ext="--config-dir conf/synthesis"
else
    ext=""
fi

if [ -z $timelag_eval_checkpoint ]; then
    timelag_eval_checkpoint=best_loss.pth
fi
if [ -z $duration_eval_checkpoint ]; then
    duration_eval_checkpoint=best_loss.pth
fi
if [ -z $acoustic_eval_checkpoint ]; then
    acoustic_eval_checkpoint=latest.pth
fi

if [ -z "${vocoder_eval_checkpoint}" ]; then
    if [ ! -z "${vocoder_model}" ]; then
        vocoder_eval_checkpoint="$(ls -dt "${expdir}/${vocoder_model}"/*.pkl | head -1 || true)"
    fi
fi

if [ -z "${vocoder_eval_checkpoint}" ]; then
    dst_name=synthesis_${timelag_model}_${duration_model}_${acoustic_model}_world
else
    if [ ! -z "${vocoder_model}" ]; then
        dst_name=synthesis_${timelag_model}_${duration_model}_${acoustic_model}_${vocoder_model}
    else
        vocoder_name=$(dirname ${vocoder_eval_checkpoint})
        vocoder_name=$(basename $vocoder_name)
        dst_name=synthesis_${timelag_model}_${duration_model}_${acoustic_model}_${vocoder_name}
    fi
fi

echo "- STEP 1: Convert xml to full lab. -"
fulllab_dir="${script_dir}/songs/${title}/full_lab"
xml_dir="${script_dir}/songs/${title}/xml"
if [ ! -d "$fulllab_dir" ]; then
    mkdir -p "$fulllab_dir"
fi
if [ ! -d "$xml_dir" ]; then
    mkdir "$xml_dir"
fi
cp $script_dir/xml/${title}.xml $xml_dir/${title}.xml
xrun python $script_dir/functions/xml2lab.py $xml_dir/${title}.xml $fulllab_dir

# xrun python $script_dir/functions/makeDatasetFolder.py $title 
wav_dir="${script_dir}/songs/${title}/result"
if [ ! -d "$wav_dir" ]; then
    mkdir "$wav_dir"
fi

echo "- STEP 2: Synthesize waves. -"
# for s in ${testsets[@]}; do
for s in ${gen_set[@]}; do
    for input in label_phone_score; do
        if [ $input = label_phone_score ]; then
            ground_truth_duration=false
        else
            ground_truth_duration=true
        fi

        xrun python $NNSVS_ROOT/nnsvs/bin/synthesis_original.py $ext \
            synthesis=$synthesis \
            synthesis.sample_rate=$sample_rate \
            synthesis.qst=$question_path \
            synthesis.ground_truth_duration=$ground_truth_duration \
            timelag.checkpoint=$expdir/${timelag_model}/$timelag_eval_checkpoint \
            timelag.in_scaler_path=$dump_norm_dir/in_timelag_scaler.joblib \
            timelag.out_scaler_path=$dump_norm_dir/out_timelag_scaler.joblib \
            timelag.model_yaml=$expdir/${timelag_model}/model.yaml \
            duration.checkpoint=$expdir/${duration_model}/$duration_eval_checkpoint \
            duration.in_scaler_path=$dump_norm_dir/in_duration_scaler.joblib \
            duration.out_scaler_path=$dump_norm_dir/out_duration_scaler.joblib \
            duration.model_yaml=$expdir/${duration_model}/model.yaml \
            acoustic.checkpoint=$expdir/${acoustic_model}/$acoustic_eval_checkpoint \
            acoustic.in_scaler_path=$dump_norm_dir/in_acoustic_scaler.joblib \
            acoustic.out_scaler_path=$dump_norm_dir/out_acoustic_scaler.joblib \
            acoustic.model_yaml=$expdir/${acoustic_model}/model.yaml \
            vocoder.checkpoint=$vocoder_eval_checkpoint \
            in_dir=./songs/$title/full_lab \
            xml_dir=./songs/$title/xml \
            out_dir=./songs/$title/result
    done
done
