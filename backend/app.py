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

UPLOADED_DOCUMENTS = []

@app.get("/api/documents")
async def get_documents():
    return {"documents": UPLOADED_DOCUMENTS}

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
            
        # 添加进内存显示列表
        if file.filename not in UPLOADED_DOCUMENTS:
            UPLOADED_DOCUMENTS.append(file.filename)

        # 异步丢入后台去切块存入 Pinecone (Serverless 最佳实践一般是发消息到 SQS 队列触发另一个 Lambda 处理，这里为单机测试做简化)
        asyncio.create_task(process_into_vectorstore(temp_path, file.filename))
        
    except Exception as e:
        upload_msg = f"S3存储或解析分发失败: {str(e)}"
    
    return {
        "status": "success", 
        "filename": file.filename, 
        "content_type": content_type,
        "message": f"[{doc_type}] {upload_msg}"
    }

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
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        splits = text_splitter.split_documents(docs)
        
        vector_store = get_vector_store()
        vector_store.add_documents(splits)
        print(f"[RAG引擎] {filename} 处理完毕！生成了 {len(splits)} 个语义块，已安全写入 Vector DB。")
    except Exception as e:
        print(f"[RAG引擎错误] 处理 {filename} 时崩溃: {e}")

@app.post("/api/chat")
async def chat_interaction(req: ChatRequest):
    """
    RAG 对话核心接口：检索向量库 -> 构建知识上下文 -> 询问底座大模型
    """
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnablePassthrough
    from langchain_core.output_parsers import StrOutputParser
    
    # 动态获取当前选定的模型和向量库（双轨架构生效点）
    llm = get_llm()
    vector_store = get_vector_store()
    retriever = vector_store.as_retriever(search_kwargs={"k": 4})
    
    template = """你是一个专业的 AWS NotebookLM AI 帮手。请基于参考资料来回答问题。
    如果提供的参考资料中找不到确切答案，请严谨地回答“抱歉，在知识库资料中没有记录相关信息”，禁止自己发散编造内容。
    
    <参考资料>
    {context}
    </参考资料>
    
    问题：{question}
    
    您的回答："""
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
