<!-- 顶部标题 & 统计徽章 -->
<div align="center">
  <h1 style="margin-top: 0" align="center">Python API for JMComic</h1>

  <p align="center">
    <a href="../../README.md">简体中文</a> •
    <a href="./README-en.md">English</a> •
    <strong>日本語</strong> •
    <a href="./README-kr.md">한국어</a>
  </p>

  <p align="center">
  <strong>JMComicへアクセスするためのPython API（Web版＆モバイル版）を提供し、GitHub Actionsダウンローダーも統合しています🚀</strong>
  </p>

[![GitHub](https://img.shields.io/badge/-GitHub-181717?logo=github)](https://github.com/hect0x7)
[![Stars](https://img.shields.io/github/stars/hect0x7/JMComic-Crawler-Python?color=orange&label=stars&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/stargazers)
[![Forks](https://img.shields.io/github/forks/hect0x7/JMComic-Crawler-Python?color=green&label=forks&style=flat)](https://github.com/hect0x7/JMComic-Crawler-Python/forks)
[![GitHub latest releases](https://img.shields.io/github/v/release/hect0x7/JMComic-Crawler-Python?color=blue&label=version)](https://github.com/hect0x7/JMComic-Crawler-Python/releases/latest)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/jmcomic?style=flat&color=hotpink)](https://pepy.tech/projects/jmcomic)
[![Licence](https://img.shields.io/github/license/hect0x7/JMComic-Crawler-Python?color=red)](https://github.com/hect0x7/JMComic-Crawler-Python)

</div>




> 本プロジェクトは、JMのクローラー用のPython APIをカプセル化したものです。
> 
> 数行のPythonコードだけで、JM上のアルバムをローカルへダウンロードすることができます。ダウンロードされた画像は完全に処理済みです。
> 
> **🧭 クイックガイド**
> - [チュートリアル: GitHub Actionsを使ってダウンロードする](../docs/sources/tutorial/1_github_actions.md)
> - [チュートリアル: お気に入りのデータをエクスポートしてダウンロードする](../docs/sources/tutorial/10_export_favorites.md)
> - [タワーブロードキャスト: 機長のみなさん、参加とコード提供を歓迎します](../../CONTRIBUTING.md)
> 
> **ご案内：JMのサーバー負荷を軽減するため、一度に大量のダウンロードは控えてください 🙏🙏🙏**


![introduction.jpg](../docs/sources/images/introduction.jpg)


## プロジェクトの紹介

本プロジェクトのコア機能は「アルバムのダウンロード」です。

これを基に、使いやすく、拡張性が高く、また特殊なダウンロード要求にも対応できるフレームワークを設計しました。

現在、主要機能の実装は比較的安定しており、プロジェクトはメンテナンス段階にあります。

ダウンロード機能以外にも、必要に応じて他のJMインターフェースも実装しています。既存の機能は以下の通りです：

- ログイン
- アルバム検索（すべての検索条件をサポート）
- 画像のダウンロードおよびデコード
- カテゴリ / ランキング
- アルバム / 各チャプター（エピソード）の詳細
- 個人のお気に入り
- インターフェースの暗号化・復号化（APP API）

## インストール手順

> ⚠ まだPythonをインストールしていない場合は、先に [公式のPythonページからダウンロード](https://www.python.org/downloads/) してインストールをお願いします。
> **Python 3.12以上の使用を推奨します**

* 公式 pip ソースからインストール（推奨。アップデートもこのコマンドを使用します）

  ```shell
  pip install jmcomic -U
  ```
* ソースコードからインストール

  ```shell
  pip install git+https://github.com/hect0x7/JMComic-Crawler-Python
  ```

## クイックスタート

### 1. アルバムのダウンロード方法

以下の簡単なコードを使用するだけで、アルバム `JM123` のすべてのチャプター画像をダウンロードできます。

```python
import jmcomic  # モジュールのインポート（事前にインストール必須）
jmcomic.download_album('123')  # ダウンロードしたいアルバムのIDを渡し、アルバム全体をローカルにダウンロード
```

上記の `download_album` メソッドには `option` パラメータが用意されており、JMのドメイン名、ネットワークプロキシ、画像のフォーマット変換、プラグインなどのダウンロード設定を管理できます。

これらの設定項目が必要な場合は、設定ファイルから `option` オブジェクトを作成し、それを使用してアルバムをダウンロードすることをお勧めします。次の章をご参照ください。

### 2. Option 設定を利用してアルバムをダウンロード

1. まず、設定ファイルを作成します。ファイル名を `option.yml` と仮定します。

   このファイルには固有の記述形式があります。こちらのドキュメントを参照してください → [設定ファイルガイド](../docs/sources/option_file_syntax.md)

   以下は簡単なデモです。ダウンロードした画像を png 形式に変換したい場合、`option.yml` に以下のように書き込みます。

```yml
download:
  image:
    suffix: .png # ダウンロードした画像をpng形式に変換する設定
```

2. 続いて、以下の Python コードを実行します。

```python
import jmcomic

# 設定オブジェクトの作成
option = jmcomic.create_option_by_file('あなたの設定ファイルのパス、例: D:/option.yml')
# option オブジェクトを使用してアルバムをダウンロード
jmcomic.download_album(123, option)
# 等価の記述: option.download_album(123)
```

### 3. コマンドラインの使用
> 単にアルバムをダウンロードするだけなら、コマンドラインを使用する方が前述の方法よりもシンプルかつ直接的です。
> 
> 例えば、Windowsでは `win+r` キーを押して `jmcomic xxx` と入力するだけでダウンロードできます。

例：

アルバム123をダウンロードするコマンド

```sh
jmcomic 123
```
アルバム123のチャプター456をダウンロードするコマンド
```sh
jmcomic 123 p456
```

コマンドラインモードも独自の Option 設定をサポートしています。環境変数またはコマンドライン引数を利用できます。

a. コマンドライン引数 `--option` 経由で設定ファイルのパスを指定

```sh
jmcomic 123 --option="D:/a.yml"
```

b. 環境変数 `JM_OPTION_PATH` にオプションファイルのパスを設定（推奨）

> 環境変数の設定方法は Google 等で検索してください。または powershell コマンドを使用: `setx JM_OPTION_PATH "D:/a.yml"` (再起動後に反映されます)

```sh
jmcomic 123
```



## 高度な利用方法

ドキュメントのトップページをご覧ください → [jmcomic.readthedocs.io](https://jmcomic.readthedocs.io/zh-cn/latest)

（ヒント: jmcomicは多数のダウンロード設定項目を提供しています。大部分のダウンロード要件については、関連する項目やプラグインを探すことで実現できる可能性が高いです。）

## プロジェクトの特色

- **Cloudflareのボット対策のバイパス機能**
- **JM APP インターフェースの最新暗号化アルゴリズムを実装 (1.6.3)**
- 様々な利用方法のサポート：

  - GitHub Actions: Web上でアルバムIDを直接入力してダウンロード（[チュートリアル：GitHub Actions経由でのダウンロード](../docs/sources/tutorial/1_github_actions.md)）
  - コマンドライン: Pythonのコード不要、簡単操作（[チュートリアル：コマンドラインからのダウンロード](../docs/sources/tutorial/2_command_line.md)）
  - Pythonコード: 最も本質的かつ強力な利用法（一定のPythonプログラミング知識が必要です）
- **Web版**と**モバイル版**の2つのクライアントをサポートし、設定から簡単に切り替え可能（**モバイル版はIP制限がなく圧倒的な互換性を持ち、Web版はエリア制限があるものの高効率**）
- **自動再試行およびドメイン切り替えメカニズム**のサポート
- **マルチスレッドダウンロード**（各画像ごとにスレッドの細分化が可能。驚異的な効率）
- **強力な設定オプション**

  - カスタマイズ無しでもシームレスに動作。
  - 設定ファイルからのOption生成・さまざまなフォーマットに対応。
  - 設定可能な要素一覧：`リクエストドメイン` `クライアントの実装` `ディスクキャッシュの利用状況` `同時にダウンロードするチャプター/画像の数` `画像フォーマット変換` `ダウンロードパスの規則構成` `メタ情報（headers, cookies, proxies）` `簡体字/繁体字（中国語）の変換` など。
- **強力な拡張性**

  - アルバム/チャプター/画像ダウンロード前後のコールバック関数のカスタムをサポート
  - 各種クラスのカスタマイズ対応: `Downloader（スケジューリング担当）` `Option（設定担当）` `Client（リクエスト担当）` `エンティティクラス` など
  - カスタムログ出力・例外リスナーの実装
  - **プラグイン(Plugin)システムにより、機能を容易に拡張したり、他者の製作物を利用可能**。組み込みプラグインの一例：
    - `ログインプラグイン`
    - `ハードウェアリソース監視プラグイン`
    - `最新チャプターのみダウンロードするプラグイン`
    - `ファイル圧縮（Zip）プラグイン`
    - `クライアントプロキシプラグイン`
    - `特定拡張子の画像ダウンロードプラグイン`
    - `QQメール送信プラグイン`
    - `ログトピックフィルタプラグイン`
    - `ブラウザのクッキーを自動で抽出するプラグイン`
    - `お気に入りをCSV形式でエクスポートするプラグイン`
    - `すべての画像を1つのPDFファイルに結合するプラグイン`
    - `すべての画像を縦長の1つのPNGファイルに結合するプラグイン`
    - `Webブラウザからローカルのチャプターを閲覧するプラグイン`
    - `アルバム更新購読プラグイン`
    - `画像数の少ないチャプターをスキップするプラグイン`
    - `重複ファイルの検出・削除プラグイン`
    - `パス文字列置換プラグイン`
    - `高度な再試行プラグイン`
    - `表紙ダウンロードプラグイン`

## ご利用上の注意点

* **Python 3.12以上**を推奨します。現在の最小互換バージョンは3.9です。
  > 注意: Python 3.9 およびそれ以前のバージョンは2025年に完全にサポート終了 (EOL) となっており、3.9以下のバージョンを使用すると、サードパーティ製ライブラリの非互換性の問題がいつでも発生する可能性があります。

* 個人のプロジェクトであるため、ドキュメントやサンプルコードの更新が遅れることがあります。ご不明な点はIssueにてご質問ください。

## ディレクトリ構造のご紹介

* `.github`: GitHub Actions 用の設定ファイル
* `assets`: コードやスクリプト以外のリソースファイル・画像類
  * `docs`: ドキュメントテキスト
  * `option`: オプションファイルのサンプル・テンプレート
* `src`: ソースコード本体
  * `jmcomic`: `jmcomic` パッケージ
* `tests`: テスト環境（`unittest`を利用した構成）
* `usage`: 使い方・使用例を実装したスクリプト類

## 特別な感謝

### 画像分割と連結アルゴリズム + JMモバイル版APIの実装と参照

<a href="https://github.com/tonquer/JMComic-qt">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt&theme=radical" />
    <source media="(prefers-color-scheme: light)" srcset="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
    <img alt="Repo Card" src="https://github-readme-stats.vercel.app/api/pin/?username=tonquer&repo=JMComic-qt" />
  </picture>
</a>
