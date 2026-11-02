#!/usr/bin/env python3
"""Simulación local inspirada en La vida de las hormigas."""
import json
import math
import os
import random
import shutil
import subprocess
import tempfile
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

WIDTH, HEIGHT = 960, 620
WORLD_WIDTH, WORLD_HEIGHT = 2400, 1600
FRAME_SECONDS = 1 / 60
# Cambia a False para permitir que las hormigas caminen y se agrupen juntas.
ANTS_SPREAD_OUT = True
# Muestra las barras de vida sobre hormigas, enemigos y nidos rivales.
SHOW_HEALTH_BARS = False
# Muestra las barras de alimento sobre los insectos muertos.
SHOW_FOOD_BARS = False
ANT_SPACING = 16
SAVE = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'vida-hormigas-local' / 'partida.json'
SETTINGS = SAVE.with_name('ajustes.json')
COSTS = {'obrera': 15, 'soldado': 25, 'universal': 30}
COLORS = {'obrera': '#34231b', 'soldado': '#9a3f31', 'universal': '#74513c'}
INSECTS = ('mariposa', 'libélula', 'abeja', 'saltamontes', 'cigarra', 'mosca')
ENEMY_TYPES = {'araña': (55, 10, 37, '#463a4a'), 'mantis': (85, 14, 32, '#527442'),
               'avispón': (70, 12, 46, '#b98b31')}
AUDIO_DIR = Path(__file__).resolve().parent / 'audio'
IMAGE_DIR = Path(__file__).resolve().parent / 'imagenes'


def load_ant_sprites():
    if Image is None:
        return {}
    try:
        atlas = Image.open(IMAGE_DIR / 'pack-0.png').convert('RGBA')
        entries = (IMAGE_DIR / 'pack.atlas').read_text(encoding='utf-8').splitlines()
        locations = {}
        for index, line in enumerate(entries):
            if line.startswith('ant') and index + 2 < len(entries) and entries[index + 2].strip().startswith('xy:'):
                locations[line] = tuple(map(int, entries[index + 2].split(':', 1)[1].split(',')))
        result = {}
        for role, name in (('obrera', 'Worker'), ('soldado', 'Soldier'), ('universal', 'Universal')):
            for direction in ('right', 'left', 'up', 'down'):
                for carrying in (False, True):
                    orientation = 'side' if direction in ('left', 'right') else 'up'
                    action = 'food' if carrying and role != 'soldado' else 'move'
                    key = f'ant{name}_{orientation}_{action}'
                    if key not in locations:
                        continue
                    x, y = locations[key]
                    frames = []
                    for frame in range(4):
                        img = atlas.crop((x + frame * 20, y, x + (frame + 1) * 20, y + 20))
                        # The atlas's side frames face left; its vertical frames face down.
                        if direction == 'right':
                            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                        elif direction == 'up':
                            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
                        frames.append(ImageTk.PhotoImage(img))
                    result[(role, direction, carrying)] = frames
        return result
    except (OSError, ValueError, IndexError):
        return {}


def load_insect_sprites():
    if Image is None:
        return {}
    try:
        atlas = Image.open(IMAGE_DIR / 'pack-0.png').convert('RGBA')
        lines = (IMAGE_DIR / 'pack.atlas').read_text(encoding='utf-8').splitlines()
        entries = {}
        for index, line in enumerate(lines):
            if not line or line.startswith(' ') or index + 3 >= len(lines):
                continue
            if lines[index + 2].strip().startswith('xy:') and lines[index + 3].strip().startswith('size:'):
                xy = tuple(map(int, lines[index + 2].split(':', 1)[1].split(',')))
                size = tuple(map(int, lines[index + 3].split(':', 1)[1].split(',')))
                entries[line] = (*xy, *size)
        names = {'mariposa': 'tehu_blue_dead', 'libélula': 'tonbo_dead', 'abeja': 'bee_dead',
                 'saltamontes': 'grasshopper_dead', 'cigarra': 'cicada_dead', 'mosca': 'fly_dead',
                 'araña': 'spider_dead', 'mantis': 'mantis_dead', 'avispón': 'hornet_dead',
                 'hormiga': 'antWorker_dead', 'insecto': 'fly_dead'}
        result = {}
        if 'colony' in entries:
            x, y, w, h = entries['colony']
            img = atlas.crop((x, y, x+w, y+h))
            img.thumbnail((50, 50), Image.Resampling.LANCZOS)
            result[('nest', 'colony')] = [ImageTk.PhotoImage(img)]
        for kind, name in names.items():
            if name in entries:
                x, y, w, h = entries[name]
                img = atlas.crop((x, y, x+w, y+h))
                img.thumbnail((42, 30), Image.Resampling.LANCZOS)
                result[('food', kind)] = [ImageTk.PhotoImage(img)]
        for kind, name in {'araña': 'spider_side', 'mantis': 'mantis_side_move', 'avispón': 'hornet_side_move'}.items():
            if name in entries:
                x, y, w, h = entries[name]
                frame_width = w // 4
                frames = []
                for frame in range(4):
                    img = atlas.crop((x + frame * frame_width, y, x + (frame + 1) * frame_width, y + h))
                    img.thumbnail((50, 38), Image.Resampling.LANCZOS)
                    frames.append(ImageTk.PhotoImage(img))
                result[('enemy', kind)] = frames
        return result
    except (OSError, ValueError, IndexError):
        return {}


class Audio:
    def __init__(self):
        self.enabled = True
        self.music_enabled = False
        self.music = None
        self.sounds = []
        self.last = 0
        self.load_settings()
        if self.music_enabled:
            self.start_music()

    def load_settings(self):
        try:
            with SETTINGS.open(encoding='utf-8') as file:
                settings = json.load(file)
            if isinstance(settings.get('effects'), bool):
                self.enabled = settings['effects']
            if isinstance(settings.get('music'), bool):
                self.music_enabled = settings['music']
        except (OSError, ValueError, AttributeError):
            pass

    def save_settings(self):
        try:
            SETTINGS.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=SETTINGS.parent, delete=False) as file:
                json.dump({'effects': self.enabled, 'music': self.music_enabled}, file)
                path = file.name
            os.replace(path, SETTINGS)
        except OSError as error:
            print(f'No se pudieron guardar los ajustes de audio: {error}')

    def play(self, name):
        player = shutil.which('paplay')
        self.sounds = [process for process in self.sounds if process.poll() is None]
        if not self.enabled or not player or len(self.sounds) >= 3 or time.monotonic() - self.last < .12:
            return
        try:
            self.sounds.append(subprocess.Popen([player, str(AUDIO_DIR / name)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            self.last = time.monotonic()
        except OSError:
            pass

    def start_music(self):
        player = shutil.which('ffplay')
        if not player:
            return False
        try:
            self.music = subprocess.Popen([player, '-nodisp', '-autoexit', '-loop', '0', '-volume', '25',
                                           str(AUDIO_DIR / 't_midi067_town18.mp3')],
                                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except OSError:
            return False

    def toggle_music(self):
        if self.music_enabled:
            if self.music and self.music.poll() is None:
                self.music.terminate()
            self.music = None
            self.music_enabled = False
        elif self.start_music():
            self.music_enabled = True
        else:
            return None
        self.save_settings()
        return self.music_enabled

    def close(self):
        for process in self.sounds + ([self.music] if self.music else []):
            if process.poll() is None:
                process.terminate()


def distance(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y'])


def distance_squared(a, b):
    dx, dy = a['x'] - b['x'], a['y'] - b['y']
    return dx * dx + dy * dy


class SpatialIndex:
    def __init__(self, entities, cell_size=200):
        self.cell_size = cell_size
        self.cells = {}
        for entity in entities:
            cell = (int(entity['x'] // cell_size), int(entity['y'] // cell_size))
            self.cells.setdefault(cell, []).append(entity)

    def nearby(self, entity, radius):
        size = self.cell_size
        x, y = entity['x'], entity['y']
        for cx in range(int((x - radius) // size), int((x + radius) // size) + 1):
            for cy in range(int((y - radius) // size), int((y + radius) // size) + 1):
                for candidate in self.cells.get((cx, cy), ()):
                    if distance_squared(entity, candidate) < radius * radius:
                        yield candidate


class Colony:
    def __init__(self):
        self.food = 90
        self.nests = [{'x': 120, 'y': 510}]
        self.ants = []
        self.sources = []
        self.enemies = []
        self.enemy_nest = {'x': 835, 'y': 110, 'hp': 600, 'max_hp': 600}
        self.extra_enemy_nests = []
        self.difficulty_version = 2
        self.attack = False
        self.level = 1
        self.victories = 0
        self.events = []
        self.speed = 1
        self.spawn_timer = 0.0
        self.food_timer = 0.0
        for _ in range(7):
            self.add_source(random.randint(190, 850), random.randint(120, 520))
        for _ in range(10):
            self.add_source()

    def add_source(self, x=None, y=None, amount=None, kind=None):
        amount = random.randint(25, 50) if amount is None else amount
        self.sources.append({'x': random.randint(30, WORLD_WIDTH - 30) if x is None else x,
                             'y': random.randint(30, WORLD_HEIGHT - 30) if y is None else y,
                             'amount': amount, 'max_amount': amount, 'kind': kind or random.choice(INSECTS)})

    def make_ant(self, kind, nest=None):
        if self.food < COSTS[kind]:
            return False
        self.food -= COSTS[kind]
        if nest is None:
            nest = self.nests[0]
        self.ants.append({'x': nest['x'], 'y': nest['y'], 'kind': kind,
                          'hp': 55 if kind == 'soldado' else 35, 'carry': 0, 'cooldown': 0})
        return True

    def next_enemy_nest(self):
        self.victories += 1
        self.level = self.victories + 1
        self.food += 40
        health = 600 + self.victories * 250
        self.enemy_nest = {'x': random.randint(600, WORLD_WIDTH - 100),
                           'y': random.randint(100, WORLD_HEIGHT - 100),
                           'hp': health, 'max_hp': health}
        self.attack = False
        self.events.append(('victory', 'Colonia derrotada. Nueva colonia rival disponible; recompensa: 40 alimentos.'))

    def enemy_nests(self):
        return [nest for nest in [self.enemy_nest, *self.extra_enemy_nests] if nest['hp'] > 0]

    def spawn_enemy(self, kind, nest, spread=0):
        x = max(15, min(WORLD_WIDTH - 15, nest['x'] + random.randint(-spread, spread)))
        y = max(15, min(WORLD_HEIGHT - 15, nest['y'] + random.randint(-spread, spread)))
        self.enemies.append({'x': x, 'y': y, 'kind': kind, 'hp': ENEMY_TYPES[kind][0], 'cooldown': 0})

    @staticmethod
    def move(entity, target, speed, dt):
        dx, dy = target['x'] - entity['x'], target['y'] - entity['y']
        remaining = speed * dt
        # Travel along one axis at a time; carry any leftover distance to the other.
        for axis, delta in (('x', dx), ('y', dy)):
            step = min(abs(delta), remaining)
            if step:
                entity[axis] += math.copysign(step, delta)
                entity['direction'] = ('right' if delta > 0 else 'left') if axis == 'x' else ('down' if delta > 0 else 'up')
                remaining -= step
            if remaining <= 0:
                break

    def update(self, dt):
        self.spawn_timer += dt
        self.food_timer += dt
        if self.food_timer >= 6:
            self.food_timer = 0
            gatherers = sum(ant['kind'] in ('obrera', 'universal') for ant in self.ants)
            limit = min(250, 40 + gatherers * 3)
            batch = min(30, 3 + gatherers // 2)
            for _ in range(min(batch, max(0, limit - len(self.sources)))):
                nest = random.choice(self.nests)
                x = max(30, min(WORLD_WIDTH - 30, nest['x'] + random.randint(-350, 350)))
                y = max(30, min(WORLD_HEIGHT - 30, nest['y'] + random.randint(-300, 300)))
                self.add_source(x, y)
        if self.spawn_timer >= 8:
            self.spawn_timer = 0
            nests = self.enemy_nests()
            enemy_limit = min(200, 60 + self.victories * 10 + 20 * max(0, len(nests) - 1))
            batch = min(12, 6 + self.victories)
            for nest in nests:
                for _ in range(min(batch, max(0, enemy_limit - len(self.enemies)))):
                    self.spawn_enemy(random.choice(list(ENEMY_TYPES)), nest, spread=65)
        enemy_index = SpatialIndex(self.enemies)
        for ant in self.ants[:]:
            ant['cooldown'] = max(0, ant['cooldown'] - dt)
            enemy = (min(enemy_index.nearby(ant, 120), key=lambda e: distance_squared(ant, e), default=None)
                     if ant['kind'] != 'obrera' else None)
            if enemy is not None:
                self.move(ant, enemy, 54, dt)
                if distance(ant, enemy) < 15 and ant['cooldown'] <= 0:
                    enemy['hp'] -= 12 if ant['kind'] == 'soldado' else 7
                    ant['cooldown'] = .55
                    self.events.append(('hit', ''))
                continue
            if ant['kind'] != 'obrera' and self.attack and self.enemy_nests():
                nest = min(self.enemy_nests(), key=lambda candidate: distance(ant, candidate))
                self.move(ant, nest, 54, dt)
                if distance(ant, nest) < 22 and ant['cooldown'] <= 0:
                    nest['hp'] = max(0, nest['hp'] - (12 if ant['kind'] == 'soldado' else 7))
                    ant['cooldown'] = .55
                    if nest['hp'] == 0:
                        if nest is self.enemy_nest:
                            self.next_enemy_nest()
                        else:
                            self.extra_enemy_nests.remove(nest)
                            self.food += 40
                            self.events.append(('victory', 'Nido rival derrotado; recompensa: 40 alimentos.'))
                continue
            if ant['kind'] == 'soldado':
                if self.enemies:
                    enemy = min(self.enemies, key=lambda e: distance_squared(ant, e))
                    self.move(ant, enemy, 54, dt)
                else:
                    # Patrol near the closest nest until an enemy appears.
                    target = ant.get('patrol')
                    if target is None or distance(ant, target) < 5:
                        nest = min(self.nests, key=lambda n: distance(ant, n))
                        target = {'x': max(15, min(WORLD_WIDTH - 15, nest['x'] + random.randint(-130, 130))),
                                  'y': max(15, min(WORLD_HEIGHT - 15, nest['y'] + random.randint(-130, 130)))}
                        ant['patrol'] = target
                    self.move(ant, target, 45, dt)
                continue
            if ant['carry']:
                nest = min(self.nests, key=lambda n: distance(ant, n))
                self.move(ant, nest, 60, dt)
                if distance(ant, nest) < 16:
                    self.food += ant['carry']
                    ant['carry'] = 0
            elif ant['kind'] != 'soldado' and self.sources:
                source = min(self.sources, key=lambda s: distance_squared(ant, s))
                self.move(ant, source, 62 if ant['kind'] == 'obrera' else 48, dt)
                if distance(ant, source) < 10:
                    amount = min(source['amount'], 3 if ant['kind'] == 'obrera' else 2)
                    source['amount'] -= amount
                    ant['carry'] = amount
                    if source['amount'] <= 0:
                        self.sources.remove(source)
        ant_index = SpatialIndex(self.ants)
        for enemy in self.enemies[:]:
            if enemy['hp'] <= 0:
                self.add_source(enemy['x'], enemy['y'], 22, enemy.get('kind', 'araña'))
                self.enemies.remove(enemy)
                continue
            enemy['cooldown'] = max(0, enemy['cooldown'] - dt)
            ant = min((candidate for candidate in ant_index.nearby(enemy, 200) if candidate['hp'] > 0),
                      key=lambda a: distance_squared(a, enemy), default=None)
            if ant:
                    stats = ENEMY_TYPES.get(enemy.get('kind', 'araña'), ENEMY_TYPES['araña'])
                    self.move(enemy, ant, stats[2], dt)
                    if distance(enemy, ant) < 14 and enemy['cooldown'] <= 0:
                        ant['hp'] -= stats[1]
                        enemy['cooldown'] = .9
                        if ant['hp'] <= 0:
                            self.ants.remove(ant)
                            self.add_source(ant['x'], ant['y'], 8, 'hormiga')
            else:
                target = enemy.get('wander')
                if target is None or distance(enemy, target) < 5:
                    target = {'x': max(15, min(WORLD_WIDTH - 15, enemy['x'] + random.randint(-250, 250))),
                              'y': max(15, min(WORLD_HEIGHT - 15, enemy['y'] + random.randint(-250, 250)))}
                    enemy['wander'] = target
                self.move(enemy, target, ENEMY_TYPES.get(enemy.get('kind', 'araña'), ENEMY_TYPES['araña'])[2] * .6, dt)
        if ANTS_SPREAD_OUT:
            self.separate_ants(dt)

    def separate_ants(self, dt):
        """Gently separate nearby ants without changing their targets."""
        cells = {}
        step_limit = 35 * dt
        for ant in self.ants:
            cell_x = int(ant['x'] // ANT_SPACING)
            cell_y = int(ant['y'] // ANT_SPACING)
            for cx in range(cell_x - 1, cell_x + 2):
                for cy in range(cell_y - 1, cell_y + 2):
                    for other in cells.get((cx, cy), ()):
                        dx, dy = ant['x'] - other['x'], ant['y'] - other['y']
                        if abs(dx) >= ANT_SPACING or abs(dy) >= ANT_SPACING:
                            continue
                        if dx * dx + dy * dy >= ANT_SPACING ** 2:
                            continue
                        if abs(dx) >= abs(dy):
                            shift = min(step_limit, (ANT_SPACING - abs(dx)) / 2)
                            sign = 1 if dx >= 0 else -1
                            ant['x'] = max(0, min(WORLD_WIDTH, ant['x'] + sign * shift))
                            other['x'] = max(0, min(WORLD_WIDTH, other['x'] - sign * shift))
                        else:
                            shift = min(step_limit, (ANT_SPACING - abs(dy)) / 2)
                            sign = 1 if dy >= 0 else -1
                            ant['y'] = max(0, min(WORLD_HEIGHT, ant['y'] + sign * shift))
                            other['y'] = max(0, min(WORLD_HEIGHT, other['y'] - sign * shift))
            cell = (int(ant['x'] // ANT_SPACING), int(ant['y'] // ANT_SPACING))
            cells.setdefault(cell, []).append(ant)

    def save(self, destination=SAVE):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=destination.parent, delete=False) as file:
            json.dump({key: value for key, value in vars(self).items() if key != 'events'}, file)
            path = file.name
        os.replace(path, destination)

    @classmethod
    def load(cls, source=SAVE, strict=False):
        colony = cls()
        try:
            with Path(source).open(encoding='utf-8') as file:
                state = json.load(file)
            if not isinstance(state, dict) or not all(key in state for key in ('food', 'nests', 'ants', 'sources', 'enemies', 'enemy_nest')):
                raise ValueError('El archivo no contiene una partida válida')
            for key in vars(colony):
                if key in state:
                    setattr(colony, key, state[key])
            if state.get('difficulty_version', 1) < 2:
                nest = colony.enemy_nest
                old_max = nest.get('max_hp', 100 + colony.victories * 30)
                new_max = 600 + colony.victories * 250
                nest['hp'] = round(new_max * max(0, min(1, nest['hp'] / max(1, old_max))))
                nest['max_hp'] = new_max
                colony.difficulty_version = 2
            for source in colony.sources:
                source.setdefault('max_amount', source['amount'])
                source.setdefault('kind', 'insecto')
            colony.enemy_nest.setdefault('max_hp', 100)
        except FileNotFoundError:
            if strict:
                raise
        except (OSError, ValueError, TypeError) as error:
            if strict:
                raise
            print(f'No se pudo cargar la partida: {error}')
        return colony


class Game:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('La vida de las hormigas · local')
        self.root.configure(bg='#272d24')
        self.colony = Colony.load()
        self.audio = Audio()
        self.mode = None
        self.build_pointer = None
        self.selected = None
        self.camera_x = 0
        self.camera_y = 0
        self.zoom_levels = ((1, 1), (3, 2), (2, 1), (3, 1))
        self.zoom_index = 0
        self.scaled_images = {}
        self.drag_origin = None
        self.dragged = False
        self.dragging_minimap = False
        self.paused = False
        for speed in (1, 2, 3):
            self.root.bind(str(speed), lambda event, value=speed: self.set_speed(value))
        bar = tk.Frame(self.root, bg='#272d24', padx=8, pady=8)
        bar.pack(fill='x')
        self.info = tk.Label(bar, bg='#272d24', fg='#f5efdc', font=('Arial', 12, 'bold'))
        self.info.pack(side='left', padx=8)
        for label, command in [('Atacar nido', self.attack), ('Pausa', self.pause),
                               ('Nueva partida', self.new_game)]:
            tk.Button(bar, text=label, command=command, padx=5).pack(side='left', padx=3)
        options = tk.Frame(self.root, bg='#364337', padx=8, pady=3)
        options.pack(fill='x')
        for label, command in [('Reembolsar hormiga', self.refund_ant), ('Destruir colonia', self.remove_nest),
                               ('Guardar como', self.save_as), ('Cargar', self.load_from),
                               ('Sonido', self.toggle_sound), ('Música', self.toggle_music), ('Ayuda', self.help)]:
            tk.Button(options, text=label, command=command).pack(side='left', padx=3)
        self.status = tk.Label(self.root, text='Crea obreras para recolectar alimento. Las unidades combaten automáticamente.', bg='#272d24', fg='#e2ddc8', pady=7)
        self.status.pack(side='bottom', fill='x')
        main = tk.Frame(self.root, bg='#272d24')
        main.pack(fill='both', expand=True)
        sidebar = tk.Frame(main, bg='#364337', padx=10, pady=12)
        sidebar.pack(side='left', fill='y')
        detail_box = tk.LabelFrame(sidebar, text='Información', bg='#2c392f', fg='#c5d2bd',
                                  font=('Arial', 9, 'bold'), padx=10, pady=10)
        detail_box.pack(side='bottom', fill='x', pady=(12, 0))
        portrait_frame = tk.Frame(detail_box, bg='#2c392f', width=165, height=110)
        portrait_frame.pack(fill='x')
        portrait_frame.pack_propagate(False)
        self.portrait = tk.Label(portrait_frame, bg='#2c392f')
        self.portrait.pack(fill='both', expand=True)
        self.detail_title = tk.Label(detail_box, text='Sin selección', bg='#2c392f', fg='#fff7e7',
                                     font=('Arial', 13, 'bold'), justify='left', anchor='w', wraplength=165)
        self.detail_title.pack(fill='x', pady=(5, 8))
        self.details = tk.Label(detail_box, text='Selecciona una entidad.', bg='#2c392f', fg='#e8ca83',
                                font=('Arial', 10, 'bold'), justify='left', anchor='nw', wraplength=165)
        self.details.pack(fill='x')
        self.detail_description = tk.Label(detail_box, bg='#2c392f', fg='#c5d2bd', font=('Arial', 10),
                                           justify='left', anchor='nw', wraplength=165)
        self.detail_description.pack(fill='x', pady=(8, 0))
        self.portrait_cache = {}
        tk.Label(sidebar, text='CONSTRUCCIÓN', bg='#364337', fg='#f4eedb', font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 10))
        for label, kind in [('Obrera · 15', 'obrera'), ('Soldado · 25', 'soldado'), ('Universal · 30', 'universal')]:
            button = tk.Button(sidebar, text=label, padx=8, pady=4)
            button.pack(fill='x', pady=3)
            button.bind('<ButtonRelease-1>', lambda event, role=kind: self.produce_click(event, role))
        tk.Button(sidebar, text='Construir colonia · 80', command=self.build_mode, padx=8, pady=4).pack(fill='x', pady=(12, 3))
        tk.Button(sidebar, text='Crear nido enemigo', command=self.build_enemy_mode, padx=8, pady=4).pack(fill='x', pady=3)
        tk.Label(sidebar, text='Shift + clic: crear 10', bg='#364337', fg='#c4ceba', font=('Arial', 9)).pack(anchor='w', pady=10)
        self.enemy_controls = tk.Frame(sidebar, bg='#364337')
        tk.Label(self.enemy_controls, text='CREAR ENEMIGOS · GRATIS', bg='#364337', fg='#f4eedb', font=('Arial', 9, 'bold')).pack(anchor='w')
        for kind in ENEMY_TYPES:
            button = tk.Button(self.enemy_controls, text=kind.capitalize())
            button.pack(fill='x', pady=2)
            button.bind('<ButtonRelease-1>', lambda event, enemy_kind=kind: self.create_enemy_click(event, enemy_kind))
        self.canvas = tk.Canvas(main, width=WIDTH, height=HEIGHT, bg='#a6b77e', highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True)
        self.ant_sprites = load_ant_sprites()
        self.insect_sprites = load_insect_sprites()
        nest_frames = self.insect_sprites.get(('nest', 'colony'))
        self.nest_image = None
        if nest_frames:
            self.nest_image = tk.PhotoImage(master=self.root)
            self.nest_image.tk.call(str(self.nest_image), 'copy', str(nest_frames[0]), '-zoom', 2, 2)
        self.canvas.bind('<ButtonPress-1>', self.start_drag)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.canvas.bind('<Motion>', self.track_build_pointer)
        self.canvas.bind('<Leave>', lambda event: self.clear_build_pointer())
        self.root.bind('<Escape>', self.cancel_build)
        self.canvas.bind('<MouseWheel>', self.zoom_wheel)
        self.canvas.bind('<Button-4>', self.zoom_wheel)
        self.canvas.bind('<Button-5>', self.zoom_wheel)
        for key, delta in (('Left', (-100, 0)), ('Right', (100, 0)), ('Up', (0, -100)), ('Down', (0, 100))):
            self.root.bind(f'<{key}>', lambda event, d=delta: self.move_camera(*d))
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.last = time.monotonic()
        self.next_frame = self.last
        self.last_save = self.last
        self.tick()
        self.root.mainloop()

    def produce_click(self, event, kind):
        if 0 <= event.x < event.widget.winfo_width() and 0 <= event.y < event.widget.winfo_height():
            self.produce(kind, 10 if event.state & 0x0001 else 1)

    def produce(self, kind, count=1):
        cost = COSTS[kind] * count
        if self.colony.food < cost:
            self.status.config(text=f'No hay alimento suficiente: necesitas {cost}.')
            return
        nest = self.selected[1] if self.selected and self.selected[0] == 'nido propio' else self.colony.nests[0]
        for _ in range(count):
            self.colony.make_ant(kind, nest)
        self.status.config(text=f'Creadas {count} hormiga(s) de tipo {kind}.')
        self.audio.play('cursor.wav')

    def refund_ant(self):
        if not self.selected or self.selected[0] != 'hormiga':
            self.status.config(text='Selecciona primero una hormiga para reembolsarla.')
            return
        ant = self.selected[1]
        refund = COSTS[ant['kind']] // 2
        if messagebox.askyesno('Reembolsar', f'¿Convertir la hormiga en {refund} de alimento?'):
            self.colony.ants.remove(ant)
            self.colony.food += refund
            self.selected = None
            self.update_details()

    def remove_nest(self):
        if not self.selected or self.selected[0] != 'nido propio':
            self.status.config(text='Selecciona primero una colonia propia.')
            return
        if len(self.colony.nests) <= 1:
            self.status.config(text='Debe quedar al menos una colonia.')
            return
        if messagebox.askyesno('Destruir colonia', '¿Destruir esta colonia y recuperar 40 de alimento?'):
            self.colony.nests.remove(self.selected[1])
            self.colony.food += 40
            self.selected = None
            self.update_details()

    def save_as(self):
        path = filedialog.asksaveasfilename(title='Guardar partida', defaultextension='.json', filetypes=[('Partida JSON', '*.json')])
        if path:
            try:
                self.colony.save(path)
                self.status.config(text='Partida guardada.')
            except OSError as error:
                messagebox.showerror('Error al guardar', str(error))

    def load_from(self):
        path = filedialog.askopenfilename(title='Cargar partida', filetypes=[('Partida JSON', '*.json')])
        if path:
            try:
                loaded = Colony.load(path, strict=True)
            except (OSError, ValueError, TypeError, KeyError) as error:
                messagebox.showerror('Error al cargar', str(error))
                return
            self.colony = loaded
            self.selected = None
            self.update_details()
            self.status.config(text='Partida cargada.')

    def toggle_sound(self):
        self.audio.enabled = not self.audio.enabled
        self.audio.save_settings()
        self.status.config(text='Efectos activados.' if self.audio.enabled else 'Efectos desactivados.')

    def toggle_music(self):
        playing = self.audio.toggle_music()
        self.status.config(text='Música activada.' if playing else ('Música desactivada.' if playing is False else 'No se encontró ffplay.'))

    def help(self):
        messagebox.showinfo('Cómo jugar', 'Crea obreras para recoger alimento y soldados para combatir.\n\nArrastra el mapa o usa las flechas; el minimapa permite navegar.\n\nSelecciona entidades para ver su información. Construye colonias y ataca el nido rival para avanzar.\n\nUsa 1, 2 y 3 para cambiar la velocidad.')

    def build_mode(self):
        self.mode = 'build'
        self.build_pointer = None
        self.canvas.config(cursor='crosshair')
        self.status.config(text='Haz clic para construir una colonia (80 de alimento). Escape cancela.')

    def build_enemy_mode(self):
        self.mode = 'build_enemy'
        self.build_pointer = None
        self.canvas.config(cursor='crosshair')
        self.status.config(text='Haz clic para crear un nido enemigo gratis. Escape cancela.')

    def create_enemy_click(self, event, kind):
        if not (0 <= event.x < event.widget.winfo_width() and 0 <= event.y < event.widget.winfo_height()):
            return
        if not self.selected or self.selected[0] != 'nido rival':
            self.status.config(text='Selecciona primero un nido enemigo.')
            return
        count = 10 if event.state & 0x0001 else 1
        for _ in range(count):
            self.colony.spawn_enemy(kind, self.selected[1], spread=12)
        self.status.config(text=f'Creados {count} enemigo(s): {kind}.')

    def track_build_pointer(self, event):
        if self.mode in ('build', 'build_enemy'):
            self.build_pointer = self.screen_point(event)

    def clear_build_pointer(self):
        self.build_pointer = None

    def cancel_build(self, event=None):
        if self.mode in ('build', 'build_enemy'):
            self.mode = None
            self.build_pointer = None
            self.canvas.config(cursor='')
            self.status.config(text='Construcción cancelada.')

    def move_camera(self, dx, dy):
        zoom = self.zoom_factor()
        self.camera_x = max(0, min(WORLD_WIDTH - WIDTH / zoom, self.camera_x + dx))
        self.camera_y = max(0, min(WORLD_HEIGHT - HEIGHT / zoom, self.camera_y + dy))

    def zoom_factor(self):
        numerator, denominator = self.zoom_levels[self.zoom_index]
        return numerator / denominator

    def zoom_wheel(self, event):
        x, y = self.screen_point(event)
        left, top, width, height = self.minimap_bounds()
        if left <= x <= left + width and top <= y <= top + height:
            return 'break'
        direction = 1 if getattr(event, 'num', None) == 4 or getattr(event, 'delta', 0) > 0 else -1
        world_x = self.camera_x + x / self.zoom_factor()
        world_y = self.camera_y + y / self.zoom_factor()
        self.zoom_index = max(0, min(len(self.zoom_levels) - 1, self.zoom_index + direction))
        zoom = self.zoom_factor()
        self.move_camera(world_x - x / zoom - self.camera_x, world_y - y / zoom - self.camera_y)
        return 'break'

    def start_drag(self, event):
        self.drag_origin = (event.x, event.y)
        self.dragged = False
        x, y = self.screen_point(event)
        left, top, width, height = self.minimap_bounds()
        self.dragging_minimap = left <= x <= left + width and top <= y <= top + height
        if self.dragging_minimap:
            self.navigate_minimap(x, y)

    @staticmethod
    def minimap_bounds():
        return WIDTH - 175, HEIGHT - 125, 160, 103

    def screen_point(self, event):
        return (event.x * WIDTH / max(1, self.canvas.winfo_width()),
                event.y * HEIGHT / max(1, self.canvas.winfo_height()))

    def navigate_minimap(self, x, y):
        left, top, width, height = self.minimap_bounds()
        x = max(left, min(left + width, x))
        y = max(top, min(top + height, y))
        zoom = self.zoom_factor()
        self.move_camera((x - left) / width * WORLD_WIDTH - WIDTH / (2 * zoom) - self.camera_x,
                         (y - top) / height * WORLD_HEIGHT - HEIGHT / (2 * zoom) - self.camera_y)

    def drag(self, event):
        if self.drag_origin is None:
            return
        if self.dragging_minimap:
            self.dragged = True
            self.navigate_minimap(*self.screen_point(event))
            return
        old_x, old_y = self.drag_origin
        dx, dy = event.x - old_x, event.y - old_y
        if abs(dx) + abs(dy) > 1:
            self.dragged = True
        self.move_camera(-dx * WIDTH / max(1, self.canvas.winfo_width()) / self.zoom_factor(),
                         -dy * HEIGHT / max(1, self.canvas.winfo_height()) / self.zoom_factor())
        self.drag_origin = (event.x, event.y)

    def release(self, event):
        self.drag_origin = None
        if self.dragging_minimap:
            self.navigate_minimap(*self.screen_point(event))
            self.dragging_minimap = False
            return
        if not self.dragged:
            self.click(event)

    def click(self, event):
        x, y = self.screen_point(event)
        left, top, width, height = self.minimap_bounds()
        if left <= x <= left + width and top <= y <= top + height:
            self.navigate_minimap(x, y)
            return
        x = self.camera_x + x / self.zoom_factor()
        y = self.camera_y + y / self.zoom_factor()
        if self.mode not in ('build', 'build_enemy'):
            point = {'x': x, 'y': y}
            choices = [(distance(point, item), kind, item)
                       for kind, items in (('hormiga', self.colony.ants), ('araña', self.colony.enemies),
                                           ('alimento', self.colony.sources), ('nido propio', self.colony.nests),
                                           ('nido rival', self.colony.enemy_nests()))
                       for item in items if distance(point, item) <= (13 if kind == 'hormiga' else 25)]
            self.selected = min(choices, key=lambda item: item[0])[1:] if choices else None
            self.update_details()
            return
        if self.mode == 'build_enemy':
            health = 600 + self.colony.victories * 250
            self.colony.extra_enemy_nests.append({'x': x, 'y': y, 'hp': health, 'max_hp': health})
            self.status.config(text='Nido enemigo creado. Selecciónalo para crear enemigos gratis.')
        elif self.colony.food < 80:
            self.status.config(text='No hay alimento suficiente para construir.')
        elif any(math.hypot(x - n['x'], y - n['y']) < 70 for n in self.colony.nests):
            self.status.config(text='Elige un lugar más alejado de otra colonia.')
            return
        else:
            self.colony.food -= 80
            self.colony.nests.append({'x': x, 'y': y})
            self.status.config(text='Colonia construida. Las obreras usarán el nido más cercano.')
        self.mode = None
        self.build_pointer = None
        self.canvas.config(cursor='')

    def pause(self):
        self.paused = not self.paused
        self.status.config(text='Pausa' if self.paused else 'Simulación en marcha.')

    def set_speed(self, value):
        self.colony.speed = value
        self.status.config(text=f'Velocidad: {value}x. Usa 1, 2 o 3 para cambiarla.')

    def attack(self):
        if self.colony.enemy_nest['hp'] <= 0:
            self.colony.next_enemy_nest()
        self.colony.attack = not self.colony.attack
        self.status.config(text='Soldados y universales atacan el nido rival.' if self.colony.attack else 'Ataque cancelado.')

    def new_game(self):
        if messagebox.askyesno('Nueva partida', '¿Empezar de nuevo? Se reemplazará la partida guardada.'):
            self.colony = Colony()
            self.selected = None
            self.update_details()
            self.save()

    def update_details(self):
        if self.selected and self.selected[0] == 'nido rival':
            if not self.enemy_controls.winfo_ismapped():
                self.enemy_controls.pack(fill='x', pady=(4, 8))
        else:
            self.enemy_controls.pack_forget()
        if self.selected is None:
            self.detail_title.config(text='Sin selección')
            self.details.config(text='Selecciona una entidad.')
            self.detail_description.config(text='')
            self.portrait.config(image='', text='')
            return
        kind, entity = self.selected
        groups = {'hormiga': self.colony.ants, 'araña': self.colony.enemies,
                  'alimento': self.colony.sources, 'nido propio': self.colony.nests,
                  'nido rival': self.colony.enemy_nests()}
        if not any(item is entity for item in groups[kind]):
            self.selected = None
            self.enemy_controls.pack_forget()
            self.detail_title.config(text='Sin selección')
            self.details.config(text='La entidad seleccionada ya no está en el mapa.')
            self.detail_description.config(text='')
            self.portrait.config(image='', text='')
            return
        if kind == 'hormiga':
            role = entity['kind']
            maximum = 55 if role == 'soldado' else 35
            descriptions = {'obrera': 'Recolecta alimento.', 'soldado': 'Combate enemigos.',
                            'universal': 'Recolecta y combate.'}
            text = f"Hormiga {role}  |  Vida: {max(0, entity['hp'])}/{maximum}  |  Alimento transportado: {entity['carry']}  |  {descriptions[role]}"
        elif kind == 'araña':
            enemy_kind = entity.get('kind', 'araña')
            text = f"{enemy_kind.capitalize()}  |  Vida: {max(0, entity['hp'])}/{ENEMY_TYPES[enemy_kind][0]}  |  Ataca a las hormigas cercanas."
        elif kind == 'alimento':
            text = f"{entity.get('kind', 'Insecto').capitalize()} muerto  |  Alimento: {entity['amount']}/{entity['max_amount']}  |  Las obreras y universales lo recolectan."
        elif kind == 'nido rival':
            text = f"Nido rival  |  Vida: {entity['hp']}/{entity.get('max_hp', 100)}  |  Envía soldados o universales con «Atacar nido»."
        else:
            text = f"Nido propio  |  Alimento compartido: {self.colony.food}  |  Las hormigas depositan aquí lo que recolectan."
        parts = text.split('  |  ')
        self.detail_title.config(text=parts[0])
        self.details.config(text='\n'.join(parts[1:-1]))
        self.detail_description.config(text=parts[-1] if len(parts) > 1 else '')
        if kind == 'hormiga':
            sprite_key = ('ant', entity['kind'])
            frames = self.ant_sprites.get((entity['kind'], 'right', False))
        elif kind == 'araña':
            sprite_key = ('enemy', entity.get('kind', 'araña'))
            frames = self.insect_sprites.get(sprite_key)
        elif kind == 'alimento':
            sprite_key = ('food', entity.get('kind', 'insecto'))
            frames = self.insect_sprites.get(sprite_key)
        else:
            sprite_key = ('nest', 'colony')
            frames = self.insect_sprites.get(sprite_key)
        if frames:
            if sprite_key not in self.portrait_cache:
                enlarged = tk.PhotoImage(master=self.root)
                enlarged.tk.call(str(enlarged), 'copy', str(frames[0]), '-zoom', 3, 3)
                self.portrait_cache[sprite_key] = enlarged
            self.portrait.config(image=self.portrait_cache[sprite_key], text='')
        else:
            self.portrait.config(image='', text=kind.capitalize(), fg='#f4eedb')

    def save(self):
        try:
            self.colony.save()
        except OSError as error:
            self.status.config(text=f'No se pudo guardar: {error}')

    def close(self):
        self.save()
        self.audio.close()
        self.root.destroy()

    def tick(self):
        now = time.monotonic()
        dt = min(now - self.last, .1)
        self.last = now
        if not self.paused:
            for _ in range(self.colony.speed):
                self.colony.update(dt)
        for event, message in self.colony.events:
            self.audio.play('power22.wav' if event == 'victory' else 'damage.wav')
            if message:
                self.status.config(text=message)
        self.colony.events.clear()
        if self.selected is not None:
            self.update_details()
        if now - self.last_save > 30:
            self.save()
            self.last_save = now
        self.draw()
        self.next_frame += FRAME_SECONDS
        if self.next_frame <= now:
            self.next_frame = now + FRAME_SECONDS
        delay = max(1, math.ceil((self.next_frame - time.monotonic()) * 1000))
        self.root.after(delay, self.tick)

    def draw_bar(self, x, y, current, maximum, width, color):
        fraction = max(0, min(1, current / maximum)) if maximum > 0 else 0
        left = x - width / 2
        self.canvas.create_rectangle(left, y, left + width, y + 4, fill='#342d26', outline='')
        if fraction:
            self.canvas.create_rectangle(left, y, left + width * fraction, y + 4, fill=color, outline='')

    def draw(self):
        c, colony = self.canvas, self.colony
        c.delete('all')
        zoom = self.zoom_factor()
        left, top = self.camera_x - 100, self.camera_y - 100
        right, bottom = self.camera_x + WIDTH / zoom + 100, self.camera_y + HEIGHT / zoom + 100

        def visible(entity):
            return left <= entity['x'] <= right and top <= entity['y'] <= bottom

        c.create_rectangle(0, 0, WORLD_WIDTH, WORLD_HEIGHT, fill='#a6b77e', outline='')
        if self.selected is not None:
            entity = self.selected[1]
            c.create_oval(entity['x']-18, entity['y']-18, entity['x']+18, entity['y']+18,
                          outline='#fff4b8', width=2, dash=(3, 3))
        for x, y in ((240, 130), (420, 330), (690, 475), (810, 250), (300, 500)):
            c.create_oval(x-25, y-9, x+25, y+9, fill='#98a970', outline='')
        for nest in colony.nests:
            if not visible(nest):
                continue
            x, y = nest['x'], nest['y']
            if self.nest_image:
                c.create_image(x, y, image=self.nest_image)
            else:
                c.create_oval(x-27, y-15, x+27, y+16, fill='#795c3c', outline='#5a432e', width=3)
                c.create_oval(x-12, y-7, x+12, y+7, fill='#35281e', outline='')
        for nest in colony.enemy_nests():
            if not visible(nest):
                continue
            x, y = nest['x'], nest['y']
            if self.nest_image:
                c.create_image(x, y, image=self.nest_image)
            else:
                c.create_oval(x-24, y-14, x+24, y+14, fill='#754139', outline='#4a2825', width=3)
            c.create_text(x, y-42, text=f"NIDO RIVAL  {nest['hp']}", fill='#63372e', font=('Arial', 9, 'bold'))
            if SHOW_HEALTH_BARS:
                self.draw_bar(x, y-53, nest['hp'], nest.get('max_hp', 100), 48, '#e05c50')
        for source in colony.sources:
            if not visible(source):
                continue
            x, y = source['x'], source['y']
            color = {'mariposa': '#dc9e66', 'libélula': '#79b9b4', 'abeja': '#e4b655',
                     'saltamontes': '#668c49', 'cigarra': '#987452', 'mosca': '#625b54'}.get(source.get('kind'), '#a25f43')
            frames = self.insect_sprites.get(('food', source.get('kind', 'insecto')))
            if frames:
                c.create_image(x, y, image=frames[0])
            else:
                c.create_oval(x-9, y-5, x+9, y+5, fill=color, outline='#68432d')
            if SHOW_FOOD_BARS:
                c.create_text(x, y-22, text=str(source['amount']), fill='#3c3a27', font=('Arial', 8))
                self.draw_bar(x, y-32, source['amount'], source['max_amount'], 25, '#efcc62')
        for enemy in colony.enemies:
            if not visible(enemy):
                continue
            x, y = enemy['x'], enemy['y']
            kind = enemy.get('kind', 'araña')
            stats = ENEMY_TYPES.get(kind, ENEMY_TYPES['araña'])
            frames = self.insect_sprites.get(('enemy', kind))
            if frames:
                c.create_image(x, y, image=frames[int(time.monotonic() * 6) % len(frames)])
            else:
                c.create_oval(x-11, y-8, x+11, y+8, fill=stats[3], outline='#241d25')
            c.create_text(x, y-26, text=kind.upper(), fill='#3d2835', font=('Arial', 7, 'bold'))
            if SHOW_HEALTH_BARS:
                self.draw_bar(x, y-37, enemy['hp'], stats[0], 32, '#e05c50')
        for ant in colony.ants:
            if not visible(ant):
                continue
            x, y = ant['x'], ant['y']
            color = COLORS[ant['kind']]
            direction = ant.get('direction', 'right')
            dx, dy = {'right': (1, 0), 'left': (-1, 0), 'up': (0, -1), 'down': (0, 1)}[direction]
            frames = self.ant_sprites.get((ant['kind'], direction, bool(ant['carry'])))
            if frames:
                c.create_image(x, y, image=frames[int(time.monotonic() * 8) % len(frames)])
            else:
                for offset, radius in ((-4, 3), (1, 3), (5, 2)):
                    part_x, part_y = x + dx * offset, y + dy * offset
                    c.create_oval(part_x-radius, part_y-radius, part_x+radius, part_y+radius, fill=color, outline='')
            if SHOW_HEALTH_BARS:
                self.draw_bar(x, y-11, ant['hp'], 55 if ant['kind'] == 'soldado' else 35, 20, '#76c864')
            if ant['carry']:
                food_x, food_y = x + dx * 9, y + dy * 9
                c.create_oval(food_x-2, food_y-2, food_x+2, food_y+2, fill='#f6dc88', outline='')
        c.move('all', -self.camera_x, -self.camera_y)
        numerator, denominator = self.zoom_levels[self.zoom_index]
        if numerator != denominator:
            for item in c.find_all():
                if c.type(item) == 'image':
                    original = c.itemcget(item, 'image')
                    key = (original, numerator, denominator)
                    if key not in self.scaled_images:
                        scaled = tk.PhotoImage(master=self.root)
                        scaled.tk.call(str(scaled), 'copy', original, '-zoom', numerator, numerator,
                                       '-subsample', denominator, denominator)
                        self.scaled_images[key] = scaled
                    c.itemconfigure(item, image=self.scaled_images[key])
            c.scale('all', 0, 0, numerator / denominator, numerator / denominator)
        if self.mode in ('build', 'build_enemy') and self.build_pointer is not None:
            x, y = self.build_pointer
            left, top, width, height = self.minimap_bounds()
            if not (left <= x <= left + width and top <= y <= top + height):
                if self.nest_image:
                    c.create_image(x, y, image=self.nest_image)
                else:
                    c.create_oval(x-25, y-15, x+25, y+15, fill='#795c3c', outline='#f4eedb')
        self.draw_minimap()
        counts = dict.fromkeys(COSTS, 0)
        for ant in colony.ants:
            counts[ant['kind']] += 1
        self.info.config(text=f"Alimento {colony.food}   Hormigas {len(colony.ants)}  (O {counts['obrera']} · S {counts['soldado']} · U {counts['universal']})   Nivel {colony.level} · {colony.speed}x")
        c.scale('all', 0, 0, c.winfo_width() / WIDTH, c.winfo_height() / HEIGHT)

    def draw_minimap(self):
        c = self.canvas
        left, top, width, height = self.minimap_bounds()
        c.create_rectangle(left-4, top-20, left+width+4, top+height+4,
                           fill='#27352b', outline='#e4e2bc', width=2)
        c.create_text(left+5, top-10, text='MAPA', anchor='w', fill='#f1efdc', font=('Arial', 8, 'bold'))
        c.create_rectangle(left, top, left+width, top+height, fill='#7c9162', outline='#b8c99e')

        def dot(entity, color, radius):
            x = left + entity['x'] / WORLD_WIDTH * width
            y = top + entity['y'] / WORLD_HEIGHT * height
            c.create_oval(x-radius, y-radius, x+radius, y+radius, fill=color, outline='')

        def dots(entities, color, radius):
            seen = set()
            for entity in entities:
                cell = (round(entity['x'] / WORLD_WIDTH * width), round(entity['y'] / WORLD_HEIGHT * height))
                if cell not in seen:
                    seen.add(cell)
                    dot(entity, color, radius)

        dots(self.colony.sources, '#edcf74', 2)
        for nest in self.colony.nests:
            dot(nest, '#f7efe0', 4)
        dots(self.colony.enemies, '#d54343', 3)
        for nest in self.colony.enemy_nests():
            dot(nest, '#e95a4f', 4)
        dots(self.colony.ants, '#2f2520', 2)
        c.create_rectangle(left + self.camera_x / WORLD_WIDTH * width,
                           top + self.camera_y / WORLD_HEIGHT * height,
                           left + (self.camera_x + WIDTH / self.zoom_factor()) / WORLD_WIDTH * width,
                           top + (self.camera_y + HEIGHT / self.zoom_factor()) / WORLD_HEIGHT * height,
                           outline='#fff4b8', width=2)


if __name__ == '__main__':
    Game()
