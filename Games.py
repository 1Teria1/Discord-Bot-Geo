from Tools import Country, DatabaseConnection, Game, lonlat_distance_between_countries
import random
import aiohttp


class FlagsGame(Game):
    def __init__(self, difficulty, player, var_num):
        super().__init__(difficulty, player, var_num)

    @staticmethod
    def get_flag_url(code):
        return f"https://flagpedia.net/data/flags/normal/{code.lower()}.png"

    def get_next_question(self):
        super().get_next_question()
        country = self.countries_database.get_random_not_used_country(params=[f"difficulty={self.difficulty}"],
                                                                      used=self.used)
        self.used.add(country.code)
        answer_vars = self.get_answer_variants(country)
        random.shuffle(answer_vars)
        question = f"{self.current_question}. Какой стране принадлежит этот флаг?"
        for i, var in enumerate(answer_vars):
            question += f"\n{i + 1}) {var.name1}"

        self.hidden_country = country
        return self.get_flag_url(country.code), question

    def is_right_guess(self, guess):
        return self.hidden_country.is_correct_name(guess)

    def get_ending_message(self):
        return f"Игра окончена! Вы ответили правильно на {self.right_questions_num} вопросов из 5 " \
               f"и заработали {self.points} очков!"

    async def get_reaction_on_answer(self, guess: str):
        await super().get_reaction_on_answer(guess)
        message = f"({self.hidden_country.name2})" if self.hidden_country.has_second_name() else ""

        if self.is_right_guess(guess):
            return f"Верно! Да, это флаг государства {self.hidden_country.name1} {message}."
        return f"Неверно! Нет, это флаг государства {self.hidden_country.name1} {message}."

    def hint(self):
        super().hint()

        if self.hint_num == 1:
            return f"Подсказка 1: Регион нахождения страны - {self.hidden_country.location}"
        return f"Подсказка 2: Регион нахождения страны - {self.hidden_country.exact_location}"


class CapitalsGame(Game):
    def __init__(self, difficulty, player, var_num):
        super().__init__(difficulty, player, var_num)

    def get_next_question(self):
        super().get_next_question()

        country = self.countries_database.get_random_not_used_country(["capital is not null",
                                                                       f"difficulty={self.difficulty}"], self.used)
        self.used.add(country.code)
        answer_vars = self.get_answer_variants(country, need_capital=True)
        random.shuffle(answer_vars)
        self.hidden_country = country
        question = f"{self.current_question}. Какой город является столицой страны {country.name1}?"
        for i, var in enumerate(answer_vars):
            question += f"\n{i + 1}) {var.capital}"
        return None, question

    def is_right_guess(self, guess):
        return self.hidden_country.is_correct_capital(guess)

    def get_ending_message(self):
        return f"Игра окончена! Вы ответили правильно на {self.right_questions_num} вопросов из 5 " \
               f"и заработали {self.points} очков!"

    async def get_reaction_on_answer(self,  guess: str):
        await super().get_reaction_on_answer(guess)

        message = f"({self.hidden_country.name2})" if self.hidden_country.has_second_name() else ""
        if self.is_right_guess(guess):
            return f"Верно! Да, столица государства {self.hidden_country.name1} {message} - это" \
                f" {self.hidden_country.capital}"
        return f"Неверно! Нет, столица государства {self.hidden_country.name1} {message} - это" \
               f" {self.hidden_country.capital}"

    def hint(self):
        super().hint()

        if self.hint_num == 1:
            return f"Первая буква столицы страны - {self.hidden_country.capital[0]}"
        return f"Первые три буквы столицы страны - {self.hidden_country.capital[:3]}"


class HotColdGame(Game):
    def __init__(self, difficulty, player):
        super().__init__(difficulty, player, var_num=0)
        self.guesses = []
        self.hidden_country = self.countries_database.get_random_not_used_country([f"difficulty={self.difficulty}"],
                                                                                  self.used)
        self.hidden_country_geo_object = None

    async def init(self):
        self.hidden_country_geo_object = await self.get_country_geo_object(self.hidden_country.name1)
        print(self.hidden_country)

    @staticmethod
    async def get_country_geo_object(country):
        session = aiohttp.ClientSession()
        geocoder_api_server = "http://geocode-maps.yandex.ru/1.x/"
        if isinstance(country, Country):
            geocoder_params = {
                "apikey": "40d1649f-0493-4b70-98ba-98533de7710b",
                "geocode": country.name1,
                "format": "json"
            }
        elif isinstance(country, str):
            geocoder_params = {
                "apikey": "40d1649f-0493-4b70-98ba-98533de7710b",
                "geocode": country,
                "format": "json"
            }

        response = await session.get(geocoder_api_server, params=geocoder_params)
        response_json = await response.json()
        toponym = response_json["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]

        await session.close()
        return toponym

    def get_next_question(self):
        super().get_next_question()

        if self.current_question == 1:
            return None, f"Угадай страну. Пиши названия стран, а я буду говорить наскололько далеко загаданная страна" \
                         f"\nПопытка номер 1:"
        if self.question_num == -1:
            return None, self.get_ending_message()
        self.question_num = self.current_question + 1
        return None, f"Попытка номер {self.current_question}:"

    async def get_reaction_on_answer(self,  guess: str):
        with DatabaseConnection("Countries.sqlite") as cursor:
            cursor.execute("SELECT name1, name2 FROM CountryNames").fetchall()
        if self.is_right_guess(guess):
            self.points += int(self.difficulty * 50 / (self.current_question + self.hint_num * 2))
            self.right_questions_num += 1
            self.question_num = -1
            return f"Да, вы угадали страну {self.hidden_country.name1} за {self.current_question} попыток"

        guess_country = await self.get_country_geo_object(guess)
        dist = lonlat_distance_between_countries(guess_country, self.hidden_country_geo_object)
        return f"Расстояние между {guess} и загаданной страной - {int(dist // 1000)} км"

    def is_right_guess(self, guess):
        return self.hidden_country.is_correct_name(guess)

    def add_points(self):
        self.points += self.difficulty

    def hint(self):
        super().hint()

        if self.hint_num == 1:
            return f"Первая буква названия страны - {self.hidden_country.name1[0]}"
        return f"Первые три буквы названия страны - {self.hidden_country.name1[:3]}"

    def get_ending_message(self):
        return f"Вы победили, вы получили {self.points} очков"
