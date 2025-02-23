# 替え歌合成システム「TalSing（トーシング）」
「喋るだけで替え歌が作れる」をキャッチコピーとした歌声合成を利用した新しい体験を提供します。  
## デモ動画
[!['TalSingデモ動画'](https://github.com/user-attachments/assets/ae5c8aad-43cb-4c10-97e7-32de75e7702f)](https://youtu.be/74o4dHv1goM)


## Documentation

- [**概要編**][docs-overview] &mdash; 制作のきっかけから実際に中で行われている処理、改良案の提案などシステム全体について説明しています。
- [**実践編**][docs-using] &mdash; ファイル構成や楽曲等データの追加方法についてなど、具体的なシステム使用方法を説明しています。

## Installation

現在のバージョンでは Windows 上で動作しません。

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


[docs-overview]: https://taiga-music-lab.com/%e6%9b%bf%e3%81%88%e6%ad%8c%e5%90%88%e6%88%90%e3%82%b7%e3%82%b9%e3%83%86%e3%83%a0%e3%80%8ctalsing%e3%80%8d%e3%81%ab%e9%96%a2%e3%81%99%e3%82%8b%e3%81%82%e3%82%8c%e3%81%93%e3%82%8c%e3%82%92%e3%81%be/
[docs-using]: https://taiga-music-lab.com/%e3%80%90%e5%ae%9f%e8%b7%b5%e7%b7%a8%e3%80%91%e9%96%8b%e7%99%ba%e3%82%92%e6%83%b3%e5%ae%9a%e3%81%97%e3%81%9ftalsing%e3%81%ae%e4%bd%bf%e3%81%84%e6%96%b9%e8%a7%a3%e8%aa%ac/
[nnsvs]: https://nnsvs.github.io/
[learned-model]: https://meijiuniversity-my.sharepoint.com/:f:/g/personal/cs242038_meiji_ac_jp/Ehu_2zD0DNpLphfZxWacxw4BbZSYyHb3G2VAAWxjkU5CgA?e=o3BiSE
