# Amazon Bedrock Knowledge Base (KB) 全程配置与避坑指南

本指南旨在帮助您在 AWS 控制台上手动打通 **托管型 RAG (Managed RAG)** 链路。通过 KB，我们可以利用 AWS 原生的 PDF 解析、Titan 向量化以及自动索引功能，实现生产级的知识库管理。

> [!IMPORTANT]
> **计费警告**：Bedrock KB 的“管理费”约为 **$0.19 / 小时**。为了省钱，建议在完成练习或测试后立刻 **Delete** 掉 KB 实体。删除 KB 不会删除 S3 文件和 Pinecone 数据。

---

## 1. 密钥准备：AWS Secrets Manager
Bedrock 需要通过此服务安全地提取您的 Pinecone 钥匙。
1. 进入 [Secrets Manager](https://console.aws.amazon.com/secretsmanager/)。
2. **Store a new secret** -> **Other type of secret**。
3. Key/value mapping:
   * Key: `apiKey` (必须叫这个名字)
   * Value: `你的-Pinecone-API-Key`
4. Secret name: `pinecone-api-key-for-kb`。
5. **记录 ARN**: 完成后复制生成的 ARN（格式如 `arn:aws:secretsmanager:...`）。

---

## 2. 核心配置：创建 Knowledge Base
进入 [Amazon Bedrock](https://console.aws.amazon.com/bedrock/) -> **Knowledge bases** -> **Create knowledge base**。

### Step 1: 基础选型
* **Name**: `notebooklm-kb`。
* **Storage**: 确保选中 **"Contains a vector database"**。

### Step 2: 数据源 (S3)
* **Source**: 选择 **Amazon S3**。
* **S3 URI**: 指向您的上传目录，例如 `s3://your-bucket-name/uploads/`。

### Step 3: 解析与分块 (关键选择)
* **Parsing Strategy (解析策略)**:
  * **デフォルト (Default)**: 最便宜，适合普通文本 PDF。
  * **基礎モデル (Foundation Model)**: 如果您的文档里有复杂表格（如年休假表），请选这个。它会用 Claude 解析表格，但会产生额外的模型调用费用。
* **Chunking Strategy (分块策略)**:
  * 建议选择 **Fixed-size chunking (固定大小)**。
  * **Max tokens**: `1000`。
  * **Overlap percentage**: `20%` (或 200 tokens)。

### Step 4: 向量化模型
* 选择 **Titan Text Embeddings v2**。

### Step 5: 向量数据库 (Pinecone)
* **Database**: 选择 **Pinecone**。
* **Connection String**: 填入 Pinecone 的 Index Host URL (e.g., `https://index-name-...pc.io`)。
* **Credentials ARN**: 填入第 1 步保存的 Secret ARN。
* **Field Mapping (细节避坑)**:
  * **Vector field**: 如果没看到就跳过（Pinecone 默认使用 `values`）。
  * **Text field**: 填写 **`text`** (对应后端代码读取的标签)。
  * **Metadata field**: 填写 **`metadata`** (存储文件名、页码等)。

---

## 3. 同步与 ID 获取
1. **Sync (同步)**: 创建完后，进入 KB 详情页，点击 Data source 区域的 **Sync**。
2. **记录关键 ID**:
   * **Knowledge Base ID**: 页面顶部的长字符串。
   * **Data Source ID**: 在 Data source 列表里点击您的 S3 源，进入后复制它的 ID。

---

## 4. 后端自动化配置
为了实现“上传即同步”和“一键换芯”，请在 **GitHub Repository Settings -> Secrets and variables -> Actions** 中配置以下环境变量：

| 变量名 | 说明 | 示例值 |
| :--- | :--- | :--- |
| `RETRIEVER_MODE` | 检索模式开关 | `BEDROCK_KB` (自动) 或 `MANUAL` (手动) |
| `KNOWLEDGE_BASE_ID` | KB 唯一标识 | `ABCDEFGHIJ` |
| `DATA_SOURCE_ID` | S3 数据源标识 | `KLMNOPQRST` |

---

## 5. 验证方式
* **查看 Lambda 日志**: 如果看到 `[Retriever Info] 当前检索模式: BEDROCK_KB`，说明已接通。
* **自动同步检测**: 上传文件后，如果日志显示 `[RAG同步器] 已成功触发 AWS KB 同步任务`，则说明自动化 Ingestion 已生效。

**再次提醒：不用时请务必删除 KB 实体以停止扣费！**💸
