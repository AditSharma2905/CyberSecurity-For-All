import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

class LeaderboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.quiz_id = self.scope.get("url_route", {}).get("kwargs", {}).get("quiz_id")
        self.group_name = f"leaderboard_{self.quiz_id}"

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_leaderboard()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def leaderboard_update(self, event):
        await self.send_leaderboard()

    async def send_leaderboard(self):
        data = await self.get_leaderboard(self.quiz_id)
        await self.send(text_data=json.dumps({
            "type": "leaderboard_update",
            "data": data
        }))

    @database_sync_to_async
    def get_leaderboard(self, quiz_id):
        from .models import QuizAttempt

        attempts = (
            QuizAttempt.objects
            .filter(quiz_id=quiz_id)
            .select_related("user")
            .order_by("-score", "completed_at")[:20]
        )

        return [
            {
                "rank": rank,
                "username": a.user.get_full_name() or a.user.username if a.user else "Anonymous",
                "score": a.score,
                "total": a.total_questions,
                "percentage": round(a.score / a.total_questions * 100) if a.total_questions else 0,
                "completed_at": a.completed_at.strftime("%H:%M:%S"),
            }
            for rank, a in enumerate(attempts, start=1)
        ]
