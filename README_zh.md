# AWS NotebookLM Clone (云原生知识库引擎)

*[🇯🇵 日本語版 (Japanese Version) はこちら](./README.md)*

本项目是一个基于 AWS Serverless 生态与开源大模型打造的轻量级、低成本个人知识库问答工具 (RAG System)。支持多模态文档上传、基于高维向量的相似度检索，并结合千亿参数大模型进行严谨的对话推理。

> 📖 **如需查阅最高深度的包含红蓝线双轨流转机制的图表系统、完整的基建及 CI/CD 发版配置指南，以及排坑实录，请狠狠点击翻阅：[💻 核心部署计划架构说明书 (Implementation Plan)](./implementation_plan.md)**

## 🌟 核心特性
- **纯血无状态云架构**：采用 AWS HTTP API Gateway + Lambda + S3 组合，按次触发计费，彻底消除闲置成本。
- **⚡️ 异步 RAG 流水线 (Async Polling)**：彻底突破 API Gateway 29s 限制，内部采用 S3 事件驱动与 DynamoDB 任务追踪机制。
- **🧠 双检索模式 (Dual-Mode RAG)**：一键切换“省钱自研版 (Lambda+ModelScope)”与“托管工程版 (AWS Bedrock KB)”，平衡开发成本与生产性能。
- **🚀 自动化索引 (Auto-Ingestion)**：上传 S3 后动态触发 Bedrock 知识库同步，告别控制台手动点击。
- **💸 成本优化策略**：针对 API Gateway 29s 限制与托管服务计费特性深度优化。
- **毛玻璃 UI 设计**：提供了直观响应式的 React 前端，集成自动滚动的极速对话交互流（且附带中英日热更新多语言支持）。
- **超强的成本控制**：在开发测试阶段依托跨国云厂白嫖额度，真实物理运行费用被完美压制在 $0/月。

## 📁 目录结构概要
- `frontend/`: AWS Amplify 完全黑盒接管的 React 前端项目核心源码。
- `backend/`: 部署至 AWS Lambda 的轻量级 FastAPI Python 后端引擎雷达中枢。
- `.github/workflows/`: 完全自动化、隔离密钥的端到端 GitHub Actions Serverless CI/CD 物理发布跑道。

## ⚙️ 部署先决条件
请在您的 GitHub 全局环境密钥库中按顺序注入以下系统级环境变量 Secret：
- `AWS_ACCESS_KEY_ID` & `AWS_SECRET_ACCESS_KEY` & `AWS_REGION` (核心打底物理通行证)
- `MODELSCOPE_API_KEY` (大模型引擎调用密钥)
- `PINECONE_API_KEY` & `PINECONE_INDEX` (需手动去 Pinecone 面板创建 Dimension 限定为 4096 维的高纬度向量仓)

## 🛠️ 本地开发环境调试
```bash
# 启动前端页面
cd frontend && npm install && npm run dev

# 启动后端 API 服务
cd backend && pip install -r requirements.txt && python app.py
```
