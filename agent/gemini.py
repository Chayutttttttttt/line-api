"""Gemini prompts, quoted-file uploads, and response generation."""

import io
import os

import requests
from google import genai
from google.genai import types

from config import CHANNEL_ACCESS_TOKEN


def get_genai_response(user_msg: str, file_id: str = None) -> str:
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    prompt = f'''Ask: {user_msg}
            Task restrictions:
            - ห้ามใช้เครื่องหมาย ``` (Markdown Code Block) หรือ ** (ตัวหนา) ในการตอบเด็ดขาด
            - ให้ตอบกลับมาเป็นข้อความตัวอักษรธรรมดา (Plain Text) เท่านั้น
            - เอาเฉพาะส่วนเนื้อหาที่เป็นคำตอบโดยตรง ไม่ต้องมีคำเกริ่นนำหรือคำลงท้าย
            - เว้นบรรทัดประโยคต่อประโยค'''

    config = types.GenerateContentConfig(
        system_instruction="คุณคือผู้เชี้ยวชาญด้านการศึกษาเเละการให้ข้อมูลที่ถูกต้อง คุณต้องวิเคราะให้เป็นกันเองอ่านง่าย",
        tools=[types.Tool(google_search=types.GoogleSearch())],
        temperature=0.3,
    )

    client = genai.Client(api_key=gemini_api_key)

    contents_payload = [prompt]

    if file_id:
        url = f'https://api-data.line.me/v2/bot/message/{file_id}/content'
        headers = {
            'Authorization': f'Bearer {CHANNEL_ACCESS_TOKEN}'
        }
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                file_content = response.content
                file_stream = io.BytesIO(file_content)

                # LINE จะส่งค่าเช่น 'image/jpeg' หรือ 'application/pdf' มาให้ใน headers เสมอ
                content_type_from_line = response.headers.get('Content-Type')

                # อัปโหลดขึ้น Gemini File API
                uploaded_file = client.files.upload(
                    file=file_stream,
                    config=types.UploadFileConfig(
                        mime_type=content_type_from_line
                    )
                )

                contents_payload.append(uploaded_file)
            else:
                print(f"ดาวน์โหลดไฟล์จาก LINE ล้มเหลว Status: {response.status_code}")
        except Exception as e:
            print(f"เกิดข้อผิดพลาดในการจัดการไฟล์: {e}")

    # ส่งให้ Gemini ประมวลผล
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents_payload,
            config=config
        )

        if response.text:
            return response.text.strip()
        else:
            return "ขออภัย ฉันไม่สามารถประมวลผลคำขอของคุณได้ในขณะนี้"
    except Exception as e:
        print(f"เกิดข้อผิดพลาดจาก Gemini API: {e}")
        return "เกิดข้อผิดพลาดในการเชื่อมต่อกับระบบ AI"
