import os
from os.path import join
import glob
import subprocess
import sys
from pathlib import Path
import shutil
import yaml
from ipdb import set_trace as ipst

def parse_yaml_config(config_path):
    # yaml_parser.shの代替：簡単な辞書変換
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
    
env = os.environ.copy() # 環境変数読み込み

# ディレクトリ設定
script_dir = Path(__file__).resolve().parent
NNSVS_ROOT = script_dir / "../../../"
NNSVS_COMMON_ROOT = NNSVS_ROOT / "recipes/_common/spsvs"
FOR_SYNTHESIS_DIR = script_dir / "forSynthesis"
FUNCTIONS_DIR = script_dir / "functions"
ORIGINAL_FUNC_ROOT = script_dir / "../../../original_func"

# config.yamlの読み込み
# with open("config.yaml") as f:
#     config = yaml.safe_load(f)

# # 環境変数としてセット（全て文字列に変換しておくと安全）
# for key, value in config.items():
#     os.environ[key] = str(value)
spk = env['SPK']

train_set = "train_no_dev"
dev_set = "dev"
eval_set = "eval"
gen_set = "gen"
datasets = [train_set, dev_set, eval_set]
testsets = [dev_set, eval_set]
genesets = gen_set

dumpdir = "dump"
dump_org_dir = Path(dumpdir) / spk / "org"
dump_norm_dir = Path(dumpdir) / spk / "norm"

tag = env['TAG'] # tag読み込み

# exp名の決定
expname = spk
expdir = Path("exp") / expname

def xrun(cmd, cwd=None):
    print(f"+ {cmd}")
    if cwd == None:
        subprocess.run(cmd, shell=True, check=True)
    else:
        subprocess.run(cmd, cwd=cwd, shell=True, check=True)

def synthesis_parody_sh():
    # 環境変数や事前定義変数の取得
    script_dir = os.path.dirname(os.path.abspath(__file__))
    NNSVS_ROOT = os.path.abspath(join(script_dir, "../../../"))
    FOR_SYNTHESIS_DIR = os.path.abspath("./forSynthesis")
    FUNCTIONS_DIR = os.path.abspath("./functions")
    timelag_eval_checkpoint = env["TIMELAG_EVAL_CHECKPOINT"]
    duration_eval_checkpoint = env["DURATION_EVAL_CHECKPOINT"]
    acoustic_eval_checkpoint = env["ACOUSTIC_EVAL_CHECKPOINT"]
    vocoder_eval_checkpoint = env["VOCODER_EVAL_CHECKPOINT"]
    vocoder_model = env["VOCODER_MODEL"]
    timelag_model = env["TIMELAG_MODEL"]
    duration_model = env["DURATION_MODEL"]
    acoustic_model = env["ACOUSTIC_MODEL"]
    refer = env["REFER_NUMBER"]
    refer_tex = env["REFER_TEXT"]
    sample_rate = env["SAMPLE_RATE"]
    question_path = env["QUESTION_PATH"]
    synthesis = env["SYNTHESIS"]
    file_name = ""
    compOnOff = env["COMP_ONOFF"]
    python_path = env["VIRTUAL_PYTHON_PATH"]
    python_path_abs = os.path.abspath(python_path)
    os.environ["PYTHONUTF8"] = "1" # エンコード設定

    # vocoder_eval_checkpointの決定
    if not vocoder_eval_checkpoint:
        if vocoder_model:
            pkl_files = sorted(
                glob.glob(join(expdir, vocoder_model, "*.pkl")),
                key=os.path.getmtime,
                reverse=True
            )
            if pkl_files:
                vocoder_eval_checkpoint = pkl_files[0]

    # dst_nameの決定
    if not vocoder_eval_checkpoint:
        dst_name = f"synthesis_{timelag_model}_{duration_model}_{acoustic_model}_world"
    else:
        if vocoder_model:
            dst_name = f"synthesis_{timelag_model}_{duration_model}_{acoustic_model}_{vocoder_model}"
        else:
            vocoder_name = os.path.basename(os.path.dirname(vocoder_eval_checkpoint))
            dst_name = f"synthesis_{timelag_model}_{duration_model}_{acoustic_model}_{vocoder_name}"

    print("STEP 1: Create Parody Score.")
    xrun(f'{python_path_abs} {join(FUNCTIONS_DIR, "makeparoscore.py")} {FOR_SYNTHESIS_DIR}/xml_refer/{refer}.xml {FOR_SYNTHESIS_DIR}/lyric.txt {refer_tex}')

    # xml_paroディレクトリ内の最新ファイル名取得
    xml_paro_dir = os.path.join(FOR_SYNTHESIS_DIR, "xml_paro")
    xml_files = sorted(
        glob.glob(os.path.join(xml_paro_dir, "*.xml")),
        key=os.path.getmtime,
        reverse=True
    )
    if xml_files:
        file_name = os.path.splitext(os.path.basename(xml_files[0]))[0]
    else:
        raise FileNotFoundError("No xml files found in xml_paro directory.")

    print("STEP 2: Convert xml to lab.")
    xrun(f'{python_path_abs} {FUNCTIONS_DIR}/xml2lab.py {xml_paro_dir}/{file_name}.xml {FOR_SYNTHESIS_DIR}/../data/acoustic/label_phone_score')

    print("STEP 3: Synthesize waveforms.")
    ground_truth_duration = "false"
    # ext = "--config-dir conf/synthesis" if os.path.isdir("conf/synthesis") else ""
    # ext = "--config-dir conf/synthesis"
    ext = ""
    xrun(
        f'{python_path_abs} {NNSVS_ROOT}/nnsvs/bin/synthesis_parody.py {ext}'
        f'synthesis={synthesis} '
        f'synthesis.sample_rate={sample_rate} '
        f'synthesis.qst={question_path} '
        f'synthesis.ground_truth_duration={ground_truth_duration} '
        f'timelag.checkpoint={expdir}/{timelag_model}/{timelag_eval_checkpoint} '
        f'timelag.in_scaler_path={dump_norm_dir}/in_timelag_scaler.joblib '
        f'timelag.out_scaler_path={dump_norm_dir}/out_timelag_scaler.joblib '
        f'timelag.model_yaml={expdir}/{timelag_model}/model.yaml '
        f'duration.checkpoint={expdir}/{duration_model}/{duration_eval_checkpoint} '
        f'duration.in_scaler_path={dump_norm_dir}/in_duration_scaler.joblib '
        f'duration.out_scaler_path={dump_norm_dir}/out_duration_scaler.joblib '
        f'duration.model_yaml={expdir}/{duration_model}/model.yaml '
        f'acoustic.checkpoint={expdir}/{acoustic_model}/{acoustic_eval_checkpoint} '
        f'acoustic.in_scaler_path={dump_norm_dir}/in_acoustic_scaler.joblib '
        f'acoustic.out_scaler_path={dump_norm_dir}/out_acoustic_scaler.joblib '
        f'acoustic.model_yaml={expdir}/{acoustic_model}/model.yaml '
        f'vocoder.checkpoint={vocoder_eval_checkpoint} '
        f'in_dir=data/acoustic/label_phone_score/ '
        f'out_dir={FOR_SYNTHESIS_DIR}/result '
        f'file_name={file_name} '
        f'refer_no={refer}',
        cwd=f"{NNSVS_ROOT}/nnsvs/bin"
    )

    if compOnOff == 'ON':
        print("STEP 4: Apply Compressor")
        xrun(
            f'{python_path_abs} {join(FUNCTIONS_DIR, "applyCompressor.py")} '
            f'{FOR_SYNTHESIS_DIR}/result/{file_name}_{refer}.wav'
        )
        


if __name__ == '__main__':
    synthesis_parody_sh()