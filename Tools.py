import sqlite3
import random
import math
import aiohttp


class Country:
    def __init__(self, base_data):
        self.code = base_data[1]
        self.name1 = base_data[2]
        self.name2 = base_data[3]
        self.capital = base_data[4]
        self.location = base_data[5]
        self.exact_location = base_data[6]

    def __hash__(self):
        return self.code

    def is_correct_name(self, name):
        if not self.has_second_name():
            return wagner_fischer(name.lower(), self.name1.lower()) <= len(self.name1) // 3

        return wagner_fischer(name.lower(), self.name1.lower()) <= len(self.name1) // 3 or \
            wagner_fischer(name.lower(), self.name2.lower()) <= len(self.name2) // 3

    def has_second_name(self):
        return self.name2 is not None

    def is_correct_capital(self, name):
        return wagner_fischer(name.lower(), self.capital.lower()) <= len(self.capital) // 3

    def __str__(self):
        return self.name1

    def __repr__(self):
        return self.name1


class DatabaseConnection:
    def __init__(self, path):
        self.path = path

    def __enter__(self):
        self._connection = sqlite3.connect(self.path)
        return self._connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._connection.commit()
        self._connection.close()


class CountriesDatabase:
    def __init__(self, path):
        self.path = path

    def get_random_not_used_country(self, params: set[str] = (), used=("123",)):
        params_str = ' AND '.join(params)
        params_str += ' AND' if params else ''
        used_str = "(" + ', '.join([f'"{code}"' for code in used]) + ")"
        request = f"""SELECT * FROM CountryNames WHERE {params_str} code not in {used_str}"""

        with DatabaseConnection(self.path) as cursor:
            rows = cursor.execute(request).fetchall()

        if not rows:
            raise ConnectionError(f"Empty database answer on request: {request}")

        return Country(random.choice(rows))

    def get_country_by_condition(self, condition: str):
        with DatabaseConnection(self.path) as cursor:
            return Country(cursor.execute(f"""SELECT * FROM CountryNames WHERE {condition}""").fetchone())


class Game:
    def __init__(self, difficulty, player, var_num):
        self.difficulty = difficulty
        self.player = player
        self.var_num = var_num
        self.used = set()
        self.current_question = 0
        self.points = 0
        self.right_questions_num = 0
        self.hidden_country = None
        self.countries_database = CountriesDatabase("Countries.sqlite")
        self.hint_num = 0
        self.question_num = 4

    def get_answer_variants(self, country, need_capital=False):
        if self.var_num == 0:
            return []
        res = [country]
        codes = {country.code}

        for i in range(self.var_num - 1):
            if need_capital:
                c = self.countries_database.get_random_not_used_country(["capital is not null",
                                                                         f"difficulty=={self.difficulty}"], self.used)
            else:
                c = self.countries_database.get_random_not_used_country([f"difficulty=={self.difficulty}"], self.used)

            res.append(c)
            codes.add(c.code)

        return res

    def get_next_question(self):
        self.hint_num = 0
        self.current_question += 1

    def hint(self):
        self.hint_num += 1

    def is_right_guess(self, guess):
        pass

    async def get_reaction_on_answer(self, guess: str):
        if self.is_right_guess(guess):
            self.points += int(self.difficulty * (self.var_num if self.var_num != 0 else 10) // 4 / (self.hint_num + 1))
            self.right_questions_num += 1

    def get_ending_message(self):
        pass

    def end_game(self):
        with DatabaseConnection("Points.sqlite") as cursor:
            note = cursor.execute(f"""SELECT * FROM Scores WHERE userid=="{self.player.id}" """).fetchall()
            if not note:
                cursor.execute(f"""INSERT INTO Scores VALUES (null, "{self.player.id}", {self.points},
                               "{self.player.global_name}")""")
            else:
                cursor.execute(f"""UPDATE Scores SET total_score=total_score + {self.points}
                                   WHERE userid="{self.player.id}" """)


def get_span(geo_object):
    bound = geo_object['boundedBy']['Envelope']
    lower, upper = list(map(float, bound['lowerCorner'].split())), list(map(float, bound['upperCorner'].split()))
    deltas = [str(upper[0] - lower[0]), str(upper[1] - lower[1])]
    return ",".join(deltas)


def clamp(value, bottom=None, top=None):
    if bottom is not None and value <= bottom:
        return bottom

    if top is not None:
        return top if value > top else value

    return value


def wagner_fischer(s1, s2):
    len_s1, len_s2 = len(s1), len(s2)
    if len_s1 > len_s2:
        s1, s2 = s2, s1
        len_s1, len_s2 = len_s2, len_s1

    current_row = range(len_s1 + 1)
    for i in range(1, len_s2 + 1):
        previous_row, current_row = current_row, [i] + [0] * len_s1
        for j in range(1, len_s1 + 1):
            add, delete, change = previous_row[j] + 1, current_row[j-1] + 1, previous_row[j-1]
            if s1[j-1] != s2[i-1]:
                change += 1
            current_row[j] = min(add, delete, change)

    return current_row[len_s1]


def string_from_lon_lat(lon_lats):
    res = []
    for a in lon_lats:
        res.append(str(a[0]))
        res.append(str(a[1]))
    return ','.join(res)


class ImageLoader:
    def __init__(self):
        self._session = aiohttp.ClientSession()

    async def load_world_map(self, mode, points):
        domain = "http://static-maps.yandex.ru/1.x"
        params = {
            "ll": "0 0",
            "z": 2,
            "l": mode,
            "pl": string_from_lon_lat(points)
        }

        response = await self._session.get(domain, params=params)

        map_file = "map.png"
        with open(map_file, "wb") as file:
            file.write(response.content)

        return map_file


def lon_lat_from_str(string):
    return list(map(float, string.split()))


def size_from_obj(country_obj):
    envelope = country_obj['boundedBy']['Envelope']

    lower = lon_lat_from_str(envelope['lowerCorner'])
    upper = lon_lat_from_str(envelope['upperCorner'])

    return [upper[0] - lower[0], upper[1] - lower[1]]


def lonlat_distance_between_countries(a, b):
    degree_to_meters_factor = 111 * 1000
    a_lon, a_lat = map(float, a['Point']['pos'].split())
    b_lon, b_lat = map(float, b['Point']['pos'].split())
    size_a = size_from_obj(a)
    size_b = size_from_obj(b)

    d_lon = clamp(abs(a_lon - b_lon) - (size_a[0] + size_b[0]) * 0.37, bottom=0)
    d_lat = clamp(abs(a_lat - b_lat) - (size_a[1] + size_b[1]) * 0.2, bottom=0)

    radians_latitude = math.radians((a_lat + b_lat) / 2.)
    lat_lon_factor = math.cos(radians_latitude)

    dx = d_lon * degree_to_meters_factor * lat_lon_factor
    dy = d_lat * degree_to_meters_factor

    distance = math.sqrt(dx * dx + dy * dy)

    return clamp(distance, bottom=1000)


def get_table_string(table, player_place):
    res = ''
    player_used = False

    if len(table) <= 3:
        for i in range(len(table)):
            res += f"{i + 1}. {table[i][3]}: {table[i][2]}\n"
        return res

    if player_place <= 3:
        for i in range(3):
            res += f"{i + 1}. {table[i][3]}: {table[i][2]}\n"
        res += ". . .\n"
        return res

    for i in range(3):
        res += f"{i + 1}. {table[i][3]}: {table[i][2]}\n"

    if player_place <= 5:
        for i in range(3, player_place + 1):
            player_used = True
            res += f"{i + 1}. {table[i][3]}: {table[i][2]}\n"

    res += ". . .\n"
    if player_used:
        return res

    for i in range(player_place - 2, player_place + 1):
        try:
            res += f"{i + 1}. {table[i][3]}: {table[i][2]}\n"
        except IndexError:
            break

    res += ". . .\n" if len(table) - 2 >= player_place else ""
    return res


def binary_search(array, value, key=lambda x: x, reverse=False):
    low = 0
    high = len(array) - 1
    mid = 0

    while low <= high:
        mid = (high + low) // 2
        if not reverse:
            if key(array[mid]) < value:
                low = mid + 1
            elif key(array[mid]) > value:
                high = mid - 1
            else:
                return mid
        else:
            if key(array[mid]) > value:
                low = mid + 1
            elif key(array[mid]) < value:
                high = mid - 1
            else:
                return mid

    return -1
