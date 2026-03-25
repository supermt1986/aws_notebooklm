# 🏗️ AWS NotebookLM 异步 RAG 架构深度解析

本文档详细介绍了本项目为了解决 API Gateway 29 秒超时限制而采用的**异步轮询 (Asynchronous Polling)** 架构。该架构不仅提升了系统的稳定性，也为高负载的 RAG（检索增强生成）任务提供了无限的扩展空间。

## 1. 核心架构拓扑图

目前系统采用 **事件驱动 (Event-Driven)** 的 Serverless 模式：

```mermaid
graph TD
    subgraph 前端与网关
        Client["React 前端 (Amplify)"]
        APIGW["API Gateway (HTTP API)"]
    end

    subgraph 同步处理逻辑
        Lambda_API["API Lambda (FastAPI)"]
        S3[("Amazon S3 (文档桶)")]
        DB_Tasks[("DynamoDB (任务状态表)")]
    end

    subgraph 异步处理引擎
        S3_Event["S3 ObjectCreated 事件"]
        Lambda_Worker["Processor Lambda (后台工蜂)"]
        RagEngine["RAG 引擎 (Shared)"]
    end

    subgraph 核心组件
        Pinecone[("Pinecone 向量搜索")]
        ModelScope["ModelScope / Bedrock (模型端)"]
    end

    %% 连线关系
    Client -- "1. 上传文件 (POST /upload)" --> APIGW
    APIGW --> Lambda_API
    Lambda_API -- "2. 记录 PENDING 状态" --> DB_Tasks
    Lambda_API -- "3. 物理上传文件" --> S3
    
    S3 -- "4. 触发事件" --> S3_Event
    S3_Event --> Lambda_Worker
    
    Lambda_Worker -- "5. 状态变更为 PROCESSING" --> DB_Tasks
    Lambda_Worker --> RagEngine
    RagEngine -- "6. 执行切片 & 向量化" --> ModelScope
    RagEngine -- "7. 写入向量索引" --> Pinecone
    Lambda_Worker -- "8. 状态变更为 COMPLETED" --> DB_Tasks

    Client -. "9. 定时轮询 (GET /tasks/{id})" .-> APIGW
    APIGW -.-> Lambda_API
    Lambda_API -. "10. 返回实时进度" .-> DB_Tasks
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
    participant V as Vector DB (Pinecone)

    U->>A: POST /api/upload (Multipart File)
    Note over A: 生成 task_id (UUID)
    A->>D: 挂号: {task_id, status: 'PENDING'}
    A->>S: 上传文件至 uploads/{task_id}_{name}
    A-->>U: 立即返回 {task_id, status: 'success'}
    
    par 后台处理过程 (Async)
        S->>W: 触发 S3:ObjectCreated 事件
        W->>D: 更新状态: status: 'PROCESSING'
        W->>S: 下载原始文件到 /tmp
        W->>W: 执行 RAG 解析与向量化转换
        W->>V: 批量 Upsert 向量索引
        W->>D: 更新状态: status: 'COMPLETED'
    and 前端轮询过程 (Polling)
        loop 每 3 秒一次
            U->>A: GET /api/tasks/{task_id}
            A->>D: 查询任务详情
            D-->>A: 返回当前状态 (PENDING/PROCESSING/...)
            A-->>U: 渲染进度条或状态文本
            Note right of U: 若状态为 COMPLETED 则停止轮询并刷新
        end
    end
```

## 3. 架构优势总结

1.  **彻底告别 29s 超时**：API 入口只负责“接活”，重活不占着网关连接。Worker Lambda 有最长 15 分钟的执行权。
2.  **极高容错性**：即使后台处理崩溃，任务状态也会记录在 DynamoDB 中，方便排查死因（CloudWatch Logs）。
3.  **零成本待机**：不上传文件时，没有任何计算资源在运行，完美符合 Serverless 精神。
4.  **扩容简单**：如果将来需要 LINE 回调，只需在 Worker 结尾加一行 LINE Push 调用，完全不需要改动 API 逻辑。

## 4. 核心术语表
*   **Polling (轮询)**：前端主动询问后端“好了没？”。
*   **Producer/Consumer (生产者/消费者)**：API 是生产者，Worker 是消费者。
*   **Idempotency (幂等性)**：使用 `task_id` 确保同一个文件上传不会产生重复的无效任务。
