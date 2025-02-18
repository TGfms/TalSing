import wave as wave
import pyroomacoustics as pa
import numpy as np
import scipy.signal as sp
import scipy as scipy

#順列計算に使用
import itertools 
import time

#コントラスト関数の微分（球対称ラプラス分布を仮定）
#s_hat: 分離信号（M, Nk, Lt）
#M: マイクロホン数
#Nk: 周波数の数
#Lt: 雑音除去後の信号
def phi_laplacian(s_hat):

    norm=np.abs(s_hat)
    phi=s_hat/np.maximum(norm, 1.e-18)
    return(phi)


#コントラスト関数（球対称ラプラス分布を仮定）
#s_hat: 分離信号(M, Nk, Lt)
def contrast_laplacian(s_hat):
    norm=2.*np.abs(s_hat)
    return(norm)

#ICAによる分離フィルタ更新
#x:入力信号(M, Nk, Lt)
#W: 分離フィルタ(Nk,M,M)
#mu: 更新係数
#n_ica_iterations: 繰り返しステップ数
#phi_func: コントラスト関数の微分を与える関数
#contrast_func: コントラスト関数
#is_use_non_holonomic: True (非ホロノミック拘束を用いる） False (用いない）
#return W 分離フィルタ(Nk,M,M) s_hat 出力信号(M,Nk, Lt),cost_buff ICAのコスト (T)
def execute_natural_gradient_ica(x,W,phi_func=phi_laplacian,contrast_func=contrast_laplacian,mu=1.0,
                                 n_ica_iterations=20,is_use_non_holonomic=True):
    M=np.shape(x)[0]

    cost_buff=[]
    for t in range(n_ica_iterations):
        #音源分離信号を得る
        s_hat=np.einsum('kmn,nkt->mkt',W,x)
        
        #コントラスト関数を計算
        G=contrast_func(s_hat)
        
        #コストを計算
        cost=np.sum(np.mean(G,axis=-1))-np.sum(2.*np.log(np.abs(np.linalg.det(W)) ))
        cost_buff.append(cost)

        #コンストラクト関数の微分を取得
        phi=phi_func(s_hat)

        phi_s=np.einsum('mkt,nkt->ktmn',phi,np.conjugate(s_hat))
        phi_s=np.mean(phi_s,axis=1)

        I=np.eye(M,M)
        if is_use_non_holonomic==False:
            deltaW=np.einsum('kmi,kin->kmn',I[None,...]-phi_s,W)
        else:
            mask=(np.ones((M,M))-I)[None,...]
            deltaW=np.einsum('kmi,kin->kmn',np.multiply(mask,-phi_s),W)

        #フィルタを更新する
        W=W+mu*deltaW
    
    #最後に出力信号を分離
    s_hat=np.einsum('kmn,nkt->mkt',W,x)

    return(W,s_hat,cost_buff)




#周波数間の振幅相関に基づくパーミュテーション解法
#s_hat: M,Nk,Lt
#return permutation_index_result：周波数毎のパーミュテーション解 
def solver_inter_frequency_permutation(s_hat):
    n_sources=np.shape(s_hat)[0]
    n_freqs=np.shape(s_hat)[1]
    n_frames=np.shape(s_hat)[2]

    s_hat_abs=np.abs(s_hat)

    norm_amp=np.sqrt(np.sum(np.square(s_hat_abs),axis=0,keepdims=True))
    s_hat_abs=s_hat_abs/np.maximum(norm_amp,1.e-18)

    spectral_similarity=np.einsum('mkt,nkt->k',s_hat_abs,s_hat_abs)
    
    frequency_order=np.argsort(spectral_similarity)
    
    #音源間の相関が最も低い周波数からパーミュテーションを解く
    is_first=True
    permutations=list(itertools.permutations(range(n_sources)))
    permutation_index_result={}
    
    for freq in frequency_order:
        
        if is_first==True:
            is_first=False

            #初期値を設定する
            accumurate_s_abs=s_hat_abs[:,frequency_order[0],:]
            permutation_index_result[freq]=range(n_sources)
        else:
            max_correlation=0
            max_correlation_perm=None
            for perm in permutations:
                s_hat_abs_temp=s_hat_abs[list(perm),freq,:]
                correlation=np.sum(accumurate_s_abs*s_hat_abs_temp)
                
                
                if max_correlation_perm is None:
                    max_correlation_perm=list(perm)
                    max_correlation=correlation
                elif max_correlation < correlation:
                    max_correlation=correlation
                    max_correlation_perm=list(perm)
            permutation_index_result[freq]=max_correlation_perm
            accumurate_s_abs+=s_hat_abs[max_correlation_perm,freq,:]
   
    return(permutation_index_result)
    

#プロジェクションバックで最終的な出力信号を求める
#s_hat: M,Nk,Lt
#W: 分離フィルタ(Nk,M,M)
#retunr c_hat: マイクロホン位置での分離結果(M,M,Nk,Lt)
def projection_back(s_hat,W):
    
    #ステアリングベクトルを推定
    A=np.linalg.pinv(W)
    c_hat=np.einsum('kmi,ikt->mikt',A,s_hat)
    return(c_hat)


#2バイトに変換してファイルに保存
#signal: time-domain 1d array (float)
#file_name: 出力先のファイル名
#sample_rate: サンプリングレート
def write_file_from_time_signal(signal,file_name,sample_rate):
    #2バイトのデータに変換
    signal=signal.astype(np.int16)

    #waveファイルに書き込む
    wave_out = wave.open(file_name, 'w')

    #モノラル:1、ステレオ:2
    wave_out.setnchannels(1)

    #サンプルサイズ2byte
    wave_out.setsampwidth(2)

    #サンプリング周波数
    wave_out.setframerate(sample_rate)

    #データを書き込み
    wave_out.writeframes(signal)

    #ファイルを閉じる
    wave_out.close()


#SNRをはかる
#desired: 目的音、Lt
#out:　雑音除去後の信号 Lt
def calculate_snr(desired,out):
    wave_length=np.minimum(np.shape(desired)[0],np.shape(out)[0])

    #消し残った雑音
    desired=desired[:wave_length]
    out=out[:wave_length]
    noise=desired-out
    snr=10.*np.log10(np.sum(np.square(desired))/np.sum(np.square(noise)))

    return(snr)



