"""
議事録生成システムのFlaskアプリケーション
"""
import os
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from src.transcriber import Transcriber
from src.minutes_generator import MinutesGenerator
from src.google_docs_client import GoogleDocsClient
from src.slack_client import SlackClient
from pydub import AudioSegment


import sys
import os

# Vercel用のパス設定
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
static_folder = os.path.join(project_root, 'static')
template_folder = os.path.join(project_root, 'templates')

app = Flask(__name__, static_folder=static_folder, template_folder=template_folder)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

# アップロードフォルダを作成
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 処理結果を保存する辞書（セッション管理）
processing_results = {}


def allowed_file(filename):
    """許可されたファイル形式かチェック"""
    ALLOWED_EXTENSIONS = {'mp4', 'm4a', 'wav', 'mp3', 'flac', 'ogg', 'webm', 'txt', 'md'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def is_text_file(filename):
    """テキストファイルかチェック"""
    return filename.endswith('.txt') or filename.endswith('.md')


def process_audio_file(file_path, session_id):
    """ファイル処理をバックグラウンドで実行"""
    try:
        result = {
            'status': 'processing',
            'step': 'transcription',
            'transcript': None,
            'minutes': None,
            'document_url': None,
            'document_title': None,
            'slack_message': None,
            'error': None
        }
        processing_results[session_id] = result
        
        filename = os.path.basename(file_path)
        is_text = is_text_file(filename)
        
        # ステップ1: 文字起こし
        if is_text:
            result['step'] = 'transcription'
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript = f.read()
            result['transcript'] = transcript
        else:
            result['step'] = 'transcription'
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT_ID')
            transcriber = Transcriber(project_id=project_id)
            
            audio = AudioSegment.from_file(file_path)
            duration_seconds = len(audio) / 1000.0
            
            if duration_seconds >= 60:
                transcript = transcriber.transcribe_long_audio(file_path)
            else:
                transcript = transcriber.transcribe_file(file_path)
            
            result['transcript'] = transcript
        
        # ステップ2: 議事録生成
        result['step'] = 'generating_minutes'
        generator = MinutesGenerator()
        minutes = generator.generate_minutes(transcript)
        result['minutes'] = minutes
        
        # ステップ3: Googleドキュメントに保存
        result['step'] = 'saving_to_docs'
        today = datetime.now().strftime('%Y-%m-%d')
        document_title = f"minutes_{today}"
        
        docs_client = GoogleDocsClient()
        folder_name = "minutes_test"
        folder_id = docs_client.get_or_create_folder(folder_name)
        document_id = docs_client.create_document(document_title, minutes, folder_id=folder_id)
        document_url = docs_client.get_document_url(document_id)
        
        result['document_url'] = document_url
        result['document_title'] = document_title
        
        # ステップ4: Slack通知
        result['step'] = 'sending_slack'
        slack_client = SlackClient()
        slack_client.send_document_notification(document_title, document_url, folder_name)
        result['slack_message'] = f"Slackに通知を送信しました: {document_title}"
        
        result['status'] = 'completed'
        result['step'] = 'completed'
        
    except Exception as e:
        result['status'] = 'error'
        result['error'] = str(e)
        import traceback
        result['traceback'] = traceback.format_exc()


@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload_file():
    """ファイルアップロード処理"""
    if 'file' not in request.files:
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        filename = f"{timestamp}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        session_id = timestamp
        thread = threading.Thread(target=process_audio_file, args=(file_path, session_id))
        thread.start()
        
        return jsonify({'session_id': session_id})
    
    return jsonify({'error': '許可されていないファイル形式です'}), 400


@app.route('/status/<session_id>')
def get_status(session_id):
    """処理ステータスを取得"""
    if session_id not in processing_results:
        return jsonify({'error': 'セッションが見つかりません'}), 404
    
    return jsonify(processing_results[session_id])


@app.route('/download/<session_id>')
def download_file(session_id):
    """生成された議事録をダウンロード"""
    if session_id not in processing_results:
        return jsonify({'error': 'セッションが見つかりません'}), 404
    
    result = processing_results[session_id]
    if not result.get('minutes'):
        return jsonify({'error': '議事録が生成されていません'}), 404
    
    # 一時ファイルとして保存
    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"{session_id}_minutes.md")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(result['minutes'])
    
    return send_file(output_file, as_attachment=True, download_name='minutes.md')


# Vercel用のエントリーポイント
# @vercel/pythonはFlaskアプリを自動的にWSGIアプリケーションとして認識します
handler = app

if __name__ == '__main__':
    load_dotenv()
    app.run(debug=True, host='0.0.0.0', port=5000)

