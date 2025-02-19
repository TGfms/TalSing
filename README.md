# 替え歌合成システム「TalSing（トーシング）」
「喋るだけで替え歌が作れる」をキャッチコピーとした歌声合成を利用した新しい体験を提供します。  
## デモ動画
[!['TalSingデモ動画'](https://github.com/user-attachments/assets/ae5c8aad-43cb-4c10-97e7-32de75e7702f)](https://youtu.be/74o4dHv1goM)


## Documentation

- [**概要編**][docs-overview] &mdash; 制作のきっかけから実際に中で行われている処理、改良案の提案などシステム全体について説明しています。
- [**実践編**][docs-using] &mdash; ファイル構成や楽曲等データの追加方法についてなど、具体的なシステム使用方法を説明しています。

## Installation
1. まずはシステム本体をダウンロードします。画面右上の Code タブからZipをダウンロードするか、以下のコマンドからダウンロード可能です。
   
   ```
   git clone https://github.com/TGfms/TalSing.git
   ```
    
2. 以下のリンクから合成に必要な学習済み歌声モデルをダウンロードします。
   もしくは任意の歌声モデルの使用も可能です。その場合は当システムで使用している歌声合成システム[NNSVS][nnsvs]の仕様を参考にしてください。
   
    学習済み歌声モデル(約12GB): [URL][learned-model]

   ダウンロードファイル展開後、中に入っている dump, exp フォルダを TalSing/recipes/seven/dev-48k-world 下に配置します。

3. システムに必要なライブラリをインストールします。

   ```
   cd TalSing
   pip install -r requirements.txt
   ```

4. インストールは完了です。以下のコマンドからGUI画面を起動できます。

   ```
   cd ./TalSing/recipes/seven/dev-48k-world
   python talsing_gui.py
   ```

## Information
- HomePage: https://taiga-music-lab.com/  
- GitHub: https://github.com/TGfms  
- X: https://x.com/LabTaiga  
- YouTube: https://www.youtube.com/@TaigaMusicLab31  


[docs-overview]: https://taiga-music-lab.com/
[docs-using]: https://taiga-music-lab.com/
[nnsvs]: https://nnsvs.github.io/
[learned-model]: https://taiga-music-lab.com/
