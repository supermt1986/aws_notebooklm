import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const resources = {
    zh: {
        translation: {
            "knowledge_base_files": "知识库文件",
            "files_count": "{{count}} 份",
            "no_docs": "暂无文档",
            "app_title": "AWS NotebookLM",
            "app_subtitle": "(Cloud Variant)",
            "upload_btn": "准备知识库资源 (多模态)",
            "uploading": "正在上传...",
            "upload_success": "上传成功",
            "upload_fail": "上传失败",
            "welcome_title": "欢迎使用全栈云原生知识库",
            "welcome_desc": "采用 React + Serverless + 架构无关适配层。您可以尝试上传文档并交流！",
            "search_placeholder": "问关于上传文档的任何问题...",
            "retrieving": "知识库检索中",
            "server_error": "连接服务器失败，请检查后端服务是否正在运行。",
            "fetch_doc_error": "获取文档列表失败",
            "switch_lang": "日本語"
        }
    },
    ja: {
        translation: {
            "knowledge_base_files": "ナレッジベースファイル",
            "files_count": "{{count}} 件",
            "no_docs": "ドキュメントなし",
            "app_title": "AWS NotebookLM",
            "app_subtitle": "(クラウド版)",
            "upload_btn": "ナレッジリソースを準備",
            "uploading": "アップロード中...",
            "upload_success": "アップロード成功",
            "upload_fail": "アップロード失敗",
            "welcome_title": "クラウドネイティブナレッジベースへようこそ",
            "welcome_desc": "React + Serverless アーキテクチャを採用しています。ドキュメントをアップロードしてお試しください！",
            "search_placeholder": "アップロードしたドキュメントについて質問してください...",
            "retrieving": "ナレッジベース検索中",
            "server_error": "サーバーへの接続に失敗しました。",
            "fetch_doc_error": "ドキュメントリストの取得に失敗しました",
            "switch_lang": "中文"
        }
    }
};

i18n
    .use(initReactI18next)
    .init({
        resources,
        lng: "zh",
        fallbackLng: "zh",
        interpolation: {
            escapeValue: false
        }
    });

export default i18n;
