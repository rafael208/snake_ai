# ai.py
"""
Автопилот змейки с гарантированной победой на поле любого размера.

=====================================================================
ИДЕЯ
=====================================================================

1. КОЛЬЦО (маршрут через всё поле)
   Строим замкнутый маршрут, проходящий через каждую клетку поля.
   Каждой клетке присваивается номер "слота" на этом кольце.

   * Если W*H чётно — это обычный гамильтонов цикл.
   * Если W и H оба нечётные — гамильтонова цикла НЕ СУЩЕСТВУЕТ
     (раскрасьте поле в шахматном порядке: клеток одного цвета на 1
     больше, а цикл обязан чередовать цвета). Поэтому строим цикл по
     всем клеткам, кроме угла E, и делаем "сдвоенный слот": угол E и
     диагональная к нему клетка C получают ОДИН И ТОТ ЖЕ номер.
     Оба соседних слота (клетки A и B) примыкают и к C, и к E, поэтому
     змейка может проходить этот слот через любую из двух клеток.

2. ИНВАРИАНТ БЕЗОПАСНОСТИ
   Тело змейки (от хвоста к голове) идёт строго по возрастанию номеров
   слотов и укладывается меньше чем в один оборот кольца.

   Пока инвариант выполняется:
     * все слоты между головой и хвостом ("окно") гарантированно пусты;
     * у головы ВСЕГДА есть ход — в следующий слот (или в клетку хвоста,
       который в этот же момент уходит);
   значит змейка не может ни врезаться, ни запереть себя — ни сейчас,
   ни через сколько угодно ходов в будущем. Это доказуемо, а не
   эвристика.

3. СРЕЗКИ (скорость)
   Голове разрешено прыгать вперёд по кольцу на любую соседнюю клетку,
   номер которой лежит внутри окна. Инвариант при этом сохраняется.

4. ВЫБОР ЦЕЛИ И ПУТИ
   * Цель — яблоко в окне, ближайшее ПО КОЛЬЦУ. Дорога к нему не
     перепрыгивает ни одно другое яблоко, поэтому змейка никогда не
     оставляет яблоки "за спиной" по своей вине.
   * Путь — кратчайший монотонный путь (BFS по клеткам окна, номера
     строго растут). Это самый короткий из всех путей, которые
     гарантированно безопасны в будущем.
   * Если в окне яблок нет (все они за хвостом), голова идёт по кольцу
     шаг за шагом, не "сжигая" свободное пространство впереди.

5. ВОССТАНОВЛЕНИЕ
   Если тело не удовлетворяет инварианту (например, после ручного
   режима), змейка ходит безопасными ходами, стараясь двигаться по
   кольцу, — через несколько ходов тело выстраивается по кольцу, и
   включается гарантированный режим.
"""

from collections import deque

from pathfinding import flood_fill_distances


Cell = tuple[int, int]


class SnakeAI:

    CYCLE = "CYCLE"          # гарантированный режим
    RECOVERY = "RECOVERY"    # тело ещё не выстроено по кольцу
    FAST = "FAST"            # быстрый безопасный сбор яблок

    # При скольких яблоках (и меньше) голова "рвётся" к хвосту,
    # когда все яблоки оказались позади. Подобрано замерами.
    RUSH_MAX_APPLES = 3

    # Коэффициент опасности: чем ближе к 1, тем теснее и рискованнее
    # позиция. Пока он ниже порога, работает быстрый сбор яблок.
    DANGER_LIMIT = 0.68
    DANGER_FILL_SCALE = 0.40

    # Запас свободных клеток после быстрого хода.
    FAST_SAFETY_MARGIN = 1

    def __init__(self, board):
        self.board = board
        self.width = board.width
        self.height = board.height
        self.total_cells = board.width * board.height

        # Для отображения в UI.
        self.planned_path: list[Cell] = []
        self.mode = self.CYCLE

        # Включать ли быстрый безопасный режим (сбор яблок по BFS).
        # Режим работает, пока коэффициент опасности ниже порога.
        self.fast_enabled = False
        self.danger = 0.0

        # Режим восстановления: план выстраивания и счётчик посещений.
        self._recovery_plan: list[Cell] = []
        self._recovery_visits: dict[Cell, int] = {}
        self._recovery_stall = 0      # ходов без прогресса

        # Соседи каждой клетки — считаем один раз.
        self._neighbors = {
            cell: board.neighbors(cell)
            for cell in board.all_cells()
        }

        self.has_cycle = False
        self.slot_count = 0
        self.direction = 1

        # direction -> (клетка -> номер слота, номер слота -> клетки)
        self._orders: dict[int, tuple[dict, list]] = {}

        self._build_cycle()

    # ================================================================
    # ПОСТРОЕНИЕ КОЛЬЦА
    # ================================================================

    @staticmethod
    def _row_comb(width: int, height: int) -> list[Cell]:
        """
        Гамильтонов цикл для поля с ЧЁТНОЙ высотой:
        "змейка" по строкам в столбцах 1..W-1 и возврат по столбцу 0.
        """
        sequence = []

        for y in range(height):
            if y % 2 == 0:
                xs = range(1, width)
            else:
                xs = range(width - 1, 0, -1)

            sequence.extend((x, y) for x in xs)

        sequence.extend((0, y) for y in range(height - 1, -1, -1))

        return sequence

    def _build_cycle(self) -> None:
        width, height = self.width, self.height

        # На поле шириной или высотой 1 кольца не существует.
        if width < 2 or height < 2:
            return

        alt_pair = None

        if height % 2 == 0:
            sequence = self._row_comb(width, height)

        elif width % 2 == 0:
            # Транспонируем: та же гребёнка, но по столбцам.
            sequence = [
                (x, y)
                for (y, x) in self._row_comb(height, width)
            ]

        else:
            # Оба размера нечётные (минимум 3x3).
            # 1) Цикл по верхней части W x (H-1) — её высота чётная.
            # 2) Нижнюю строку (без правого угла) вставляем "карманами"
            #    по две клетки в рёбра строки H-2:
            #       (x+1, H-2) -> (x, H-2)   превращается в
            #       (x+1, H-2) -> (x+1, H-1) -> (x, H-1) -> (x, H-2)
            base = self._row_comb(width, height - 1)
            last_row = height - 2
            bottom = height - 1

            sequence = []
            for i, cell in enumerate(base):
                sequence.append(cell)
                nxt = base[(i + 1) % len(base)]

                x, y = cell
                if (
                    y == last_row
                    and nxt == (x - 1, last_row)
                    and (x - 1) % 2 == 0
                ):
                    sequence.append((x, bottom))
                    sequence.append((x - 1, bottom))

            corner = (width - 1, height - 1)       # E — вне цикла
            twin = (width - 2, height - 2)         # C — делит с E слот
            alt_pair = (twin, corner)

        slots = [[cell] for cell in sequence]

        if alt_pair:
            twin, corner = alt_pair
            slots[sequence.index(twin)].append(corner)

        self.slot_count = len(slots)
        count = self.slot_count

        # Прямое направление обхода.
        forward_pos = {}
        for index, cells in enumerate(slots):
            for cell in cells:
                forward_pos[cell] = index

        # Обратное направление обхода.
        backward_slots = [None] * count
        backward_pos = {}
        for index, cells in enumerate(slots):
            new_index = (count - index) % count
            backward_slots[new_index] = cells
            for cell in cells:
                backward_pos[cell] = new_index

        self._orders = {
            1: (forward_pos, slots),
            -1: (backward_pos, backward_slots),
        }

        self.has_cycle = self._verify_cycle()

    def _verify_cycle(self) -> bool:
        """Проверка: все клетки покрыты, соседние слоты смежны."""
        pos, slots = self._orders[1]

        if len(pos) != self.total_cells:
            return False

        count = len(slots)
        for index in range(count):
            for a in slots[index]:
                for b in slots[(index + 1) % count]:
                    if abs(a[0] - b[0]) + abs(a[1] - b[1]) != 1:
                        return False

        return True

    @property
    def cycle(self) -> list[Cell]:
        """Кольцо как список клеток (основная клетка каждого слота)."""
        if not self.has_cycle:
            return []
        return [cells[0] for cells in self._orders[self.direction][1]]

    # ================================================================
    # ИНВАРИАНТ
    # ================================================================

    def _ordered_prefix(self, body: list[Cell], pos: dict) -> int:
        """
        Сколько сегментов, начиная с головы, уже выстроены по кольцу:
        от каждого сегмента к более новому — строго вперёд,
        и всё вместе меньше одного оборота.
        """
        count = self.slot_count
        travelled = 0
        ordered = 1

        for i in range(1, len(body)):
            step = (pos[body[i - 1]] - pos[body[i]]) % count

            if step == 0:
                break

            travelled += step
            if travelled >= count:
                break

            ordered += 1

        return ordered

    def _is_ordered(self, body: list[Cell], pos: dict) -> bool:
        """Всё тело выстроено по кольцу — инвариант выполняется."""
        return self._ordered_prefix(body, pos) == len(body)

    def _find_direction(self, body: list[Cell]):
        """Направление обхода кольца, в котором тело упорядочено."""
        for direction in (self.direction, -self.direction):
            if self._is_ordered(body, self._orders[direction][0]):
                return direction
        return None

    # ================================================================
    # БЫСТРЫЙ БЕЗОПАСНЫЙ РЕЖИМ
    # ================================================================

    def _fast_move(self, body: list[Cell], apples: set[Cell]):
        """
        Самый короткий путь до ближайшего яблока, после которого
        змейка сохраняет возможность добраться до хвоста и имеет
        запас свободных клеток.

        Возвращает (первая клетка пути, путь) или None.
        """
        if not apples:
            return None

        head = body[0]
        tail = body[-1]
        body_set = set(body)

        # BFS по свободным клеткам; хвост считается проходимым,
        # потому что он уходит в этот же ход.
        blocked = set(body_set)
        blocked.discard(tail)

        previous = {head: None}
        queue = deque([head])

        while queue:
            current = queue.popleft()
            for neighbor in self._neighbors[current]:
                if neighbor in previous or neighbor in blocked:
                    continue
                previous[neighbor] = current
                queue.append(neighbor)

        candidates = []

        for apple in apples:
            if apple in body_set or apple not in previous:
                continue

            path = []
            cell = apple
            while cell != head:
                path.append(cell)
                cell = previous[cell]
            path.reverse()

            result = self._simulate_fast_path(
                body, path, apples
            )

            if result is None:
                continue

            snake, eaten, free = result

            if apple not in eaten:
                continue

            # При равной длине пути предпочитаем яблоко, рядом
            # с которым есть другие яблоки: это сокращает следующий
            # участок маршрута.
            remaining = [
                other for other in apples
                if other not in eaten and other not in body_set
            ]
            next_distance = min(
                (
                    abs(apple[0] - other[0])
                    + abs(apple[1] - other[1])
                    for other in remaining
                ),
                default=0,
            )

            score = (len(path), next_distance, -free)
            candidates.append((score, path[0], path))

        if not candidates:
            return None

        _, move, path = min(candidates, key=lambda item: item[0])
        return move, path

    def _simulate_fast_path(
        self,
        body: list[Cell],
        path: list[Cell],
        apples: set[Cell],
    ):
        """Проигрывает путь и проверяет безопасность позиции после него."""
        snake = list(body)
        eaten: set[Cell] = set()

        for cell in path:
            eating = cell in apples

            occupied = set(snake)
            if not eating:
                occupied.discard(snake[-1])

            if cell in occupied:
                return None

            snake.insert(0, cell)
            if not eating:
                snake.pop()
            if eating:
                eaten.add(cell)

        # После хода хвост ещё будет двигаться, поэтому он свободен.
        blocked = set(snake[:-1])
        reachable = {snake[0]}
        queue = deque([snake[0]])

        while queue:
            current = queue.popleft()
            for neighbor in self._neighbors[current]:
                if neighbor in reachable or neighbor in blocked:
                    continue
                reachable.add(neighbor)
                queue.append(neighbor)

        if snake[-1] not in reachable:
            return None

        free = len(reachable) - 1
        if free < len(snake) + self.FAST_SAFETY_MARGIN:
            return None

        return snake, eaten, free

    # ================================================================
    # ОЦЕНКА ОПАСНОСТИ
    # ================================================================

    def _board_pressure(self) -> float:
        """
        Поправка на тесноту малого поля. На 5×5–9×9 змейка быстрее
        упирается в собственное тело, поэтому быстрый режим там
        должен уступать кольцу раньше, чем на большом поле.
        """
        total = self.total_cells

        if total <= 36:
            return 0.35
        if total <= 49:
            return 0.25
        if total <= 81:
            return 0.10
        return 0.0

    def _danger_level(self, body: list[Cell]) -> float:
        """
        Коэффициент опасности 0..1.

        Учитывает:
          * долю заполнения поля (главный фактор);
          * поправку на тесноту малого поля;
          * запас свободных клеток относительно длины тела.
        """
        length = len(body)
        fill = length / self.total_cells

        danger = (
            fill / self.DANGER_FILL_SCALE
            + self._board_pressure()
        )

        # Свободная область, доступная из головы. Хвост считаем
        # свободным: он уходит в этот же ход.
        blocked = set(body[:-1])
        reachable = {body[0]}
        queue = deque([body[0]])

        while queue:
            current = queue.popleft()
            for neighbor in self._neighbors[current]:
                if neighbor in reachable or neighbor in blocked:
                    continue
                reachable.add(neighbor)
                queue.append(neighbor)

        free = len(reachable) - 1
        room = free / max(1, length)
        room_risk = 1.0 - min(1.0, room / 2.5)

        return min(1.0, max(danger, room_risk))

    # ================================================================
    # ГЛАВНЫЙ МЕТОД
    # ================================================================

    def choose_move(self, snake_body, apples):
        """
        snake_body — тело (голова первая) или объект с атрибутом body.
        apples     — любая коллекция клеток с яблоками (set, list...).
        Возвращает клетку, в которую нужно пойти, или None.
        """
        if hasattr(snake_body, "body"):
            snake_body = snake_body.body

        body = list(snake_body)
        apples = set(apples or ())

        self.planned_path = []

        if not body:
            return None

        # Историческая версия: только гарантированный обход кольца.
        if self.has_cycle:
            direction = self._find_direction(body)

            if direction is not None:
                self.direction = direction
                move = self._cycle_move(body, apples)

                if move is not None:
                    self.mode = self.CYCLE
                    self._recovery_plan = []
                    self._recovery_visits.clear()
                    self._recovery_stall = 0
                    return move

        self.mode = self.RECOVERY
        return self._recovery_move(body, apples)

    # ================================================================
    # ГАРАНТИРОВАННЫЙ РЕЖИМ
    # ================================================================

    def _cycle_move(self, body: list[Cell], apples: set):
        pos, slots = self._orders[self.direction]
        count = self.slot_count

        head = body[0]
        tail = body[-1]
        length = len(body)
        body_set = set(body)

        head_slot = pos[head]

        def ahead(cell):
            """На сколько слотов клетка впереди головы."""
            return (pos[cell] - head_slot) % count

        # Расстояние до хвоста по кольцу. Окно — слоты 1..tail_ahead-1.
        tail_ahead = ahead(tail) if length > 1 else count

        # ------------------------------------------------------------
        # Последнее яблоко на поле — просто съедаем, это победа.
        # (Нужно для поля с нечётными сторонами: последней свободной
        # клеткой может оказаться "двойник" слота хвоста.)
        # ------------------------------------------------------------
        if length + 1 == self.total_cells:
            for cell in self._neighbors[head]:
                if cell in apples and cell not in body_set:
                    self.planned_path = [cell]
                    return cell

        # ------------------------------------------------------------
        # 1. Яблоки в окне: идём к ближайшему ПО КОЛЬЦУ кратчайшим
        #    монотонным путём.
        # ------------------------------------------------------------
        window_apples = [
            apple for apple in apples
            if apple not in body_set
            and 0 < ahead(apple) < tail_ahead
        ]

        if window_apples:
            target = min(window_apples, key=ahead)
            path = self._monotone_path(
                head, target, ahead(target), ahead, body_set
            )

            if path:
                self.planned_path = path
                return path[0]

        # ------------------------------------------------------------
        # 2. Яблок в окне нет — все они за хвостом. Хвост сам
        #    освобождает место, и через несколько ходов яблоко
        #    окажется в окне. Пока ждём:
        #
        #    * яблок мало  -> "рывок": голова прыгает как можно ближе
        #      к хвосту, чтобы оказаться рядом, когда яблоко
        #      освободится (замеры: до -20% ходов);
        #    * яблок много -> шаг по кольцу: окно остаётся большим,
        #      и новые яблоки чаще появляются впереди.
        #
        #    Исключение: яблоко в сдвоенном слоте, чей "двойник" занят
        #    телом. Рывок мог бы бесконечно держать этот слот занятым
        #    (змейка гонялась бы за хвостом по кругу), а пошаговое
        #    движение гарантированно до него доходит.
        # ------------------------------------------------------------
        if len(apples) <= self.RUSH_MAX_APPLES and not self._twin_blocked(
            apples, pos, slots, body_set
        ):
            options = [
                cell for cell in self._neighbors[head]
                if cell not in body_set and 0 < ahead(cell) < tail_ahead
            ]

            if options:
                move = max(options, key=ahead)
                self.planned_path = [move]
                return move

        next_slot_cells = slots[(head_slot + 1) % count]

        if tail_ahead == 1:
            # Следующий слот — хвост: идём за ним
            # (он сдвинется в этот же ход).
            if tail in next_slot_cells and tail not in apples:
                self.planned_path = [tail]
                return tail
            return None

        free = [cell for cell in next_slot_cells if cell not in body_set]
        if not free:
            return None

        # В сдвоенном слоте предпочитаем клетку с яблоком.
        free.sort(key=lambda cell: cell not in apples)

        self.planned_path = self._preview_cycle(head_slot, tail_ahead, slots)
        return free[0]

    @staticmethod
    def _twin_blocked(apples, pos, slots, body_set) -> bool:
        """Яблоко в сдвоенном слоте, а вторая клетка слота — тело."""
        for apple in apples:
            cells = slots[pos[apple]]
            if len(cells) > 1 and any(
                cell in body_set for cell in cells if cell != apple
            ):
                return True
        return False

    def _monotone_path(self, head, target, target_ahead, ahead, body_set):
        """
        BFS от головы к цели по свободным клеткам окна,
        где номер слота на каждом шаге строго растёт.
        """
        previous = {head: None}
        slot_ahead = {head: 0}
        queue = deque([head])

        while queue:
            current = queue.popleft()

            if current == target:
                break

            current_ahead = slot_ahead[current]

            # Сначала маленькие прыжки: при равной длине пути
            # предпочитаем не "сжигать" окно.
            candidates = []
            for cell in self._neighbors[current]:
                if cell in previous or cell in body_set:
                    continue

                cell_ahead = ahead(cell)
                if current_ahead < cell_ahead <= target_ahead:
                    candidates.append((cell_ahead, cell))

            candidates.sort()

            for cell_ahead, cell in candidates:
                previous[cell] = current
                slot_ahead[cell] = cell_ahead
                queue.append(cell)

        if target not in previous:
            return None

        path = []
        cell = target
        while cell != head:
            path.append(cell)
            cell = previous[cell]
        path.reverse()

        return path

    def _preview_cycle(self, head_slot, tail_ahead, slots, limit=12):
        """Несколько следующих клеток кольца — для отрисовки."""
        count = self.slot_count
        steps = min(limit, max(tail_ahead - 1, 0))
        return [
            slots[(head_slot + i) % count][0]
            for i in range(1, steps + 1)
        ]

    # ================================================================
    # РЕЖИМ ВОССТАНОВЛЕНИЯ
    # ================================================================

    def _recovery_move(self, body: list[Cell], apples: set):
        """
        Тело не выстроено по кольцу (например, после ручного режима).

        1. Если есть сохранённый план выстраивания — продолжаем его.
        2. Ищем новый план (см. _find_alignment) из текущей позиции,
           а если не нашли — после 1-2 пробных безопасных ходов.
        3. Плана нет — делаем безопасный ход по эвристике и пробуем
           снова на следующем ходу (хвост сдвинется, появятся варианты).
        """
        head = body[0]

        # --- 1. Продолжаем план --------------------------------------
        plan = self._recovery_plan
        if plan and plan[0] in self._neighbors[head] and not (
            set(plan) & apples
        ) and plan[0] not in body[:-1]:
            move = plan.pop(0)
            self.planned_path = [move] + plan
            return move

        self._recovery_plan = []

        # --- 2. Ищем план ---------------------------------------------
        if self.has_cycle:
            plan = self._plan_alignment(body, apples)
            if plan:
                self._recovery_plan = plan[1:]
                self.planned_path = plan
                return plan[0]

        # --- 3. Эвристика ---------------------------------------------
        return self._heuristic_move(body, apples)

    # ----------------------------------------------------------------

    def _plan_alignment(self, body, apples, depth=2):
        """План выстраивания: сразу или после depth пробных ходов."""
        plan = self._find_alignment(body, apples)
        if plan or depth == 0:
            return plan

        for cell in self._neighbors[body[0]]:
            if cell in apples or cell in body[:-1]:
                continue

            new_body = [cell] + body[:-1]
            if not self._can_escape(new_body, apples):
                continue

            rest = self._plan_alignment(new_body, apples, depth - 1)
            if rest:
                return [cell] + rest

        return None

    def _find_alignment(self, body, apples):
        """
        Ищет последовательность ходов "строго вперёд по кольцу",
        после которой всё тело окажется выстроенным.

        Если от головы уже выстроено p сегментов, нужно ещё
        len - p таких ходов. Клетка тела с индексом i (0 = голова)
        освобождается через len - i ходов; яблоки обходим (без еды
        новые яблоки не появляются, и план выполняется точно).

        Поиск идёт по слоям-ходам: в слое t хранятся клетки, где
        голова может оказаться через t ходов. Благодаря монотонности
        номеров слотов слоёв не больше длины змейки.
        """
        length = len(body)
        count = self.slot_count

        release = {
            cell: length - index
            for index, cell in enumerate(body)
        }

        best = None

        for pos, _ in self._orders.values():
            prefix = self._ordered_prefix(body, pos)
            steps_needed = length - prefix

            # Уже пройденная выстроенной частью дистанция по кольцу.
            span = (pos[body[0]] - pos[body[prefix - 1]]) % count
            budget = count - 1 - span

            head_slot = pos[body[0]]

            def ahead(cell):
                return (pos[cell] - head_slot) % count

            if best is not None and steps_needed >= len(best):
                continue

            layer = {body[0]: None}
            parents = []

            for step in range(1, steps_needed + 1):
                nxt_layer = {}

                for cell in layer:
                    cell_ahead = ahead(cell) if step > 1 else 0

                    for nxt in self._neighbors[cell]:
                        if nxt in nxt_layer or nxt in apples:
                            continue

                        nxt_ahead = ahead(nxt)
                        if not (cell_ahead < nxt_ahead <= budget):
                            continue

                        if release.get(nxt, 0) > step:
                            continue          # ещё занята телом

                        nxt_layer[nxt] = cell

                if not nxt_layer:
                    break

                parents.append(nxt_layer)
                layer = nxt_layer

            else:
                # Восстанавливаем путь от любой клетки последнего слоя.
                cell = next(iter(layer))
                path = []
                for step_layer in reversed(parents):
                    path.append(cell)
                    cell = step_layer[cell]
                path.reverse()

                if path and (best is None or len(path) < len(best)):
                    best = path

        return best

    def _heuristic_move(self, body: list[Cell], apples: set):
        """
        Плана нет: выбираем безопасный ход, по возможности без еды,
        наращивающий выстроенную часть тела и не крутящийся на месте.

        Если прогресса долго нет (например, все свободные клетки
        заняты яблоками и змейка просто ходит за хвостом), разрешаем
        есть: позиция меняется, и появляется шанс выстроиться.
        """
        head = body[0]

        self._recovery_stall += 1
        stalled = self._recovery_stall > 2 * len(body) + 10

        best = None
        best_score = None

        for cell in self._neighbors[head]:
            eating = cell in apples
            remaining = body if eating else body[:-1]

            if cell in remaining:
                continue                           # столкновение

            new_body = [cell] + remaining

            if len(new_body) == self.total_cells:
                return cell                        # победа

            prefix = 0
            if self.has_cycle:
                prefix = max(
                    self._ordered_prefix(new_body, pos)
                    for pos, _ in self._orders.values()
                )

            safe = self._can_escape(
                new_body, apples - {cell}, margin=int(eating)
            )

            score = (
                safe,
                eating if stalled else not eating,
                -self._recovery_visits.get(cell, 0),   # против петель
                prefix,
                self._free_area(new_body),
            )

            if best_score is None or score > best_score:
                best_score = score
                best = cell

        if best is not None:
            if best in apples:
                self._recovery_stall = 0
                self._recovery_visits.clear()

            self.planned_path = [best]
            self._recovery_visits[best] = (
                self._recovery_visits.get(best, 0) + 1
            )

        return best

    def _can_escape(
        self, body: list[Cell], apples: set, margin: int = 0
    ) -> bool:
        """
        Сможет ли голова выжить: BFS по времени.

        Сегмент тела i (0 = голова) освобождает клетку через len - i
        ходов. Каждое яблоко на пути считаем за 2 хода задержки:
        хвост стоит на месте, а новое яблоко может появиться на пути. Если голова успевает добраться до клетки сегмента
        к моменту его ухода, дальше можно бесконечно идти "по следу"
        хвоста — значит, позиция не тупиковая.

        margin — запас в ходах (после еды появится новое яблоко,
        и оно может лечь на путь).
        """
        length = len(body)
        head = body[0]

        free_at = {
            cell: length - index
            for index, cell in enumerate(body)
        }

        # Новое яблоко появляется только если есть свободная клетка
        # без яблока. Если её нет — за яблоко только 1 ход задержки.
        spawnable = self.total_cells - length - len(apples) > 0
        apple_delay = 2 if spawnable else 1
        if not spawnable:
            margin = 0

        # Состояние: (клетка, накопленная задержка из-за яблок).
        max_delay = apple_delay * len(apples)
        visited = {(head, 0)}
        queue = deque([(head, 0, 0)])

        while queue:
            cell, time, eaten = queue.popleft()

            for nxt in self._neighbors[cell]:
                release = free_at.get(nxt)

                if release is not None:
                    if time + 1 >= release + eaten + margin:
                        return True
                    continue

                grown = min(eaten + apple_delay * (nxt in apples), max_delay)
                if (nxt, grown) in visited:
                    continue

                visited.add((nxt, grown))
                queue.append((nxt, time + 1, grown))

        return False

    def _free_area(self, body: list[Cell]) -> int:
        blocked = set(body[1:])
        return len(flood_fill_distances(self.board, body[0], blocked))
