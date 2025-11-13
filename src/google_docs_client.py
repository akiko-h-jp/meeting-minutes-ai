"""
Google Docs APIを使用したドキュメント管理モジュール
"""
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle


SCOPES = ['https://www.googleapis.com/auth/documents', 'https://www.googleapis.com/auth/drive']


class GoogleDocsClient:
    def __init__(self, credentials_file: str = None, token_file: str = None):
        """
        初期化
        
        Args:
            credentials_file: OAuth2認証情報ファイルのパス
            token_file: トークンファイルのパス
        """
        if credentials_file is None:
            # 環境変数から認証情報を取得
            credentials_json = os.getenv('GOOGLE_OAUTH_CREDENTIALS')
            if credentials_json:
                # 環境変数がJSON文字列の場合、一時ファイルとして保存
                import json
                import tempfile
                try:
                    # JSON文字列をパースして検証
                    json.loads(credentials_json)
                    # 一時ファイルを作成
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
                    temp_file.write(credentials_json)
                    temp_file.close()
                    credentials_file = temp_file.name
                except json.JSONDecodeError:
                    # JSON文字列でない場合は、ファイルパスとして扱う
                    credentials_file = credentials_json
            else:
                # 環境変数が設定されていない場合は、デフォルトのパスを試す
                credentials_file = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        
        if token_file is None:
            token_file = os.getenv('GOOGLE_TOKEN_FILE', 'token.json')
        
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.creds = self._authenticate()
        self.docs_service = build('docs', 'v1', credentials=self.creds)
        self.drive_service = build('drive', 'v3', credentials=self.creds)
    
    def _authenticate(self):
        """OAuth2認証を実行"""
        # まず、サービスアカウントキーを試す（クラウド環境用）
        service_account_json = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
        if service_account_json:
            try:
                # JSON文字列をパース
                service_account_info = json.loads(service_account_json)
                # サービスアカウント認証情報を作成
                creds = service_account.Credentials.from_service_account_info(
                    service_account_info, scopes=SCOPES)
                return creds
            except (json.JSONDecodeError, ValueError) as e:
                # JSON文字列でない場合は、ファイルパスとして扱う
                if os.path.exists(service_account_json):
                    creds = service_account.Credentials.from_service_account_file(
                        service_account_json, scopes=SCOPES)
                    return creds
        
        # サービスアカウントキーが設定されていない場合は、OAuth認証を試す（ローカル環境用）
        creds = None
        
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_file or not os.path.exists(self.credentials_file):
                    raise FileNotFoundError(
                        f"認証情報ファイルが見つかりません: {self.credentials_file}\n"
                        "Render環境では、環境変数GOOGLE_SERVICE_ACCOUNT_JSONにサービスアカウントキーのJSONを設定してください。"
                    )
                
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)
        
        return creds
    
    def get_or_create_folder(self, folder_name: str) -> str:
        """
        フォルダを取得または作成
        
        Args:
            folder_name: フォルダ名
            
        Returns:
            フォルダID
        """
        # 既存のフォルダを検索
        results = self.drive_service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)"
        ).execute()
        
        items = results.get('files', [])
        if items:
            return items[0]['id']
        
        # フォルダが存在しない場合は作成
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')
    
    def create_document(self, title: str, content: str, folder_id: str = None) -> str:
        """
        ドキュメントを作成
        
        Args:
            title: ドキュメントタイトル
            content: ドキュメントの内容（Markdown形式）
            folder_id: 保存先フォルダID（オプション）
            
        Returns:
            作成されたドキュメントID
        """
        document = {'title': title}
        doc = self.docs_service.documents().create(body=document).execute()
        document_id = doc.get('documentId')
        
        # フォルダに移動
        if folder_id:
            file = self.drive_service.files().get(fileId=document_id, fields='parents').execute()
            previous_parents = ",".join(file.get('parents'))
            self.drive_service.files().update(
                fileId=document_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields='id, parents'
            ).execute()
        
        # コンテンツを更新
        self.update_document_content(document_id, content)
        
        return document_id
    
    def update_document_content(self, document_id: str, content: str):
        """
        ドキュメントのコンテンツを更新
        
        Args:
            document_id: ドキュメントID
            content: 更新する内容（Markdown形式）
        """
        # Markdownをプレーンテキストに変換（簡易版）
        # 実際の実装では、より高度なMarkdownパーサーを使用することを推奨
        text_content = content.replace('# ', '').replace('## ', '').replace('### ', '')
        
        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': text_content
                }
            }
        ]
        
        self.docs_service.documents().batchUpdate(
            documentId=document_id,
            body={'requests': requests}
        ).execute()
    
    def get_document_url(self, document_id: str) -> str:
        """
        ドキュメントのURLを取得
        
        Args:
            document_id: ドキュメントID
            
        Returns:
            ドキュメントのURL
        """
        return f"https://docs.google.com/document/d/{document_id}"

