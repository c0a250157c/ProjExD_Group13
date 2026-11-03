# GitHubへのアップロード

この教材は手元に作成したファイルです。この作業ではGitHubへの公開はしていません。

## おすすめの配置

ゲームのリポジトリ内の`docs/lec05/`に、teaching-kitの中身を置きます。
例えば`docs/lec05/README.md`、`docs/lec05/pdf/00_slides.pdf`となります。
サブフォルダを含む構造を維持すると、READMEのリンクがそのまま使えます。

## Gitを使う場合

1. 作業中の変更を確認し、教材用のブランチを作る。
2. `docs/lec05/`へ教材一式をコピーする。
3. `git status`で関係するファイルだけが追加されたか確認する。
4. 次のコマンドで自分のフォークへ送る。

```powershell
git switch -c docs/lec05-materials
git add docs/lec05
git commit -m "Add group development tutorials"
git push -u origin docs/lec05-materials
```

originが自分のフォークを指していることを`git remote -v`で先に確認してください。
代表者のリポジトリへはPRで提案し、代表者が内容を確認して取り込みます。
参考デモ側へ公開する場合も、同じフォルダ構造で置けます。

## ブラウザでアップロードする場合

ZIPを展開し、リポジトリのAdd file → Upload filesへteaching-kitフォルダをドラッグします。
フォルダ構造を保った状態で追加し、コミット前の一覧を確認してください。
公開後はteaching-kit/README.mdを開き、PDFと担当別リンクが開けるか確認します。
ZIPだけをアップすると中身をGitHub上で読みづらいので、展開したファイルを推奨します。

## リポジトリ直下のREADMEに追加する案

docs/lec05へ配置した場合：

```markdown
## 開発教材
[5人の担当別演習と説明スライド](docs/lec05/README.md)
```

teaching-kitのまま置いた場合はリンクを`teaching-kit/README.md`へ変更します。
