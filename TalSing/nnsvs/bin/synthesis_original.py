import os
from os.path import join

import hydra
import joblib
import numpy as np
import torch
from hydra.utils import to_absolute_path
from nnmnkwii.io import hts
from nnsvs.gen import (
    postprocess_acoustic,
    postprocess_waveform,
    predict_acoustic,
    predict_timing,
    predict_waveform,
)
from nnsvs.logger import getLogger
from nnsvs.util import extract_static_scaler, init_seed, load_utt_list, load_vocoder
from omegaconf import DictConfig, OmegaConf
from scipy.io import wavfile
from tqdm.auto import tqdm

from ipdb import set_trace as ipst
from MyLib import orgfiles as files
from pathlib import Path

### config ###

# Phone Duration
cl_append = False

# Edit Duration
editver = 2 # 編集アルゴリズムver
# 1:表拍の母音のdurを調節（表拍と裏拍のdurの総和が変わる）
# 2:表拍/裏拍両方のdurを調節（表拍と裏拍のdurの総和を維持）
testdur = True # 調整後のdurationが正しいかの確認をするか

##############
def makePhoneDurations(durations, phonemes):
    durations_mora = []
    durations_mora_sil = []
    mora = []
    mora_sil = []
    stock_dur = 0
    stock_phone = ''
    for dur, ph in zip(durations, phonemes):
        if ph == 'sil' or ph == 'pau':
            durations_mora_sil.append(dur)
            mora_sil.append(ph)
        elif ph in ['a', 'i', 'u', 'e', 'o', 'N', 'cl']: # 母音と/N/のタイミングで新しいリストに追加
            if ph == 'cl' and cl_append == False: # /cl/のときだけ例外処理（直前のモーラと同じ扱い）
                durations_mora[-1] = float(durations_mora[-1]) + float(dur)
                durations_mora_sil[-1] = float(durations_mora[-1]) + float(dur)
                mora[-1] = mora[-1] + 'cl'
                mora_sil[-1] = mora_sil[-1] + 'cl'
                stock_dur = 0
                stock_phone = ''
            else:
                stock_dur += dur
                stock_phone += ph
                durations_mora.append(stock_dur)
                durations_mora_sil.append(stock_dur)
                mora.append(stock_phone)
                mora_sil.append(stock_phone)
                stock_dur = 0
                stock_phone = ''
        else:
            stock_dur += dur
            stock_phone += ph
    # print(f"Mora Durations({len(durations_mora)}) : {[round(d, 3) for d in durations_mora]}")
    # print(f"Mora({len(mora)}) : {mora}")

    return durations_mora, durations_mora_sil, mora, mora_sil

def editDuration(label, sw_ratio):
    start = 0
    durations = []
    phones = []
    for line in label:
        end = int(line[1])
        durations.append(end - start)
        start = int(line[1])
        phones.append(line[2].split('+')[0].split('-')[1])

    durations_mora, durations_mora_sil, mora, mora_sil = makePhoneDurations(durations, phones)

    # print(f"Durations_mora({len(durations_mora)}) : {durations_mora}")
    # print(f"Mora({len(durations_mora)}) : {mora}")
    # l = [(d, p) for d, p in zip(durations, phones)]
    # print(l)

    # duration調節
    new_durations = [] # 調整後のdurations
    d_m1, d_m2 = [], [] # 表拍/裏拍の各モーラのduration(音素ごとに格納)
    moraNo = 0 # 対象としているモーラ
    fill1, fill2 = False, False
    for d, p in zip(durations, phones):
        if p not in ['sil', 'pau']:
            # 比率調節
            if sum(d_m1) < durations_mora[moraNo] and fill1 == False:
                d_m1.append(d)
            elif sum(d_m2) < durations_mora[moraNo] and fill2 == False:
                if fill1 == False:
                    fill1 = True
                    moraNo += 1
                d_m2.append(d)
                if sum(d_m2) == durations_mora[moraNo]:
                    if fill2 == False:
                        fill2 = True
                        moraNo += 1
                    if editver == 1:
                        # ratio = sum(d_m1) / sum(d_m2)
                        diff = sw_ratio * sum(d_m2) - sum(d_m1)
                        d_m1[-1] += diff
                        new_durations += d_m1
                        new_durations += d_m2
                    elif editver == 2:
                        totaldur = sum(d_m1) + sum(d_m2)
                        ideal_m2 = totaldur / (sw_ratio + 1) # 理想の裏拍のduration
                        ideal_m1 = totaldur - ideal_m2 # 理想の表拍のduration
                        if len(d_m1) == 2: # 表拍に子音が含まれる時
                            phRatio = d_m1[0] / sum(d_m1) # 表拍における子音の比率
                            d_m1[0] = ideal_m1 * phRatio
                            d_m1[1] = ideal_m1 - d_m1[0]
                        else: # 表拍が母音のみの時
                            d_m1 = [ideal_m1]
                        if len(d_m2) == 2: # 裏拍に子音が含まれる時
                            phRatio = d_m2[0] / sum(d_m2) # 裏拍における子音の比率
                            d_m2[0] = ideal_m2 * phRatio
                            d_m2[1] = ideal_m2 - d_m2[0]
                        else: # 裏拍が母音のみの時
                            d_m2 = [ideal_m2]
                        new_durations += d_m1
                        new_durations += d_m2
                        
                    assert round(sum(d_m1) / sum(d_m2), 2) == sw_ratio, f'適切な比率に調整できませんでした(ratio={round(sum(d_m1) / sum(d_m2), 2)})'
                    
                    d_m1, d_m2 = [], []
                    fill1, fill2 = False, False
        else:
            if d_m1 != []: # 最後の表拍
                new_durations += d_m1
            new_durations.append(d)

    assert len(durations) == len(new_durations), '調整前後のdurationの長さが一致しません'
    # 正しく調整されてるかの確認用
    if testdur:
        new_durations_mora, new_durations_mora_sil, new_mora, new_mora_sil = makePhoneDurations(new_durations, phones)
        for i in range((len(new_durations_mora))//2):
            if round(new_durations_mora[i*2] / new_durations_mora[i*2+1], 2) != sw_ratio:
                print(f"Ratio = {new_durations_mora[i*2] / new_durations_mora[i*2+1]}")
                print(f"Diff = {sw_ratio * new_durations_mora[i*2+1] - new_durations_mora[i*2]}")
                print(f"Tar Phone : {new_mora[i*2 : i*2+2]}")
            assert round(new_durations_mora[i*2] / new_durations_mora[i*2+1], 2) == sw_ratio

    # 調整後のdurationsで新規ラベル作成
    new_fullLabel = hts.HTSLabelFile()
    start, end = 0, 0
    for id, line in enumerate(label):
        if id != 0:
            start += new_durations[id - 1]
        end += new_durations[id]
        if start >= end:
            print("start >= end")
            ipst()
        new_fullLabel.append((start, end, label[id][2]))

    return new_fullLabel

@hydra.main(config_path="conf/synthesis", config_name="config")
def my_app(config: DictConfig) -> None:
    global logger
    logger = getLogger(config.verbose)
    logger.info(OmegaConf.to_yaml(config))

    if not torch.cuda.is_available():
        device = torch.device("cpu")
    else:
        device = torch.device(config.device)

    # timelag
    timelag_config = OmegaConf.load(to_absolute_path(config.timelag.model_yaml))
    timelag_model = hydra.utils.instantiate(timelag_config.netG).to(device)
    checkpoint = torch.load(
        to_absolute_path(config.timelag.checkpoint),
        map_location=lambda storage, loc: storage,
    )
    timelag_model.load_state_dict(checkpoint["state_dict"])
    timelag_in_scaler = joblib.load(to_absolute_path(config.timelag.in_scaler_path))
    timelag_out_scaler = joblib.load(to_absolute_path(config.timelag.out_scaler_path))
    timelag_model.eval()

    # duration
    duration_config = OmegaConf.load(to_absolute_path(config.duration.model_yaml))
    duration_model = hydra.utils.instantiate(duration_config.netG).to(device)
    checkpoint = torch.load(
        to_absolute_path(config.duration.checkpoint),
        map_location=lambda storage, loc: storage,
    )
    duration_model.load_state_dict(checkpoint["state_dict"])
    duration_in_scaler = joblib.load(to_absolute_path(config.duration.in_scaler_path))
    duration_out_scaler = joblib.load(to_absolute_path(config.duration.out_scaler_path))
    duration_model.eval()

    # acoustic model
    acoustic_config = OmegaConf.load(to_absolute_path(config.acoustic.model_yaml))
    acoustic_model = hydra.utils.instantiate(acoustic_config.netG).to(device)
    checkpoint = torch.load(
        to_absolute_path(config.acoustic.checkpoint),
        map_location=lambda storage, loc: storage,
    )
    acoustic_model.load_state_dict(checkpoint["state_dict"])
    acoustic_in_scaler = joblib.load(to_absolute_path(config.acoustic.in_scaler_path))
    acoustic_out_scaler = joblib.load(to_absolute_path(config.acoustic.out_scaler_path))
    acoustic_model.eval()                                                                                                             

    # NOTE: this is used for GV post-filtering
    acoustic_out_static_scaler = extract_static_scaler(
        acoustic_out_scaler, acoustic_config
    )

    # Vocoder
    if config.vocoder.checkpoint is not None and len(config.vocoder.checkpoint) > 0:
        vocoder, vocoder_in_scaler, vocoder_config = load_vocoder(
            to_absolute_path(config.vocoder.checkpoint),
            device,
            acoustic_config,
        )
    else:
        vocoder, vocoder_in_scaler, vocoder_config = None, None, None
        if config.synthesis.vocoder_type != "world":
            logger.warning("Vocoder checkpoint is not specified")
            logger.info(f"Use world instead of {config.synthesis.vocoder_type}.")
        config.synthesis.vocoder_type = "world"

    # Run synthesis for each utt.
    binary_dict, numeric_dict = hts.load_question_set(
        to_absolute_path(config.synthesis.qst)
    )

    in_dir = to_absolute_path(config.in_dir)
    out_dir = to_absolute_path(config.out_dir)
    os.makedirs(out_dir, exist_ok=True)
    xml_ids = files.getFilenames(to_absolute_path(config.xml_dir), remove_ext=True)
    # utt_ids = load_utt_list(to_absolute_path(config.utt_list))

    logger.info("Processes %s utterances...", len(xml_ids))
    for utt_id in tqdm(xml_ids):
        labels = hts.load(join(in_dir, f"{utt_id}.lab"))
        hts_frame_shift = int(config.synthesis.frame_period * 1e4)
        labels.frame_shift = hts_frame_shift
        init_seed(1234)

        if config.synthesis.ground_truth_duration:
            duration_modified_labels = labels
        else:
            duration_modified_labels = predict_timing(
                device=device,
                labels=labels,
                binary_dict=binary_dict,
                numeric_dict=numeric_dict,
                timelag_model=timelag_model,
                timelag_config=timelag_config,
                timelag_in_scaler=timelag_in_scaler,
                timelag_out_scaler=timelag_out_scaler,
                duration_model=duration_model,
                duration_config=duration_config,
                duration_in_scaler=duration_in_scaler,
                duration_out_scaler=duration_out_scaler,
                log_f0_conditioning=config.synthesis.log_f0_conditioning,
                allowed_range=config.timelag.allowed_range,
                allowed_range_rest=config.timelag.allowed_range_rest,
                force_clip_input_features=config.timelag.force_clip_input_features,
                frame_period=config.synthesis.frame_period,
            )
        
        # Duratoinモデルの出力ラベルを保存
        # fulllab_aftdur_path = join(Path(in_dir).parent, f"full_lab_afterDurationModel/{utt_id}.lab")
        # with open(fulllab_aftdur_path, 'w') as f:
        #     for line in duration_modified_labels:
        #         f.write(f"{line[0]} {line[1]} {line[2]}\n")

        # swing調節
        if config.swingRatio != None:
            duration_modified_labels = editDuration(duration_modified_labels, config.swingRatio)

        # Predict acoustic features
        acoustic_features = predict_acoustic(
            device=device,
            labels=duration_modified_labels,
            acoustic_model=acoustic_model,
            acoustic_config=acoustic_config,
            acoustic_in_scaler=acoustic_in_scaler,
            acoustic_out_scaler=acoustic_out_scaler,
            binary_dict=binary_dict,
            numeric_dict=numeric_dict,
            subphone_features=config.synthesis.subphone_features,
            log_f0_conditioning=config.synthesis.log_f0_conditioning,
            force_clip_input_features=config.acoustic.force_clip_input_features,
            f0_shift_in_cent=config.synthesis.pre_f0_shift_in_cent,
        )

        # NOTE: the output of this function is tuple of features
        # e.g., (mgc, lf0, vuv, bap)
        multistream_features = postprocess_acoustic(
            device=device,
            acoustic_features=acoustic_features,
            duration_modified_labels=duration_modified_labels,
            binary_dict=binary_dict,
            numeric_dict=numeric_dict,
            acoustic_config=acoustic_config,
            acoustic_out_static_scaler=acoustic_out_static_scaler,
            postfilter_model=None,  # NOTE: learned post-filter is not supported
            postfilter_config=None,
            postfilter_out_scaler=None,
            sample_rate=config.synthesis.sample_rate,
            frame_period=config.synthesis.frame_period,
            relative_f0=config.synthesis.relative_f0,
            feature_type=config.synthesis.feature_type,
            post_filter_type=config.synthesis.post_filter_type,
            trajectory_smoothing=config.synthesis.trajectory_smoothing,
            trajectory_smoothing_cutoff=config.synthesis.trajectory_smoothing_cutoff,
            trajectory_smoothing_cutoff_f0=config.synthesis.trajectory_smoothing_cutoff_f0,
            vuv_threshold=config.synthesis.vuv_threshold,
            f0_shift_in_cent=config.synthesis.post_f0_shift_in_cent,
            vibrato_scale=1.0,
            force_fix_vuv=config.synthesis.force_fix_vuv,
        )

        # Generate waveform by vocoder
        wav = predict_waveform(
            device=device,
            multistream_features=multistream_features,
            vocoder=vocoder,
            vocoder_config=vocoder_config,
            vocoder_in_scaler=vocoder_in_scaler,
            sample_rate=config.synthesis.sample_rate,
            frame_period=config.synthesis.frame_period,
            use_world_codec=config.synthesis.use_world_codec,
            feature_type=config.synthesis.feature_type,
            vocoder_type=config.synthesis.vocoder_type,
            vuv_threshold=config.synthesis.vuv_threshold,
        )

        wav = postprocess_waveform(
            wav=wav,
            sample_rate=config.synthesis.sample_rate,
            dtype=np.int16,
            peak_norm=False,
            loudness_norm=False,
        )

        out_wav_path = join(to_absolute_path(out_dir), f"{utt_id}.wav")
        wavfile.write(
            out_wav_path, rate=config.synthesis.sample_rate, data=wav.astype(np.int16)
        )


def entry():
    my_app()  # pylint: disable=no-value-for-parameter


if __name__ == "__main__":
    my_app()  # pylint: disable=no-value-for-parameter
