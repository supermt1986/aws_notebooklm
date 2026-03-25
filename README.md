# AWS NotebookLM Clone (クラウドネイティブ ナレッジベース エンジン)

*[🇨🇳 中文版 (Chinese Version) はこちら](./README_zh.md)*

本プロジェクトは、AWS Serverless エコシステムとオープンソースの LLM を活用した、軽量かつ低コストの個人用ナレッジベース Q&A ツール (RAG システム) です。マルチモーダルなドキュメントのアップロードに対応し、高次元ベクトルに基づく類似度検索および 1,000億パラメータクラスの LLM による厳密な対話推論を提供します。

> 📖 **詳細なシステム構成図や「完全自動 CI/CD デプロイ」の仕組み、並びに解決済み課題の記録については、[💻 核心実装計画と作業実績報告 (Implementation Plan)](./implementation_plan_ja.md) をご参照ください。**

## 🌟 主な特徴
- **ピュアステートレスなクラウドアーキテクチャ**: AWS HTTP API Gateway + Lambda + S3 の組み合わせにより、従量課金モデルを実現し、アイドル時のコストを完全に排除。
- **🧠 デュアル検索モード (Dual-Mode RAG)**：「節約自作版 (Lambda+ModelScope)」と「フルマネージド版 (AWS Bedrock KB)」をワンクリックで切替可能。
- **⚡️ 自動インデックス (Auto-Ingestion)**：S3 アップロード後に Bedrock ナレッジベースの同期を自動トリガー。
- **💸 コスト最適化戦略**：API Gateway の 29s 制限とマネージドサービスの課金特性に合わせた高度な最適化。
- **グラスモーフィズム UI**: 直感的でレスポンシブな React フロントエンド。自動スクロール対応の RAG 対話UIを搭載（日中多言語自動切替サポート）。
- **圧倒的なコストパフォーマンス**: テスト段階では無料枠を最大限活用し、クラウドネイティブ環境での維持コストを $0/月 に抑制。

## 📁 ディレクトリ構造
- `frontend/`: AWS Amplify でホストされる React フロントエンドのソースコード。
- `backend/`: AWS Lambda にデプロイされる FastAPI ベースの Python バックエンドアプリケーション。
- `.github/workflows/`: シークレットを安全に管理し、完全に自動化された GitHub Actions バックエンド CI/CD パイプライン。

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
