"""
議事録生成システムのメインスクリプト（コマンドライン用）
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

from src.transcriber import Transcriber
from src.minutes_generator import MinutesGenerator
from src.google_docs_client import GoogleDocsClient
from src.slack_client import SlackClient
from pydub import AudioSegment


def main():
    """メイン処理"""
    load_dotenv()
    
    # 環境変数の確認
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '').strip('"\'')
    if not credentials_path or not os.path.exists(credentials_path):
        print("エラー: GOOGLE_APPLICATION_CREDENTIALSが正しく設定されていません")
        sys.exit(1)
    
    project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
    if not project_id:
        print("エラー: GOOGLE_CLOUD_PROJECT_IDが設定されていません")
        sys.exit(1)
    
    if len(sys.argv) < 2:
        print("使用方法: python src/main.py <音声ファイルまたはテキストファイルのパス>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    if not os.path.exists(input_file):
        print(f"エラー: ファイルが見つかりません: {input_file}")
        sys.exit(1)
    
    # ファイルタイプの判定
    is_text_file = input_file.endswith('.txt') or input_file.endswith('.md')
    
    try:
        # ステップ1: 文字起こし
        print("\n" + "="*50)
        print("文字起こし中...")
        print("="*50)
        
        if is_text_file:
            with open(input_file, 'r', encoding='utf-8') as f:
                transcript = f.read()
            print("テキストファイルを読み込みました")
        else:
            transcriber = Transcriber(project_id=project_id)
            
            # 音声の長さを確認
            audio = AudioSegment.from_file(input_file)
            duration_seconds = len(audio) / 1000.0
            
            if duration_seconds >= 60:
                transcript = transcriber.transcribe_long_audio(input_file)
            else:
                transcript = transcriber.transcribe_file(input_file)
            
            print(f"文字起こし完了（{len(transcript)}文字）")
        
        # ステップ2: 議事録生成
        print("\n" + "="*50)
        print("議事録生成中...")
        print("="*50)
        
        generator = MinutesGenerator()
        minutes = generator.generate_minutes(transcript)
        
        print("議事録生成完了")
        
        # ステップ3: Googleドキュメントに保存
        print("\n" + "="*50)
        print("Googleドキュメントに保存中...")
        print("="*50)
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            document_title = f"minutes_{today}"
            
            print("\n認証が必要です。ブラウザが開きますので、Googleアカウントでログインしてください。")
            docs_client = GoogleDocsClient()
            
            folder_name = "minutes_test"
            folder_id = docs_client.get_or_create_folder(folder_name)
            document_id = docs_client.create_document(document_title, minutes, folder_id=folder_id)
            document_url = docs_client.get_document_url(document_id)
            
            print("\n" + "="*50)
            print("✅ Googleドキュメントに保存しました！")
            print("="*50)
            print(f"タイトル: {document_title}")
            print(f"URL: {document_url}")
            print(f"ドキュメントID: {document_id}")
            print("="*50)
            
            # ステップ4: Slack通知
            print("\nSlackに通知を送信中...")
            slack_client = SlackClient()
            slack_client.send_document_notification(document_title, document_url, folder_name)
            print("✅ Slackに通知を送信しました")
            
        except Exception as e:
            print(f"Googleドキュメント保存またはSlack通知でエラー: {e}")
            sys.exit(1)
        
        print("\n" + "="*50)
        print("✅ 全ての処理が完了しました！")
        print("="*50)
        
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

