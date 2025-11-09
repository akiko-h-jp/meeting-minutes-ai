"""
OpenAI APIを使用した議事録生成モジュール
"""
import os
from openai import OpenAI
import httpx


class MinutesGenerator:
    def __init__(self, api_key: str = None):
        """
        初期化
        
        Args:
            api_key: OpenAI APIキー（未指定の場合は環境変数から取得）
        """
        if api_key is None:
            api_key = os.getenv('OPENAI_API_KEY')
        
        if not api_key:
            raise ValueError("OpenAI APIキーが設定されていません")
        
        # httpx.Clientを作成（proxiesなし）
        http_client = httpx.Client()
        self.client = OpenAI(api_key=api_key, http_client=http_client)
        self.model = "gpt-4o-mini"
    
    def generate_minutes(self, transcript: str) -> str:
        """
        文字起こしテキストから議事録を生成
        
        Args:
            transcript: 文字起こしテキスト
            
        Returns:
            生成された議事録（Markdown形式）
        """
        prompt = self._create_prompt(transcript)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "あなたは会議の議事録を作成する専門家です。文字起こしテキストから構造化された議事録を生成してください。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        
        return response.choices[0].message.content
    
    def _create_prompt(self, transcript: str) -> str:
        """
        議事録生成用のプロンプトを作成
        
        Args:
            transcript: 文字起こしテキスト
            
        Returns:
            プロンプトテキスト
        """
        return f"""以下の文字起こしテキストから、構造化された議事録をMarkdown形式で生成してください。

【文字起こしテキスト】
{transcript}

【議事録の形式】
以下の形式で議事録を作成してください：

# 議事録

## 日時
[会議の日時（文字起こしから推測）]

## 参加者
[参加者の名前（文字起こしから推測）]

## 議題
[主な議題やトピック]

## 議論内容
[主要な議論のポイント]

## 決定事項
[決定した事項]

## アクションアイテム
[今後のアクションアイテムと担当者]

## その他
[その他の重要な情報]
"""
    
    def generate_minutes_from_file(self, transcript_file_path: str) -> str:
        """
        文字起こしファイルから議事録を生成
        
        Args:
            transcript_file_path: 文字起こしファイルのパス
            
        Returns:
            生成された議事録（Markdown形式）
        """
        with open(transcript_file_path, 'r', encoding='utf-8') as f:
            transcript = f.read()
        
        return self.generate_minutes(transcript)

