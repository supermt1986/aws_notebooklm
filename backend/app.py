try:
    import unzip_requirements
except ImportError:
    pass

# AWS NotebookLM Backend API - Triggering fresh deploy for SQS upgrade
import os
import uuid
import time
import json
import boto3
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel
from dotenv import load_dotenv

from adapters import get_llm, get_embeddings, get_vector_store
from rag_engine import process_into_vectorstore

# 【核心修复】强制指定所有涉及到 Token 计算的底层 C 库在 AWS Lambda 无头环境下的缓存目录至 /tmp，
# 防止默认去挂载只读或不存在的 /home 目录引发 [Errno 2] No such file or directory 的隐形血案
os.environ["TIKTOKEN_CACHE_DIR"] = "/tmp/tiktoken_cache"
os.environ["XDG_CACHE_HOME"] = "/tmp/xdg_cache"

load_dotenv()

# 初始化 AWS 客户端资源
dynamodb = boto3.resource("dynamodb")

app = FastAPI(title="AWS NotebookLM API")

# 解决本地开发跨域问题 (也可以配置到 Amplify API Gateway)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str

@app.get("/api/health")
def health_check():
    """用于 API Gateway / 负载均衡器的健康检查"""
    return {"status": "ok", "message": "NotebookLM backend is running."}

@app.get("/api/documents")
async def get_documents():
    s3_bucket = os.getenv("AWS_S3_BUCKET_NAME")
    if not s3_bucket:
        return {"documents": []}
        
    try:
        import boto3
        s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
        response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix="uploads/")
        
        documents = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # 去除 uploads/ 前缀和 UUID
                full_name = obj['Key'].replace("uploads/", "")
                parts = full_name.split("_", 1)
                display_name = parts[1] if len(parts) > 1 else full_name
                if display_name not in documents:
                    documents.append(display_name)
                    
        return {"documents": documents}
    except Exception as e:
        print(f"Failed to list documents from S3: {e}")
        return {"documents": []}

@app.delete("/api/documents/{filename}")
async def delete_document(filename: str):
    """
    知识库销毁接口: 深跨越 S3 和 Pinecone 同步粉碎物理文件与逻辑向量碎片
    """
    s3_bucket = os.getenv("AWS_S3_BUCKET_NAME")
    try:
        # 1. 扫描并摧毁 AWS S3 持久层存档
        if s3_bucket:
            import boto3
            s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
            response = s3_client.list_objects_v2(Bucket=s3_bucket, Prefix="uploads/")
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith(f"_{filename}") or obj['Key'] == f"uploads/{filename}":
                        s3_client.delete_object(Bucket=s3_bucket, Key=obj['Key'])
                        print(f"[S3粉碎] 已彻底删除原文件: {obj['Key']}")

        # 2. 调用 Pinecone DB metadata 过滤器销毁源切片神经元
        vector_store = get_vector_store()
        if hasattr(vector_store, "delete"):
            vector_store.delete(filter={"source": f"/tmp/{filename}"})
            print(f"[Pinecone粉碎] 已抹除文档关联神经元集 (Source: /tmp/{filename})")

        return {"status": "success", "message": f"全链路粉碎完毕: {filename}"}
    except Exception as e:
        # Removed redundant from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

class IngestUrlRequest(BaseModel):
    url: str

@app.post("/api/ingest-url")
async def ingest_url(req: IngestUrlRequest):
    """
    URL 抓取入口：接收 URL 并将其存入 SQS 队列进行异步解析
    """
    task_id = str(uuid.uuid4())
    
    try:
        # 1. 在 DynamoDB 中注册“爬虫”任务
        table = dynamodb.Table(os.getenv("TASKS_TABLE"))
        table.put_item(
            Item={
                "task_id": task_id,
                "status": "PENDING",
                "filename": req.url,
                "type": "URL",
                "createdAt": int(time.time()),
                "updatedAt": int(time.time())
            }
        )
        
        # 2. 推送至 SQS 队列
        sqs = boto3.client("sqs")
        queue_url = os.getenv("TASKS_QUEUE_URL")
        
        message_body = {
            "task_id": task_id,
            "bucket": "N/A", # URL 任务不需要 bucket
            "key": req.url,   # 将 URL 作为 key 传递给 worker
            "filename": req.url
        }
        
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body)
        )
        
        return {"task_id": task_id, "message": "URL 任务已提交"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}")
async def get_task_status(task_id: str):
    """
    任务对账接口：前端轮询此接口获取异步处理进度
    """
    table_name = os.getenv("TASKS_TABLE")
    if not table_name:
        return {"status": "ERROR", "message": "未配置任务追踪表"}

    try:
        import boto3
        db = boto3.resource('dynamodb', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
        table = db.Table(table_name)
        response = table.get_item(Key={'task_id': task_id})
        
        if 'Item' not in response:
            return {"status": "NOT_FOUND", "message": "任务不存在"}
            
        return response['Item']
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    异步上传接口：文件存入 S3 后立即返回 task_id，后续处理交由后台 Worker
    """
    import boto3
    import uuid
    import io
    import time
    
    task_id = str(uuid.uuid4())
    s3_bucket = os.getenv("AWS_S3_BUCKET_NAME")
    table_name = os.getenv("TASKS_TABLE")
    
    if not s3_bucket:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="未配置 S3 Bucket，无法进行异步处理")

    try:
        content = await file.read()
        
        # 1. 在 DynamoDB 挂号 (PENDING 状态)
        db = boto3.resource('dynamodb', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
        table = db.Table(table_name)
        table.put_item(Item={
            'task_id': task_id,
            'filename': file.filename,
            'status': 'PENDING',
            'createdAt': int(time.time()),
            'message': '文件已上传，排队等待解析中...'
        })

        # 2. 物理上传至 S3
        s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
        file_key = f"uploads/{task_id}_{file.filename}"
        s3_client.upload_fileobj(io.BytesIO(content), s3_bucket, file_key)
        
        # 3. 将任务推送至 SQS 队列 (异步削峰的关键)
        sqs_url = os.getenv("TASKS_QUEUE_URL")
        if sqs_url:
            import json
            sqs_client = boto3.client('sqs', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
            message_body = {
                "task_id": task_id,
                "bucket": s3_bucket,
                "key": file_key,
                "filename": file.filename
            }
            sqs_client.send_message(
                QueueUrl=sqs_url,
                MessageBody=json.dumps(message_body)
            )
            print(f"[API] 已向 SQS 发送任务消息: {task_id}")
        
        return {
            "status": "success", 
            "task_id": task_id,
            "message": "文件上传成功，RAG 解析任务已加入队列"
        }
    except Exception as e:
        print(f"[异步上传崩溃] {str(e)}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


# -------------------------------------------------------------------------

@app.post("/api/chat")
async def chat_interaction(req: ChatRequest):
    """
    RAG 对话核心接口：检索向量库 -> 构建知识上下文 -> 询问底座大模型
    """
    from adapters import get_llm, get_retriever
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_core.output_parsers import StrOutputParser
    
    # 动态获取当前选定的模型和检索器（支持代码手动挡与 KB 托管挡切换）
    llm = get_llm()
    # 【检索调优】底层根据 RETRIEVER_MODE 变量自动路由，并统一召回 Top-12 深度背景
    retriever = get_retriever()
    
    template = """You are a professional AWS NotebookLM AI Assistant.
    Please answer the query based ONLY on the provided Context. 
    If the answer is not in the context, strictly state that the information is not recorded (in the same language as the user's question).
    
    <Context>
    {context}
    </Context>
    
    【CRITICAL RULE】
    - ALWAYS reply in the SAME language as the user's question.
    - User asks in Japanese (日本語) -> You MUST reply in Japanese (日本語).
    - User asks in Chinese (中文) -> You MUST reply in Chinese (中文).
    - If the context is in Japanese but the user asks in Chinese, summarize the content in Chinese.
    
    Question: {question}
    
    Your Response:"""
    prompt = ChatPromptTemplate.from_template(template)
    
    def format_docs(docs):
        return "\n\n---\n\n".join(f"片段参考: {doc.page_content}" for doc in docs)
        
    from langchain_core.runnables import RunnableParallel
    rag_chain = (
        RunnableParallel({"context": retriever | format_docs, "question": RunnablePassthrough()})
        | prompt
        | llm
        | StrOutputParser()
    )
    
    try:
        response = rag_chain.invoke(req.message)
        return {"reply": response}
    except Exception as e:
        return {"reply": f"系统对话能力异常，底层组件报错: {str(e)}"}

# Mangum: 包装 FastAPI 应用，使其可以直接作为 AWS Lambda 函数运行，接管 API Gateway 的 HTTP Proxy 事件
handler = Mangum(app)
