import asyncio
from asyncio import sleep


class AIClient:
    def __init__(self, name):
        self.name = name

    async def request(self, text):
        print('AI analysing your request...')
        await sleep(5)
        return f'Hello {self.name}, I am a chatbot. Your request "{text}" is being processed.'
    

class CommandSystem:
    def __init__(self, ai_client):
        self.ai_client = ai_client
        
    async def __call__(self, text):
        if not text.startswith('/'):
            return
        command = getattr(self, text.split()[0][1:])
        return await command(*text.split()[1:])
        
    async def test(self, *args):
        return ','.join(args)
        
    async def ai(self, *args):
        return await self.ai_client.request(args[0])


async def main():
    ai_client = AIClient('Hirasawa')
    command_system = CommandSystem(ai_client)
    print(await command_system('/ai Hello'))
    print(await command_system('/test 123'))
    

if __name__ == '__main__':
    asyncio.run(main())