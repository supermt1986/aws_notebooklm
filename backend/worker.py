import os
import boto3
import urllib.parse
from rag_engine import process_into_vectorstore, update_task_status

s3_client = boto3.client('s3')

def handler(event, context):
    """
    S3 Event Trigger Handler: 处理从 S3 上传的文件并执行异步 RAG 索引
    """
    print(f"[Worker] 收到 S3 事件: {event}")
    
    try:
        # 1. 解析 S3 事件获取存储桶和文件名
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = urllib.parse.unquote_plus(event['Records'][0]['s3']['object']['key'], encoding='utf-8')
        
        # 文件名格式预期为: uploads/{task_id}_{filename}
        filename_part = key.replace("uploads/", "")
        if "_" not in filename_part:
            print(f"[Worker] 文件名格式不符，跳过处理: {key}")
            return
            
        task_id, original_filename = filename_part.split("_", 1)
        print(f"[Worker] 开始处理任务: {task_id}, 文件: {original_filename}")
        
        # 2. 更新状态为 PROCESSING
        update_task_status(task_id, "PROCESSING", "正在后台执行切片与向量化...")
        
        # 3. 下载文件至 /tmp 目录
        temp_path = f"/tmp/{original_filename}"
        s3_client.download_file(bucket, key, temp_path)
        
        # 4. 执行核心 RAG 索引逻辑
        # 检查是否是 BEDROCK_KB 模式，如果是，则可能不需要执行本地嵌入
        retriever_mode = os.getenv("RETRIEVER_MODE", "MANUAL")
        
        if retriever_mode == "BEDROCK_KB":
            print("[Worker] 检测到 BEDROCK_KB 模式，跳过本地嵌入过程...")
            # 注意：Ingestion Job 已经在 app.py 中触发了，这里只需标记完成（或等待，但 S3 触发无法直接等待 Job）
            update_task_status(task_id, "COMPLETED", "已触发 AWS Bedrock 知识库自动同步。")
        else:
            print("[Worker] 执行 MANUAL 模式本地嵌入...")
            import asyncio
            # Lambda 3.11+ 环境建议直接使用 asyncio.run
            asyncio.run(process_into_vectorstore(temp_path, original_filename))
            update_task_status(task_id, "COMPLETED", "文档解析与向量入库圆满完成。")
            
        print(f"[Worker] 任务 {task_id} 处理成功。")
        
    except Exception as e:
        import traceback
        error_info = traceback.format_exc()
        print(f"[Worker] 关键错误: {e}\n{error_info}")
        # 如果能解析出 task_id，记录失败
        try:
            if 'task_id' in locals():
                update_task_status(task_id, "FAILED", f"处理失败: {str(e)}")
        except:
            pass
