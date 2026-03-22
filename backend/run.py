import uvicorn

if __name__ == "__main__":
    print("================================================")
    print("🚀 启动 NotebookLM Serverless 本地测试代理...")
    print("访问地址: http://localhost:8000/api/health")
    print("================================================")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
