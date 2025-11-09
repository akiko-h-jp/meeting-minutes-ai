"""
Google Cloud Speech-to-Text APIを使用した音声文字起こしモジュール
"""
import os
from google.cloud import speech
from pydub import AudioSegment


class Transcriber:
    def __init__(self, project_id: str, language_code: str = "ja-JP"):
        """
        初期化
        
        Args:
            project_id: Google Cloud プロジェクトID
            language_code: 言語コード（デフォルト: ja-JP）
        """
        self.client = speech.SpeechClient()
        self.project_id = project_id
        self.language_code = language_code
    
    def convert_audio_to_wav(self, audio_path: str) -> str:
        """
        音声ファイルをWAV形式に変換
        
        Args:
            audio_path: 入力音声ファイルのパス
            
        Returns:
            変換後のWAVファイルのパス
        """
        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.rsplit('.', 1)[0] + '_converted.wav'
        audio.export(wav_path, format="wav")
        return wav_path
    
    def transcribe_file(self, audio_path: str) -> str:
        """
        短い音声ファイル（1分未満）を文字起こし
        
        Args:
            audio_path: 音声ファイルのパス
            
        Returns:
            文字起こし結果のテキスト
        """
        # WAV形式に変換
        if not audio_path.endswith('.wav'):
            audio_path = self.convert_audio_to_wav(audio_path)
        
        with open(audio_path, "rb") as audio_file:
            content = audio_file.read()
        
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=self.language_code,
        )
        
        response = self.client.recognize(config=config, audio=audio)
        
        transcript = ""
        for result in response.results:
            transcript += result.alternatives[0].transcript + "\n"
        
        return transcript.strip()
    
    def transcribe_long_audio(self, audio_path: str) -> str:
        """
        長い音声ファイル（1分以上）を文字起こし（チャンク処理）
        
        Args:
            audio_path: 音声ファイルのパス
            
        Returns:
            文字起こし結果のテキスト
        """
        # WAV形式に変換
        if not audio_path.endswith('.wav'):
            audio_path = self.convert_audio_to_wav(audio_path)
        
        audio = AudioSegment.from_wav(audio_path)
        duration_seconds = len(audio) / 1000.0
        
        # 50秒ごとにチャンクに分割
        chunk_duration_ms = 50000
        chunks = []
        for i in range(0, len(audio), chunk_duration_ms):
            chunk = audio[i:i + chunk_duration_ms]
            chunks.append(chunk)
        
        transcript = ""
        for i, chunk in enumerate(chunks):
            chunk_path = f"{audio_path}_chunk_{i}.wav"
            chunk.export(chunk_path, format="wav")
            
            try:
                chunk_transcript = self.transcribe_file(chunk_path)
                transcript += chunk_transcript + "\n"
            except Exception as e:
                print(f"チャンク {i} の文字起こしでエラー: {e}")
            finally:
                # 一時ファイルを削除
                if os.path.exists(chunk_path):
                    os.remove(chunk_path)
        
        return transcript.strip()

