# AWS NotebookLM Clone (クラウドネイティブ ナレッジベース エンジン)

本プロジェクトは、AWS Serverless エコシステムとオープンソースの LLM を活用した、軽量かつ低コストの個人用ナレッジベース Q&A ツール (RAG システム) です。マルチモーダルなドキュメントのアップロードに対応し、高次元ベクトルに基づく類似度検索および 1,000億パラメータクラスの LLM による厳密な対話推論を提供します。

## 🌟 主な特徴
- **ピュアステートレスなクラウドアーキテクチャ**: AWS HTTP API Gateway + Lambda + S3 の組み合わせにより、従量課金モデルを実現し、アイドル時のコストを完全に排除。
- **プラグアンドプレイのデュアルトラック抽象化**: `ModelScope オープンソース API` と `Amazon Bedrock ネイティブ API` 間を環境変数でシームレスに切り替え可能。
- **グラスモーフィズム UI**: 直感的でレスポンシブな React フロントエンド。自動スクロール対応の RAG 対話UIを搭載。
- **圧倒的なコストパフォーマンス**: テスト段階では無料枠を最大限活用し、クラウドネイティブ環境での維持コストを $0/月 に抑制。

## 📁 ディレクトリ構造
- `frontend/`: AWS Amplify でホストされる React フロントエンドのソースコード。
- `backend/`: AWS Lambda にデプロイされる FastAPI ベースの Python バックエンドアプリケーション。
- `.github/workflows/`: シークレットを安全に管理し、完全に自動化された GitHub Actions CI/CD パイプライン。

## ⚙️ デプロイの前提条件
GitHub リポジトリに以下の環境変数 Secrets を設定してから Actions 自動ビルドをトリガーしてください：
- `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY` & `AWS_REGION`
- `MODELSCOPE_API_KEY` (LLM および Embedding API 用)
- `PINECONE_API_KEY` & `PINECONE_INDEX` (事前に Pinecone で次元数 4096 のインデックスを作成する必要があります)

## 🛠️ ローカル開発
```bash
# フロントエンドの起動
cd frontend && npm install && npm run dev

# バックエンドの起動 (仮想環境内)
cd backend && pip install -r requirements.txt && python app.py
```
