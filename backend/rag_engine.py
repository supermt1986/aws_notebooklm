import os
import boto3
from adapters import get_llm, get_embeddings, get_vector_store

# 【核心修复】强制指定所有涉及到 Token 计算的底层 C 库在 AWS Lambda 无头环境下的缓存目录至 /tmp
os.environ["TIKTOKEN_CACHE_DIR"] = "/tmp/tiktoken_cache"
os.environ["XDG_CACHE_HOME"] = "/tmp/xdg_cache"

async def process_into_vectorstore(file_path: str, filename: str):
    """
    向量化处理引擎核心逻辑 (抽取自 app.py)
    """
    from langchain_community.document_loaders import PyPDFLoader, TextLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    print(f"[RAG引擎] 开始对文件进行分块处理: {filename}")
    try:
        if file_path.lower().endswith(".pdf"):
            loader = PyPDFLoader(file_path)
        else:
            loader = TextLoader(file_path, autodetect_encoding=True)
            
        docs = loader.load()
        
        # 统一 metadata 标志位
        for doc in docs:
            doc.metadata["source"] = f"/tmp/{filename}"
            
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        splits = text_splitter.split_documents(docs)
        
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
            
        print(f"[RAG引擎] {filename} 处理完毕！")
        return len(splits)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[RAG引擎错误] 处理 {filename} 时崩溃: {e}")
        raise e

def update_task_status(task_id: str, status: str, error: str = None):
    """
    更新 DynamoDB 中任务的状态
    """
    table_name = os.getenv("TASKS_TABLE")
    if not table_name:
        print("[TaskDB] 警告：没有配置 TASKS_TABLE 环境变量")
        return
        
    try:
        db = boto3.resource('dynamodb', region_name=os.getenv("AWS_REGION", "ap-northeast-1"))
        table = db.Table(table_name)
        import time
        update_expr = "SET #s = :s, updatedAt = :u"
        expr_attr_names = {"#s": "status"}
        expr_attr_values = {":s": status, ":u": int(time.time())}
        
        if error:
            update_expr += ", error_msg = :e"
            expr_attr_values[":e"] = error
            
        table.update_item(
            Key={'task_id': task_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values
        )
        print(f"[TaskDB] 成功更新任务 {task_id} 为 {status}")
    except Exception as e:
        print(f"[TaskDB] 更新失败: {e}")
