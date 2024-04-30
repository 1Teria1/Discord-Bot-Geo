from discord.ext import commands
from Games import FlagsGame, CapitalsGame, HotColdGame
from Tools import DatabaseConnection, Game, binary_search, get_table_string


async def check_game_args(ctx, difficulty, answer_vars, game_type):
    if not difficulty.isdigit():
        await ctx.channel.send("Сложность должна быть целым числом от 1 до 5")
        return False

    if not(5 >= int(difficulty) >= 1):
        await ctx.channel.send("Сложность должна быть целым числом от 1 до 5")
        return False

    if not answer_vars.isdigit():
        await ctx.channel.send("Количество вариантов ответа должно быть целым числом от 0 до 8")
        return False

    if not(8 >= int(answer_vars) >= 0):
        await ctx.channel.send("Количество вариантов ответа должно быть целым числом от 0 до 8")
        return False

    if int(answer_vars) == 1:
        await ctx.channel.send("Играть с одним варинтом ответа скучно")
        return False

    return True


class Geo(commands.Cog):
    def __init__(self, bot, logger):
        self.bot = bot
        self.logger = logger
        self.games: dict[Game] = {}

    @commands.command("h")
    async def help(self, ctx):
        await ctx.channel.send(f"Я Гео\nЯ могу сыграть с тобой в игры, которые помогут тебе выучить географию!\n"
                               f"У меня есть три игры - флаги, столицы, горячо-холодно\n"
                               f"Ты можешь выбрать сложность: 1 - самый простой режим, 5 - самый сложный режим")

    @commands.command("помощь")
    async def commands_help(self, ctx):
        await self.help(ctx)
        await ctx.channel.send(f"Комманды:\n"
                               f"1. -флаги (сложность(1-5)) (количество вариантов ответа(0-8)) - игра с флагами\n"
                               f"2. -столицы (сложность(1-5)) (количество вариантов ответа(0-8)) - игра со столицами\n"
                               f"3. -горячо-холодно (сложность(1-5)) - игра с угадыванием страны\n"
                               f"4. -- (ответ) - дать ответ в игре\n"
                               f"5. -счёт - посмотреть свой счёт\n"
                               f"6. -таблица - посмотреть таблицу со счётами других игроков и своё место в ней\n")

    @commands.command("счёт")
    async def send_score(self, ctx):
        with DatabaseConnection("Points.sqlite") as cursor:
            score = cursor.execute(f'SELECT total_score FROM Scores WHERE userid=="{ctx.message.author.id}"').fetchone()

        await ctx.channel.send(f"Ваш счёт: {score[0]}")

    @commands.command("таблица")
    async def send_leader_table(self, ctx):
        with DatabaseConnection("Points.sqlite") as cursor:
            score = cursor.execute(f'SELECT total_score FROM Scores'
                                   f' WHERE userid=="{ctx.message.author.id}"').fetchone()[0]

            table = cursor.execute(f"SELECT * FROM Scores").fetchall()
            table.sort(key=lambda x: x[2], reverse=True)

        await ctx.channel.send(get_table_string(table, binary_search(table, score, lambda x: x[2], reverse=True) + 1))

    @commands.command("флаги")
    async def start_flags_game(self, ctx, difficulty, answer_vars='4'):
        if not await check_game_args(ctx, difficulty, answer_vars, FlagsGame):
            return

        self.games[(ctx.channel, ctx.message.author.id)] = FlagsGame(int(difficulty), ctx.message.author,
                                                                     int(answer_vars))
        await self.ask_question(ctx)

    @commands.command("столицы")
    async def start_capitals_game(self, ctx, difficulty, answer_vars='4'):
        if not await check_game_args(ctx, difficulty, answer_vars, CapitalsGame):
            return

        self.games[(ctx.channel, ctx.message.author.id)] = CapitalsGame(int(difficulty), ctx.message.author,
                                                                        int(answer_vars))
        await self.ask_question(ctx)

    @commands.command("горячо-холодно")
    async def start_hot_cold_game(self, ctx, difficulty):
        if not await check_game_args(ctx, difficulty, '4', FlagsGame):
            return

        game = HotColdGame(int(difficulty), ctx.message.author)
        await game.init()
        self.games[(ctx.channel, ctx.message.author.id)] = game
        await self.ask_question(ctx)

    @commands.command("подсказка")
    async def hint(self, ctx):
        game = self.games[(ctx.channel, ctx.message.author.id)]
        await ctx.channel.send(game.hint())

    async def ask_question(self, ctx):
        a, question = self.games[(ctx.channel, ctx.message.author.id)].get_next_question()
        if a is not None:
            await ctx.channel.send(a)

        await ctx.channel.send(question)

    @commands.command("-")
    async def guess(self, ctx, *args):
        name = " ".join(args).replace('ё', 'е')
        game = self.games.get((ctx.channel, ctx.message.author.id))
        if game is None:
            await ctx.channel.send("Вы должны начать игру, чтобы давать ответ")
            return
        message = await game.get_reaction_on_answer(name)

        if game.current_question > game.question_num:
            await ctx.channel.send(message)
            await ctx.channel.send(game.get_ending_message())
            game.end_game()
            self.games.pop((ctx.channel, ctx.message.author.id))
            return

        await ctx.channel.send(message)
        await self.ask_question(ctx)
