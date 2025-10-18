from ncatbot.core import BotClient
from ncatbot.utils import get_log

# from commands import commands


if __name__ == '__main__':
    logger = get_log()
    bot = BotClient()
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info('KeyboardInterrupt')
