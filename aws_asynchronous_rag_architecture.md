# 🏗️ AWS NotebookLM 异步 RAG 架构深度解析

本文档详细介绍了本项目为了解决 API Gateway 29 秒超时限制而采用的**异步上传与解析 (Asynchronous Ingestion)** 架构。需要注意的是，**对话问答 (QA) 仍保持同步模式**以提供即时反馈。

## 1. 核心架构拓扑图

目前系统采用 **事件驱动 (Event-Driven)** 的 Serverless 模式：

```mermaid
graph TD
    subgraph 核心引擎
        Pinecone[("Pinecone 向量搜索")]
        ModelScope["ModelScope / Bedrock (模型端)"]
        RagEngine["RAG 核心逻辑 (Shared)"]
    end

    %% 1. 异步上传流水线 (Async Ingestion - 同步部分)
    Client -- "1. 上传文件 (POST /upload)" --> APIGW
    APIGW -- "2. 转发请求" --> Lambda_API
    Lambda_API -- "3. 记录任务 (DynamoDB)" --> DB_Tasks
    Lambda_API -- "4. 存档原始文件 (S3)" --> S3
    Lambda_API -- "5. 立即返回成功 & task_id" --> Client
    
    %% 异步处理部分 (Async Ingestion - 后台爆发)
    S3 -- "6. 触发 ObjectCreated 事件" --> S3_Event
    S3_Event -- "7. 激活后台 Worker" --> Lambda_Worker
    
    Lambda_Worker -- "8. 核心 RAG 向量化解析" --> RagEngine
    RagEngine -- "9. 写入向量索引" --> Pinecone
    Lambda_Worker -- "10. 将状态改写为 COMPLETED" --> DB_Tasks

    Client -. "11. 定期轮询状态 (Polling)" .-> APIGW

    %% 2. 同步对话流水线 (Sync QA)
    Client -- "A. 同步提问 (POST /chat)" --> APIGW
    APIGW -- "B. 实时请求转发" --> Lambda_API
    Lambda_API -- "C. 检索召回 & 背景生成" --> RagEngine
    RagEngine -- "D. AI 回答内容" --> Lambda_API
    Lambda_API -- "E. 即时回复响应" --> Client
```

## 2. 详细时序图 (Sequence Diagram)

展示了从用户点击上传到看到结果的完整生命周期：

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户 (React UI)
    participant A as API Lambda
    participant S as Amazon S3
    participant D as DynamoDB (Tasks)
    participant W as Worker Lambda
    participant R as RAG Engine

    Note over U, R: --- 场景 A：异步文档建库 (Async Ingestion) ---
    U->>A: POST /api/upload (Multipart File)
    A->>D: 挂号: {task_id, status: 'PENDING'}
    A->>S: 上传文件
    A-->>U: 立即返回 {task_id} (秒回)
    
    S->>W: 触发 S3:ObjectCreated 事件
    W->>D: 更新状态: status: 'PROCESSING'
    W->>R: 执行解析 & 写入向量库
    W->>D: 更新状态: status: 'COMPLETED'
    
    loop 前端轮询
        U->>A: GET /api/tasks/{task_id}
        A->>D: 查询进度
        A-->>U: 返回当前进度
    end

    Note over U, R: --- 场景 B：同步对话问答 (Sync Q&A) ---
    U->>A: POST /api/chat (用户提问)
    A->>R: 调用同步 RAG 检索链
    R->>R: 向量库搜寻 -> 模型回复
    R-->>A: 返回生成的答案内容
    A-->>U: 返回 {reply: "..."} (约 5-15s)
```

## 3. 为什么 QA 仍然是同步的？

虽然文档上传采用了异步架构，但目前的 **`POST /api/chat` (问答接口) 依然采用同步模式**。原因如下：

1.  **用户体验 (Latency)**：RAG 问答通常在 5-15 秒内完成，用户期望即时看到打字机效果或回答内容。
2.  **复杂性权衡**：如果问答也转为异步，前端需要为每一个问题维护一个轮询状态，显著增加开发成本。
3.  **超时控制**：目前的 Bedrock/ModelScope 推理速度在 API Gateway 的 29 秒限制内能够稳定完成。

> [!TIP]
> 如果未来需要支持超长文档总结（耗时 > 30s），可以考虑将问答也迁移至类似的异步轮询模式。

## 4. 架构优势总结

1.  **彻底告别 29s 超时**：API 入口只负责“接活”，重活不占着网关连接。Worker Lambda 有最长 15 分钟的执行权。
2.  **极高容错性**：即使后台处理崩溃，任务状态也会记录在 DynamoDB 中，方便排查死因（CloudWatch Logs）。
3.  **零成本待机**：不上传文件时，没有任何计算资源在运行，完美符合 Serverless 精神。
4.  **扩容简单**：如果将来需要 LINE 回调，只需在 Worker 结尾加一行 LINE Push 调用，完全不需要改动 API 逻辑。

## 4. 核心术语表
*   **Polling (轮询)**：前端主动询问后端“好了没？”。
*   **Producer/Consumer (生产者/消费者)**：API 是生产者，Worker 是消费者。
*   **Idempotency (幂等性)**：使用 `task_id` 确保同一个文件上传不会产生重复的无效任务。
