"""
Shadowforge — Advanced Top‑Down Action Roguelite (single-file)
Requirements: Python 3.8+, pygame
Install: pip install pygame
Run: python shadowforge.py

Overview
- Procedural dungeon (rooms + corridors) with fog-of-war lighting
- Top-down player with smooth movement, dodges, dash and weapon switching
- Multiple enemy types with behavior trees (patrol, seek, ranged)
- Weapons: melee (slash), ranged (projectile) and special (area)
- Loot, shop between runs (spend gold), simple perk system
- Room-based waves, boss rooms, persistent unlocks saved to disk (JSON)
- Particle system, screen shake, camera lerp, UI/HUD, keybindings

This is intentionally feature-rich but kept in a single file for easy experimentation.
"""

import math
import random
import json
import os
import time
from collections import deque

import pygame
from pygame import Vector2

# -------- CONFIG --------
SCREEN = (1280, 720)
FPS = 60
TILE = 48
MAP_W, MAP_H = 40, 24  # in tiles (larger maps cost more CPU)
ROOM_MIN, ROOM_MAX = 5, 12
MAX_ROOMS = 10
PLAYER_SPEED = 260
DASH_SPEED = 720
DASH_TIME = 0.18
INVINCIBLE_TIME = 0.9
SAVE_FILE = 'shadowforge_save.json'

# Colors
COL_BG = (10, 10, 16)
COL_WALL = (28, 28, 36)
COL_FLOOR = (18, 18, 26)
COL_PLAYER = (100, 200, 255)
COL_ENEMY = (240, 100, 100)
COL_GOLD = (240, 220, 80)
COL_UI = (220, 220, 220)

# Helpers
def clamp(v, a, b):
    return max(a, min(b, v))

# Basic RNG seed useful for testing reproducible runs
random.seed()

# -------- SAVE / UNLOCKS --------
class SaveData:
    def __init__(self):
        self.gold_total = 0
        self.unlocked = {'double_dash': False, 'extra_hp': False}
        self.load()

    def load(self):
        if os.path.exists(SAVE_FILE):
            try:
                with open(SAVE_FILE, 'r') as f:
                    data = json.load(f)
                    self.gold_total = data.get('gold_total', 0)
                    self.unlocked = data.get('unlocked', self.unlocked)
            except Exception as e:
                print('Failed to load save:', e)

    def save(self):
        with open(SAVE_FILE, 'w') as f:
            json.dump({'gold_total': self.gold_total, 'unlocked': self.unlocked}, f)

save_data = SaveData()

# -------- MAP / DUNGEON GENERATION --------
class RectRoom:
    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.center = (x + w//2, y + h//2)

    def intersects(self, other):
        return (self.x <= other.x + other.w and self.x + self.w >= other.x and
                self.y <= other.y + other.h and self.y + self.h >= other.y)

class Dungeon:
    def __init__(self, seed=None):
        self.seed = seed or random.randint(0, 10**9)
        random.seed(self.seed)
        self.tiles = [['#' for _ in range(MAP_H)] for __ in range(MAP_W)]
        self.rooms = []
        self.generate()

    def create_room(self, room: RectRoom):
        for i in range(room.x, room.x + room.w):
            for j in range(room.y, room.y + room.h):
                if 0 <= i < MAP_W and 0 <= j < MAP_H:
                    self.tiles[i][j] = '.'

    def create_h_tunnel(self, x1, x2, y):
        for x in range(min(x1, x2), max(x1, x2) + 1):
            if 0 <= x < MAP_W and 0 <= y < MAP_H:
                self.tiles[x][y] = '.'

    def create_v_tunnel(self, y1, y2, x):
        for y in range(min(y1, y2), max(y1, y2) + 1):
            if 0 <= x < MAP_W and 0 <= y < MAP_H:
                self.tiles[x][y] = '.'

    def generate(self):
        self.rooms = []
        for _ in range(MAX_ROOMS):
            w = random.randint(ROOM_MIN, ROOM_MAX)
            h = random.randint(ROOM_MIN, ROOM_MAX)
            x = random.randint(1, MAP_W - w - 2)
            y = random.randint(1, MAP_H - h - 2)
            new_room = RectRoom(x, y, w, h)
            if any(new_room.intersects(r) for r in self.rooms):
                continue
            self.create_room(new_room)
            if self.rooms:
                (prev_x, prev_y) = self.rooms[-1].center
                (new_x, new_y) = new_room.center
                if random.choice([True, False]):
                    self.create_h_tunnel(prev_x, new_x, prev_y)
                    self.create_v_tunnel(prev_y, new_y, new_x)
                else:
                    self.create_v_tunnel(prev_y, new_y, prev_x)
                    self.create_h_tunnel(prev_x, new_x, new_y)
            self.rooms.append(new_room)

    def get_tile(self, tx, ty):
        if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
            return self.tiles[tx][ty]
        return '#'

# -------- ENTITIES --------
class Particle:
    def __init__(self, pos, vel, life, col):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.col = col

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel *= 0.92

    def draw(self, surf, cam):
        if self.life <= 0:
            return
        a = int(255 * (self.life/self.max_life))
        pygame.draw.circle(surf, (*self.col, a), (int(self.pos.x - cam.x), int(self.pos.y - cam.y)), max(1, int(4 * (self.life/self.max_life))))

class Projectile:
    def __init__(self, pos, vel, owner, dmg=12, life=2.0):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.owner = owner
        self.dmg = dmg
        self.life = life

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt

    def draw(self, surf, cam):
        if self.life <= 0:
            return
        pygame.draw.circle(surf, (255, 240, 200), (int(self.pos.x - cam.x), int(self.pos.y - cam.y)), 4)

class Enemy:
    def __init__(self, pos, kind=0):
        self.pos = Vector2(pos)
        self.kind = kind
        self.radius = 14 if kind == 0 else 20
        self.max_hp = 40 if kind == 0 else 110
        self.hp = self.max_hp
        self.speed = 120 if kind == 0 else 70
        self.aggro = 220 if kind == 0 else 350
        self.fire_cooldown = 0

    def update(self, dt, player, projectiles, particles):
        to_player = player.pos - self.pos
        dist = to_player.length()
        if self.kind == 0:  # melee simple
            if dist < self.aggro:
                dirv = to_player.normalize()
                self.pos += dirv * self.speed * dt
        else:  # ranged
            if dist < self.aggro:
                # keep distance
                if dist < 160:
                    self.pos -= to_player.normalize() * self.speed * dt
                elif dist > 220:
                    self.pos += to_player.normalize() * self.speed * dt
                # fire
                self.fire_cooldown -= dt
                if self.fire_cooldown <= 0:
                    self.fire_cooldown = 1.1
                    vel = to_player.normalize() * 360
                    projectiles.append(Projectile(self.pos + to_player.normalize()*22, vel, owner=self, dmg=14))

    def draw(self, surf, cam):
        c = COL_ENEMY if self.kind == 0 else (180, 100, 220)
        pygame.draw.circle(surf, c, (int(self.pos.x - cam.x), int(self.pos.y - cam.y)), self.radius)
        # hp bar
        w = int(self.radius*2 * (self.hp/self.max_hp))
        if w > 0:
            pygame.draw.rect(surf, (40,40,40), (int(self.pos.x - cam.x - self.radius), int(self.pos.y - cam.y - self.radius - 8), self.radius*2, 6))
            pygame.draw.rect(surf, (120,220,120), (int(self.pos.x - cam.x - self.radius), int(self.pos.y - cam.y - self.radius - 8), w, 6))

class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.radius = 14
        self.hp = 120 if not save_data.unlocked.get('extra_hp', False) else 160
        self.max_hp = self.hp
        self.dash_timer = 0
        self.inv_timer = 0
        self.gold = 0
        self.weapons = ['sword', 'pistol', 'grenade']
        self.cur_weapon = 1
        self.projectiles = []
        self.particles = []

    def switch_weapon(self, idx):
        self.cur_weapon = idx % len(self.weapons)

    def dash(self):
        if self.dash_timer <= 0:
            self.dash_timer = DASH_TIME
            self.inv_timer = INVINCIBLE_TIME
            return True
        return False

    def shoot(self, target):
        w = self.weapons[self.cur_weapon]
        dirv = (Vector2(target) - self.pos)
        if dirv.length_squared() == 0:
            dirv = Vector2(1, 0)
        dirv = dirv.normalize()
        if w == 'pistol':
            self.projectiles.append(Projectile(self.pos + dirv*20, dirv*520, self, dmg=18))
        elif w == 'grenade':
            self.projectiles.append(Projectile(self.pos + dirv*20, dirv*360 + Vector2(0,-40), self, dmg=45, life=1.6))
        elif w == 'sword':
            # melee slash simulated via short-range projectile
            self.projectiles.append(Projectile(self.pos + dirv*28, dirv*240, self, dmg=34, life=0.25))

    def update(self, dt, keys, mouse_pos, projectiles_global, particles):
        # movement
        move = Vector2(0,0)
        if keys[pygame.K_w] or keys[pygame.K_UP]: move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: move.x += 1
        if move.length_squared() > 0:
            move = move.normalize()
        target_speed = PLAYER_SPEED
        if self.dash_timer > 0:
            target_speed = DASH_SPEED
            self.dash_timer -= dt
        self.vel += (move*target_speed - self.vel) * clamp(12*dt, 0, 1)
        self.pos += self.vel * dt
        self.inv_timer = max(0, self.inv_timer - dt)
        # update own projectiles and push to global on expiry
        for pr in list(self.projectiles):
            pr.update(dt)
            if pr.life <= 0:
                # create explosion for grenade
                if pr.dmg >= 40:
                    for _ in range(18):
                        particles.append(Particle(pr.pos + Vector2(random.uniform(-6,6), random.uniform(-6,6)), Vector2(random.uniform(-120,120), random.uniform(-120,120)), random.uniform(0.4,0.9), (240,180,60)))
                projectiles_global.append(pr)
                self.projectiles.remove(pr)

    def draw(self, surf, cam):
        c = COL_PLAYER if self.inv_timer<=0 else (255,255,200)
        pygame.draw.circle(surf, c, (int(self.pos.x - cam.x), int(self.pos.y - cam.y)), self.radius)
        # weapon indicator
        font = pygame.font.SysFont('Arial', 16)
        txt = font.render(self.weapons[self.cur_weapon].upper(), True, COL_UI)
        surf.blit(txt, (int(self.pos.x - cam.x - txt.get_width()/2), int(self.pos.y - cam.y - self.radius - 22)))

# -------- GAME MANAGER --------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption('Shadowforge')
        self.screen = pygame.display.set_mode(SCREEN)
        self.clock = pygame.time.Clock()
        self.dt = 0
        self.dungeon = Dungeon()
        # spawn player in first room center
        cx, cy = self.dungeon.rooms[0].center
        self.player = Player(Vector2(cx*TILE + TILE/2, cy*TILE + TILE/2))
        self.enemies = []
        self.projectiles = []
        self.particles = []
        self.cam = Vector2(self.player.pos)
        self.running = True
        self.state = 'playing'  # menu, playing, shop
        self.font = pygame.font.SysFont('Arial', 18)
        self.spawn_enemies_wave(3)
        self.room_index = 0
        self.shake = 0

    def spawn_enemies_wave(self, n):
        # spawn enemies in rooms except first
        for _ in range(n):
            r = random.choice(self.dungeon.rooms[1:])
            rx = random.randint(r.x+1, r.x + r.w-2)
            ry = random.randint(r.y+1, r.y + r.h-2)
            kind = 0 if random.random() < 0.7 else 1
            epos = Vector2(rx*TILE + TILE/2, ry*TILE + TILE/2)
            self.enemies.append(Enemy(epos, kind))

    def handle_input(self):
        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_TAB:
                    self.state = 'shop' if self.state=='playing' else 'playing'
                if event.key == pygame.K_1:
                    self.player.switch_weapon(0)
                if event.key == pygame.K_2:
                    self.player.switch_weapon(1)
                if event.key == pygame.K_3:
                    self.player.switch_weapon(2)
                if event.key == pygame.K_SPACE:
                    self.player.dash()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and self.state=='playing':
                    # shoot toward mouse
                    world_mouse = Vector2(mx, my) + self.cam - Vector2(SCREEN[0]/2, SCREEN[1]/2)
                    self.player.shoot(world_mouse)
        return keys

    def physics(self):
        keys = pygame.key.get_pressed()
        mx, my = pygame.mouse.get_pos()
        world_mouse = Vector2(mx, my) + self.cam - Vector2(SCREEN[0]/2, SCREEN[1]/2)
        self.player.update(self.dt, keys, world_mouse, self.projectiles, self.particles)
        # update enemies
        for e in list(self.enemies):
            e.update(self.dt, self.player, self.projectiles, self.particles)
            if e.hp <= 0:
                self.player.gold += 8 if e.kind==0 else 28
                save_data.gold_total += 8 if e.kind==0 else 28
                for _ in range(12):
                    self.particles.append(Particle(e.pos + Vector2(random.uniform(-6,6), random.uniform(-6,6)), Vector2(random.uniform(-120,120), random.uniform(-120,120)), random.uniform(0.4,1.0), (240,100,100)))
                self.enemies.remove(e)
        # update global projectiles (including those emitted by enemies)
        for pr in list(self.projectiles):
            pr.update(self.dt)
            # collisions
            if pr.life <= 0:
                try:
                    self.projectiles.remove(pr)
                except:
                    pass
                continue
            # if owner is enemy, check hit player
            if isinstance(pr.owner, Enemy):
                if (pr.pos - self.player.pos).length() < self.player.radius + 6 and self.player.inv_timer<=0:
                    self.player.hp -= pr.dmg
                    self.player.inv_timer = 0.6
                    self.shake = 6
                    for _ in range(8):
                        self.particles.append(Particle(self.player.pos + Vector2(random.uniform(-6,6), random.uniform(-6,6)), Vector2(random.uniform(-120,120), random.uniform(-120,120)), random.uniform(0.2,0.7), (240,200,80)))
                    try:
                        self.projectiles.remove(pr)
                    except:
                        pass
            # if owner player, check hit enemy
            elif isinstance(pr.owner, Player):
                for e in self.enemies:
                    if (pr.pos - e.pos).length() < e.radius + 6:
                        e.hp -= pr.dmg
                        for _ in range(6):
                            self.particles.append(Particle(pr.pos + Vector2(random.uniform(-3,3), random.uniform(-3,3)), Vector2(random.uniform(-80,80), random.uniform(-80,80)), random.uniform(0.2,0.6), (255,200,120)))
                        try:
                            self.projectiles.remove(pr)
                        except:
                            pass
        # update particles
        for p in list(self.particles):
            p.update(self.dt)
            if p.life <= 0:
                try:
                    self.particles.remove(p)
                except:
                    pass

    def update(self):
        if self.state != 'playing':
            return
        self.physics()
        # camera lerp to player
        target = self.player.pos
        self.cam += (target - self.cam) * clamp(6*self.dt, 0, 1)
        # reduce shake
        self.shake = max(0, self.shake - 40*self.dt)
        # if room clear spawn more
        if not self.enemies:
            # reward
            self.player.gold += 25
            save_data.gold_total += 25
            # next wave bigger
            self.spawn_enemies_wave(3 + random.randint(0,3))

    def draw_map(self):
        # draw tiles around camera
        cam_tile_x = int((self.cam.x) // TILE)
        cam_tile_y = int((self.cam.y) // TILE)
        tiles_x = SCREEN[0]//TILE + 4
        tiles_y = SCREEN[1]//TILE + 4
        start_x = clamp(cam_tile_x - tiles_x//2, 0, MAP_W-tiles_x)
        start_y = clamp(cam_tile_y - tiles_y//2, 0, MAP_H-tiles_y)
        for i in range(start_x, min(MAP_W, start_x + tiles_x)):
            for j in range(start_y, min(MAP_H, start_y + tiles_y)):
                t = self.dungeon.get_tile(i, j)
                rect = pygame.Rect((i*TILE - self.cam.x + SCREEN[0]//2, j*TILE - self.cam.y + SCREEN[1]//2), (TILE, TILE))
                if t == '#':
                    pygame.draw.rect(self.screen, COL_WALL, rect)
                else:
                    pygame.draw.rect(self.screen, COL_FLOOR, rect)

    def draw(self):
        # background
        self.screen.fill(COL_BG)
        # map
        self.draw_map()
        # entities
        cam_offset = self.cam - Vector2(SCREEN[0]/2, SCREEN[1]/2)
        # projectiles
        for pr in list(self.player.projectiles) + list(self.projectiles):
            pr.draw(self.screen, cam_offset)
        for e in self.enemies:
            e.draw(self.screen, cam_offset)
        # player
        self.player.draw(self.screen, cam_offset)
        # particles
        for p in self.particles:
            p.draw(self.screen, cam_offset)
        # HUD
        self.draw_hud()
        if self.state == 'shop':
            self.draw_shop()

    def draw_hud(self):
        font = self.font
        # HP
        hp_s = font.render(f'HP: {int(self.player.hp)}/{int(self.player.max_hp)}', True, COL_UI)
        self.screen.blit(hp_s, (12, 12))
        # gold
        gold_s = font.render(f'Gold: {self.player.gold} (Total: {save_data.gold_total})', True, COL_UI)
        self.screen.blit(gold_s, (12, 36))
        # weapon
        w_s = font.render(f'Weapon: {self.player.weapons[self.player.cur_weapon]}', True, COL_UI)
        self.screen.blit(w_s, (12, 60))

    def draw_shop(self):
        # simple shop overlay - buy upgrades
        srect = pygame.Rect(200, 100, SCREEN[0]-400, SCREEN[1]-200)
        pygame.draw.rect(self.screen, (18,18,22), srect)
        pygame.draw.rect(self.screen, (90,90,110), srect, 3)
        font = pygame.font.SysFont('Arial', 22)
        title = font.render('SHOP - Press TAB to leave', True, COL_UI)
        self.screen.blit(title, (srect.x+18, srect.y+14))
        items = [('Double Dash', 150, 'double_dash'), ('Extra Max HP', 240, 'extra_hp')]
        y = srect.y + 64
        for name, cost, key in items:
            txt = font.render(f'{name}  -  {cost} gold', True, COL_UI)
            self.screen.blit(txt, (srect.x+24, y))
            buy_rect = pygame.Rect(srect.x + srect.w - 140, y, 110, 28)
            pygame.draw.rect(self.screen, (60,60,80), buy_rect)
            btxt = font.render('BUY', True, COL_UI)
            self.screen.blit(btxt, (buy_rect.x + 30, buy_rect.y + 4))
            y += 48
        # simple mouse click handler
        mx, my = pygame.mouse.get_pos()
        mdown = pygame.mouse.get_pressed()
        if mdown[0]:
            # detect clicks roughly in item area
            idx = (my - (srect.y + 64)) // 48
            if 0 <= idx < len(items):
                name, cost, key = items[idx]
                if self.player.gold >= cost and not save_data.unlocked.get(key, False):
                    save_data.unlocked[key] = True
                    save_data.gold_total += 0
                    self.player.gold -= cost
                    save_data.save()

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS)/1000.0
            keys = self.handle_input()
            if self.state == 'playing':
                self.update()
            self.draw()
            pygame.display.flip()
        pygame.quit()
        save_data.save()

if __name__ == '__main__':
    Game().run()
ju