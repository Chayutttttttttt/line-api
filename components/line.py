"""LINE webhook verification and text-message handling."""

from fastapi import APIRouter, Header, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.messaging.models import MarkMessagesAsReadByTokenRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent

from agent.gemini import get_genai_response
from config import CHANNEL_ACCESS_TOKEN, CHANNEL_SECRET

router = APIRouter()
configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(channel_secret=CHANNEL_SECRET)


@router.post("/webhook")
async def get_json(request: Request, x_line_signature: str = Header(None)):
    if x_line_signature is None:
        raise HTTPException(status_code=400, detail="Missing X-Line-Signature header")

    body = await request.body()
    body_str = body.decode("utf-8")

    try:
        handler.handle(body_str, x_line_signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if event.type == "message":
        api_client = ApiClient(configuration=configuration)
        messaging_api = MessagingApi(api_client)

        reply_token = event.reply_token
        user_message = event.message.text
        mark_as_read_token = event.message.mark_as_read_token

        is_group = False
        if event.source.type == "group" and event.message.mention:
            is_self = event.message.mention.mentionees[0].is_self
            if is_self == True:
                is_group = True

        if is_group:
            imin = event.message.mention.mentionees[0].index
            imax = event.message.mention.mentionees[0].length
            user_message = user_message[:imin] + user_message[imax:]

        quoted_message_id = event.message.quoted_message_id

        if event.source.type == "user" or is_group:
            reply_message = get_genai_response(
                user_message.strip(), file_id=quoted_message_id
            )
            messaging_api.mark_messages_as_read_by_token(
                mark_messages_as_read_by_token_request=MarkMessagesAsReadByTokenRequest(
                    markAsReadToken=mark_as_read_token
                )
            )
            messaging_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=reply_message)],
                )
            )
