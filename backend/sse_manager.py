import asyncio

class SSEManager:
    def __init__(self):
        # We will map a task_id to an asyncio.Queue
        self.clients = {}

    def connect(self, task_id: str):
        queue = asyncio.Queue()
        self.clients[task_id] = queue
        return queue

    def disconnect(self, task_id: str):
        if task_id in self.clients:
            del self.clients[task_id]

    async def send_message(self, task_id: str, message: dict):
        if task_id in self.clients:
            import json
            await self.clients[task_id].put(f"data: {json.dumps(message)}\n\n")

    async def event_generator(self, task_id: str):
        queue = self.clients.get(task_id)
        if not queue:
            return
        
        try:
            while True:
                data = await queue.get()
                yield data
        except asyncio.CancelledError:
            self.disconnect(task_id)

sse_manager = SSEManager()
