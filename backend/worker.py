try:
    import unzip_requirements
except ImportError:
    pass

import json
import os
import boto3
import urllib.parse
import asyncio
from rag_engine import process_into_vectorstore, update_task_status

s3_client = boto3.client('s3')

def handler(event, context):
    """
    SQS Event Trigger Handler: 处理来自 SQS 队列的任务消息
    """
    print(f"[Worker] 收到 SQS 事件, 记录数: {len(event.get('Records', []))}")
    
    for record in event.get('Records', []):
        task_id = "UNKNOWN"
        try:
            # 1. 解析 SQS 消息体
            body = json.loads(record['body'])
            task_id = body.get('task_id')
            bucket = body.get('bucket')
            key = body.get('key')
            original_filename = body.get('filename')
            
            print(f"[Worker] 开始处理任务: {task_id}, 文件: {original_filename}")
            
            # 2. 更新状态为 PROCESSING
            update_task_status(task_id, "PROCESSING", "正在从队列提取并执行向量化...")
            
            # 3. 下载文件至 /tmp 目录
            temp_path = f"/tmp/{original_filename}"
            s3_client.download_file(bucket, key, temp_path)
            
            # 4. 执行核心 RAG 索引逻辑
            retriever_mode = os.getenv("RETRIEVER_MODE", "MANUAL")
            
            if retriever_mode == "BEDROCK_KB":
                print("[Worker] 检测到 BEDROCK_KB 模式，跳过本地嵌入过程...")
                update_task_status(task_id, "COMPLETED", "已触发 AWS Bedrock 知识库自动同步。")
            else:
                print("[Worker] 执行 MANUAL 模式本地嵌入...")
                # 在 SQS 触发的同步 Handler 中运行异步逻辑
                asyncio.run(process_into_vectorstore(temp_path, original_filename))
                update_task_status(task_id, "COMPLETED", "文档解析与消息队列处理圆满完成。")
                
            print(f"[Worker] 任务 {task_id} 处理成功。")
            
        except Exception as e:
            import traceback
            error_info = traceback.format_exc()
            print(f"[Worker] 任务 {task_id} 发生错误: {e}\n{error_info}")
            # 更新状态为 FAILED，这样 SQS 会根据重试策略决定是否重发
            if task_id != "UNKNOWN":
                update_task_status(task_id, "FAILED", f"处理失败: {str(e)}")
            
            # 既然 SQS 有重试机制，在这里抛出异常可以让 SQS 知道处理失败
            raise e
