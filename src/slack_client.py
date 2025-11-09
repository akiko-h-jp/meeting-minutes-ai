"""
Slack通知モジュール
"""
import os
import requests
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClient:
    def __init__(self, webhook_url: str = None, bot_token: str = None):
        """
        初期化
        
        Args:
            webhook_url: Slack Incoming Webhook URL
            bot_token: Slack Bot User OAuth Token
        """
        if webhook_url is None:
            webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        
        if bot_token is None:
            bot_token = os.getenv('SLACK_BOT_TOKEN')
        
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.client = WebClient(token=bot_token) if bot_token else None
    
    def send_message(self, message: str, channel: str = None):
        """
        メッセージを送信
        
        Args:
            message: 送信するメッセージ
            channel: チャンネル名（Bot Token使用時）
        """
        if self.webhook_url:
            # Incoming Webhookを使用
            payload = {"text": message}
            response = requests.post(self.webhook_url, json=payload)
            response.raise_for_status()
        elif self.client and channel:
            # Bot Tokenを使用
            try:
                self.client.chat_postMessage(channel=channel, text=message)
            except SlackApiError as e:
                raise Exception(f"Slack APIエラー: {e.response['error']}")
        else:
            raise ValueError("Webhook URLまたはBot Tokenが設定されていません")
    
    def send_document_notification(self, document_title: str, document_url: str, folder_name: str = None):
        """
        ドキュメント保存通知を送信
        
        Args:
            document_title: ドキュメントタイトル
            document_url: ドキュメントURL
            folder_name: 保存先フォルダ名（オプション）
        """
        message = f"📄 議事録がGoogleドキュメントに保存されました\n\n"
        message += f"ファイル名: {document_title}\n"
        message += f"URL: {document_url}\n"
        if folder_name:
            message += f"保存先フォルダ: {folder_name}"
        
        channel = os.getenv('SLACK_CHANNEL')
        self.send_message(message, channel=channel)

