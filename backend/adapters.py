import os
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_aws import ChatBedrock, BedrockEmbeddings
# Pinecone 和 OpenSearch 将在这里根据配置进行导入

def get_llm():
    """
    LLM 大模型适配器：通过 LLM_PROVIDER 环境变量一键切换
    """
    provider = os.getenv("LLM_PROVIDER", "modelscope")
    print(f"[Adapter Info] LLM 正在使用: {provider} 轨道")
    
    if provider == "modelscope":
        # 【修复超时死区】之前的 122B 参数量过于庞大，稍微生成多一点字就会突破 API Gateway 29秒的物理斩杀线导致前端报 500！
        # 由于 API Gateway 的 29s timeout 是物理不可篡改的，这里必须降级为超高扇出的 7B 轻量级纯指令调优模型保证每次返回毫秒级！
        return ChatOpenAI(
            api_key=os.getenv("MODELSCOPE_API_KEY", "your-modelscope-key"),
            base_url="https://api-inference.modelscope.cn/v1/",
            model="Qwen/Qwen3-VL-8B-Instruct"
        )
    elif provider == "bedrock":
        # 如果使用纯粹 AWS 轨道，利用 IAM 角色默认的环境变量 (如在 Lambda 内) 获取凭证
        return ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0", # 个人练习可使用更便宜的 Nova 微型模型
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
    else:
        raise ValueError(f"未知的 LLM 提供商: {provider}")

def get_embeddings():
    """
    向量化模型适配器：通过 EMBED_PROVIDER 环境变量切换
    """
    provider = os.getenv("EMBED_PROVIDER", "modelscope")
    print(f"[Adapter Info] Embeddings 正在使用: {provider} 轨道")
    
    if provider == "modelscope":
        return OpenAIEmbeddings(
            api_key=os.getenv("MODELSCOPE_API_KEY", "your-modelscope-key"),
            base_url="https://api-inference.modelscope.cn/v1/",
            model="Qwen/Qwen3-Embedding-0.6B" # 由用户建议的专职 1024维 对比学习召回模型
        )
    elif provider == "bedrock":
        return BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v1",
            region_name=os.getenv("AWS_REGION", "us-east-1")
        )
    else:
        raise ValueError(f"未知的 Embedding 提供商: {provider}")

def get_vector_store():
    """
    向量数据库适配器抽象。
    返回一个可用于检索的 Retriever / VectorStore。
    """
    provider = os.getenv("VECTOR_DB_PROVIDER", "pinecone")
    print(f"[Adapter Info] VectorDB 正在使用: {provider} 轨道")
    
    if provider == "pinecone":
        from langchain_pinecone import PineconeVectorStore
        
        pc_key = os.getenv("PINECONE_API_KEY")
        if not pc_key:
            raise ValueError("请在 .env 中配置 PINECONE_API_KEY 以便对接 Pinecone 向量库")
            
        index_name = os.getenv("PINECONE_INDEX", "notebooklm-clone")
        # 使用最新官方 langchain_pinecone 库进行检索与存储
        return PineconeVectorStore.from_existing_index(index_name=index_name, embedding=get_embeddings())
    elif provider == "opensearch":
        # 返回 AWS 原生的 OpenSearch Serverless Vector Store
        from langchain_community.vectorstores import OpenSearchVectorSearch
        # return OpenSearchVectorSearch(opensearch_url="...", embedding_function=get_embeddings())
        return "OpenSearchStore(Placeholder)"
    else:
         raise ValueError(f"未知的 VectorDB 提供商: {provider}")

def get_retriever():
    """
    RAG 检索器核心逻辑：支持代码手动挡（Manual）与 AWS 全托管（Bedrock KB）两种模式切换
    """
    mode = os.getenv("RETRIEVER_MODE", "MANUAL")
    print(f"[Retriever Info] 当前检索模式: {mode}")

    if mode == "BEDROCK_KB":
        from langchain_aws import AmazonKnowledgeBasesRetriever
        kb_id = os.getenv("KNOWLEDGE_BASE_ID")
        if not kb_id:
            raise ValueError("使用 BEDROCK_KB 模式必须提供 KNOWLEDGE_BASE_ID 环境变量")
        
        return AmazonKnowledgeBasesRetriever(
            knowledge_base_id=kb_id,
            retrieval_config={
                "vectorSearchConfiguration": {
                    "numberOfResults": 12 # 保持与手动模式一致的召回孔径
                }
            }
        )
    else:
        # 默认使用手动接入模式 (Manual Mode: Local Splitter + ModelScope Embeddings + Raw Pinecone)
        vector_store = get_vector_store()
        return vector_store.as_retriever(search_kwargs={"k": 12})

