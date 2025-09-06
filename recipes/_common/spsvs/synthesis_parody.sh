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

echo "STEP 1: Create Parody Score."
# xrun python $ORIGINAL_FUNC_ROOT/makeparoscore.py $FOR_SYNTHESIS_DIR/xml_refer/${refer}.xml $FOR_SYNTHESIS_DIR/lyric.txt # for text file
xrun python $FUNCTIONS_DIR/makeparoscore.py $FOR_SYNTHESIS_DIR/xml_refer/${refer}.xml $FOR_SYNTHESIS_DIR/lyric.txt $refer_tex
IFS=/ file_name=$(basename "$(ls -t "$FOR_SYNTHESIS_DIR/xml_paro" | head -1)" .xml) IFS=' '

echo "STEP 2: Convert xml to lab."
xrun python $FUNCTIONS_DIR/xml2lab.py $FOR_SYNTHESIS_DIR/xml_paro/${file_name}.xml $FOR_SYNTHESIS_DIR/../data/acoustic/label_phone_score

echo "STEP 3: Synthesize waveforms."
ground_truth_duration=false
xrun python $NNSVS_ROOT/nnsvs/bin/synthesis_parody.py $ext \
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
    in_dir=data/acoustic/label_phone_score/ \
    out_dir=$FOR_SYNTHESIS_DIR/result \
    file_name=$file_name \
    refer_no=$refer