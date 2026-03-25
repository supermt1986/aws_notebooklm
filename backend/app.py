try:
    import unzip_requirements
except ImportError:
    pass

import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel
from dotenv import load_dotenv

from adapters import get_llm, get_embeddings, get_vector_store

# 【核心修复】强制指定所有涉及到 Token 计算的底层 C 库在 AWS Lambda 无头环境下的缓存目录至 /tmp，
# 防止默认去挂载只读或不存在的 /home 目录引发 [Errno 2] No such file or directory 的隐形血案
os.environ["TIKTOKEN_CACHE_DIR"] = "/tmp/tiktoken_cache"
os.environ["XDG_CACHE_HOME"] = "/tmp/xdg_cache"

load_dotenv()

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
        print(f"[删除失败异常] {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    多模态文档上传接口：支持 PDF、图片和纯文本格式。
    """
    content_type = file.content_type
    is_image = content_type and content_type.startswith("image/")
    doc_type = "图像资源" if is_image else "文档资源"
    
    s3_bucket = os.getenv("AWS_S3_BUCKET_NAME")
    try:
        content = await file.read()
        if s3_bucket:
            import boto3
            import uuid
            import io
            s3_client = boto3.client('s3', region_name=os.getenv("AWS_REGION", "us-east-1"))
            file_key = f"uploads/{uuid.uuid4().hex[:8]}_{file.filename}"
            s3_client.upload_fileobj(io.BytesIO(content), s3_bucket, file_key)
            upload_msg = f"成功持久化至真实的 AWS S3 ({s3_bucket})"
        else:
            upload_msg = "已暂存本地 (您尚未配置 AWS S3 Bucket)"
            
        # 将文件写入临时区，准备给后台解析引擎（或 Lambda Event）处理
        import asyncio
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as buffer:
            buffer.write(content)
            
        # 必须使用 await 同步等待向量化完成！
        await process_into_vectorstore(temp_path, file.filename)
        
        # 【Bedrock KB 自动化挂钩】若处于托管模式，上传 S3 后动态触发 Ingestion Job 实现“上传即同步”
        retriever_mode = os.getenv("RETRIEVER_MODE", "MANUAL")
        if retriever_mode == "BEDROCK_KB":
            kb_id = os.getenv("KNOWLEDGE_BASE_ID")
            ds_id = os.getenv("DATA_SOURCE_ID")
            if kb_id and ds_id:
                try:
                    # 注意：Ingestion Job 由 bedrock-agent 客户端管理
                    agent_client = boto3.client('bedrock-agent', region_name=os.getenv("AWS_REGION", "us-east-1"))
                    agent_client.start_ingestion_job(knowledgeBaseId=kb_id, dataSourceId=ds_id)
                    print(f"[RAG同步器] 已成功触发 AWS KB 同步任务 (DS_ID: {ds_id})")
                except Exception as e:
                    print(f"[RAG同步器错误] 触发 IngestionJob 失败: {str(e)}")
            else:
                print("[RAG同步器提示] 缺少 KB_ID 或 DS_ID，请在 GitHub 中配置以启用自动同步")

        
        return {
            "status": "success", 
            "filename": file.filename, 
            "content_type": content_type,
            "message": f"[{doc_type}] {upload_msg} 且成功入库 Pinecone"
        }
    except Exception as e:
        from fastapi import HTTPException
        print(f"[全局上传崩溃] {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档处理崩溃: {str(e)}")

async def process_into_vectorstore(file_path: str, filename: str):
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    print(f"[RAG引擎] 开始对文件进行分块处理: {filename}")
    try:
        if file_path.lower().endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path, autodetect_encoding=True)
            
        docs = loader.load()
        
        # 【核心修复】因为物理文件用了 UUID，Loader 会默认把 metadata["source"] 写成 /tmp/abc...pdf。
        # 我们必须在这把它强行还原回用户文件名的挂载路径，否则后续的 DELETE 按照 filename 进行过滤器清理时，将完全找不到这批幽灵切片！
        for doc in docs:
            doc.metadata["source"] = f"/tmp/{filename}"
            
        # 【RAG 精度回归】回退切片大小至 1000，确保语义向量更聚焦在具体条款。
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        
        # 【核心终局修复】彻底击碎 AWS Lambda 的多线程诅咒！
        # Langchain 的 Pinecone 适配器默认强制并发，而 Pinecone Client 在初始化 ThreadPool 时需要挂载 Linux 的 /dev/shm 内存区块。
        # AWS Lambda 的极简安全容器物理阉割了 /dev/shm，导致底层的 C 语言 SemLock(信号量锁)一创建就爆出无名 FileNotFoundError！
        # 解决方案：完全手写单线程、全同步的 HTTP Upsert 发送器，物理越过多线程池！
        provider = os.getenv("VECTOR_DB_PROVIDER", "pinecone")
        if provider == "pinecone":
            from pinecone import Pinecone
            import uuid
            pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
            index = pc.Index(os.getenv("PINECONE_INDEX", "notebooklm-clone"))
            embeddings = get_embeddings()
            
            batch_size = 32
            for i in range(0, len(splits), batch_size):
                batch = splits[i:i+batch_size]
                texts = [doc.page_content for doc in batch]
                metas = [doc.metadata.copy() for doc in batch]
                for m, t in zip(metas, texts):
                    m["text"] = t
                ids = [str(uuid.uuid4()) for _ in batch]
                vecs = embeddings.embed_documents(texts)
                index.upsert(vectors=list(zip(ids, vecs, metas)))
        else:
            vector_store = get_vector_store()
            vector_store.add_documents(splits)
            
        print(f"[RAG引擎] {filename} 处理完毕！纯同步模式已安全注入了 {len(splits)} 个语义切片到 Vector 边界。")
    except Exception as e:
        import traceback
        traceback.print_exc()  # 打印完整堆栈到 CloudWatch 供核查死因
        print(f"[RAG引擎错误] 处理 {filename} 时崩溃: {e}")
        raise ValueError(f"向量神经元切片抛出异常: {str(e)}")

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
