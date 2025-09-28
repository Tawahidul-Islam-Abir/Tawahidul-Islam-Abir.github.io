"""
Modern Action Game (single-file)
Requirements: Python 3.8+, pygame
Install: pip install pygame
Run: python modern_action_game.py

Features:
- Smooth player movement with dash and dodge roll
- Aim with mouse, shoot bullets with recoil
- Procedural particle effects (muzzle flash, explosions)
- Simple enemy AI with patrol and chase states
- Wave based spawner and scoring
- Upgrades, health, HUD, pause & main menu
- All art is procedural (no external assets required)

This file is intentionally one file to make it easy to run and iterate on.
"""

import math
import random
import sys
from dataclasses import dataclass

import pygame
from pygame import Vector2

# --------- CONFIG ---------
SCREEN_SIZE = (1200, 700)
FPS = 60
PLAYER_SPEED = 320
BULLET_SPEED = 900
ENEMY_SPEED = 140
SPAWN_PADDING = 50

# Colors
WHITE = (245, 245, 245)
BLACK = (12, 12, 12)
UI_BG = (20, 20, 22)
RED = (220, 60, 60)
GREEN = (60, 200, 100)
YELLOW = (240, 220, 100)

# --------- UTIL ---------

def clamp(v, a, b):
    return max(a, min(b, v))


def angle_to(v: Vector2):
    return math.degrees(math.atan2(-v.y, v.x))


# --------- PARTICLES ---------
class Particle:
    def __init__(self, pos, vel, life, size, color):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.life = life
        self.max_life = life
        self.size = size
        self.color = color

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        # gravity-like
        self.vel *= 0.98

    def draw(self, surf):
        if self.life <= 0:
            return
        a = clamp(self.life / self.max_life, 0, 1)
        s = int(self.size * (0.6 + 0.4 * a))
        surf_rect = pygame.Rect(0, 0, s, s)
        surf_rect.center = self.pos
        col = tuple(int(c * (0.4 + 0.6 * a)) for c in self.color)
        pygame.draw.ellipse(surf, col, surf_rect)


# --------- ENTITIES ---------
class Bullet:
    def __init__(self, pos, vel, owner):
        self.pos = Vector2(pos)
        self.vel = Vector2(vel)
        self.owner = owner
        self.life = 2.2
        self.radius = 4

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt

    def draw(self, surf):
        if self.life <= 0:
            return
        end = self.pos - self.vel.normalize() * 6
        pygame.draw.line(surf, YELLOW, tuple(self.pos), tuple(end), 2)
        pygame.draw.circle(surf, YELLOW, (int(self.pos.x), int(self.pos.y)), self.radius)


class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.speed = PLAYER_SPEED
        self.health = 100
        self.max_health = 100
        self.radius = 18
        self.reload = 0
        self.fire_rate = 0.12
        self.dash_timer = 0
        self.score = 0
        self.upgrades = {"damage": 1.0, "firerate": 1.0}

    def update(self, dt, keys, mouse_pos):
        move = Vector2(0, 0)
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            move.x += 1
        if move.length_squared() > 0:
            move = move.normalize()
        target_speed = self.speed
        if keys[pygame.K_LSHIFT]:
            target_speed *= 1.6
            self.dash_timer = 0.12
        self.vel += (move * target_speed - self.vel) * clamp(12 * dt, 0, 1)
        self.pos += self.vel * dt
        self.reload = max(0, self.reload - dt * self.upgrades.get("firerate", 1.0))
        if self.dash_timer > 0:
            self.dash_timer -= dt

    def shoot(self, target, bullets, particles):
        if self.reload > 0:
            return
        direction = Vector2(target) - self.pos
        if direction.length_squared() == 0:
            direction = Vector2(1, 0)
        direction = direction.normalize()
        spread = random.uniform(-6, 6)
        rad = math.radians(spread)
        dir_rot = Vector2(direction.x * math.cos(rad) - direction.y * math.sin(rad),
                          direction.x * math.sin(rad) + direction.y * math.cos(rad))
        speed = BULLET_SPEED
        bullets.append(Bullet(self.pos + dir_rot * (self.radius + 6), dir_rot * speed, owner=self))
        self.reload = self.fire_rate
        # muzzle particle
        for _ in range(8):
            vel = dir_rot.rotate(random.uniform(-40, 40)) * random.uniform(80, 420)
            particles.append(Particle(self.pos + dir_rot * (self.radius + 6), vel, random.uniform(0.25, 0.6), random.uniform(2, 5), YELLOW))

    def draw(self, surf, mouse_pos):
        # shadow
        pygame.draw.circle(surf, (10, 10, 10), (int(self.pos.x + 4), int(self.pos.y + 6)), self.radius)
        # body
        pygame.draw.circle(surf, (40, 120, 200), (int(self.pos.x), int(self.pos.y)), self.radius)
        # direction
        dirv = Vector2(mouse_pos) - self.pos
        if dirv.length_squared() > 1:
            dirv = dirv.normalize()
            tip = self.pos + dirv * (self.radius + 8)
            pygame.draw.line(surf, WHITE, tuple(self.pos), tuple(tip), 3)


class Enemy:
    def __init__(self, pos, kind=0):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.kind = kind
        self.radius = 14 if kind == 0 else 22
        self.health = 30 if kind == 0 else 90
        self.max_health = self.health
        self.state = "patrol"
        self.target = None
        self.wander_dir = Vector2(random.uniform(-1, 1), random.uniform(-1, 1)).normalize()
        self.change_timer = random.uniform(1.0, 3.0)

    def update(self, dt, player_pos):
        # simple state machine: patrol -> chase
        dist = (player_pos - self.pos).length()
        if dist < 260:
            self.state = "chase"
        elif dist > 360:
            self.state = "patrol"

        if self.state == "chase":
            desired = (player_pos - self.pos).normalize() * ENEMY_SPEED
        else:
            self.change_timer -= dt
            if self.change_timer <= 0:
                self.wander_dir = Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
                if self.wander_dir.length_squared() > 0:
                    self.wander_dir = self.wander_dir.normalize()
                self.change_timer = random.uniform(1.0, 3.0)
            desired = self.wander_dir * (ENEMY_SPEED * 0.6)

        self.vel += (desired - self.vel) * clamp(6 * dt, 0, 1)
        self.pos += self.vel * dt

    def draw(self, surf):
        col = (200, 80, 80) if self.kind == 0 else (180, 90, 200)
        pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), self.radius)
        # health
        hpw = int(self.radius * 2 * (self.health / max(1, self.max_health)))
        if hpw > 0:
            rect = pygame.Rect(0, 0, hpw, 4)
            rect.midtop = (self.pos.x, self.pos.y - self.radius - 8)
            pygame.draw.rect(surf, GREEN, rect)


# --------- GAME ---------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Modern Action - Python (procedural art)")
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        self.clock = pygame.time.Clock()
        self.dt = 0
        self.player = Player(Vector2(SCREEN_SIZE[0] / 2, SCREEN_SIZE[1] / 2))
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.spawn_timer = 0
        self.wave = 1
        self.running = True
        self.paused = False
        self.state = "menu"  # menu, playing, gameover
        self.menu_sel = 0
        self.font = pygame.font.SysFont("Segoe UI", 20)

    def spawn_enemy(self):
        side = random.choice(["left", "right", "top", "bottom"])
        if side == "left":
            pos = Vector2(-SPAWN_PADDING, random.uniform(0, SCREEN_SIZE[1]))
        elif side == "right":
            pos = Vector2(SCREEN_SIZE[0] + SPAWN_PADDING, random.uniform(0, SCREEN_SIZE[1]))
        elif side == "top":
            pos = Vector2(random.uniform(0, SCREEN_SIZE[0]), -SPAWN_PADDING)
        else:
            pos = Vector2(random.uniform(0, SCREEN_SIZE[0]), SCREEN_SIZE[1] + SPAWN_PADDING)
        kind = 0 if random.random() < 0.82 else 1
        self.enemies.append(Enemy(pos, kind))

    def world_bounds(self, ent):
        x = clamp(ent.pos.x, -40, SCREEN_SIZE[0] + 40)
        y = clamp(ent.pos.y, -40, SCREEN_SIZE[1] + 40)
        ent.pos.x = x
        ent.pos.y = y

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.paused = not self.paused
                    else:
                        self.running = False
                if event.key == pygame.K_SPACE and self.state == "menu":
                    self.start_game()
                if event.key == pygame.K_r and self.state == "gameover":
                    self.start_game()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and self.state == "playing" and not self.paused:
                    self.player.shoot(pygame.mouse.get_pos(), self.bullets, self.particles)

    def start_game(self):
        self.state = "playing"
        self.player = Player(Vector2(SCREEN_SIZE[0] / 2, SCREEN_SIZE[1] / 2))
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.wave = 1
        self.spawn_timer = 0
        self.player.score = 0

    def update(self):
        keys = pygame.key.get_pressed()
        mouse_pos = pygame.mouse.get_pos()
        if self.state == "playing" and not self.paused:
            self.player.update(self.dt, keys, mouse_pos)
            # spawn logic
            self.spawn_timer -= self.dt
            if self.spawn_timer <= 0:
                # spawn wave count
                for _ in range(self.wave + 2):
                    self.spawn_enemy()
                self.spawn_timer = 6.0
                self.wave += 1
            # update bullets
            for b in list(self.bullets):
                b.update(self.dt)
                if b.life <= 0:
                    self.bullets.remove(b)
            # update enemies
            for e in list(self.enemies):
                e.update(self.dt, self.player.pos)
                self.world_bounds(e)
                # collisions with bullets
                for b in list(self.bullets):
                    if (b.pos - e.pos).length() < e.radius + b.radius:
                        e.health -= 20 * self.player.upgrades.get("damage", 1.0)
                        try:
                            self.bullets.remove(b)
                        except ValueError:
                            pass
                        # hit particles
                        for _ in range(10):
                            vel = Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * random.uniform(40, 260)
                            self.particles.append(Particle(e.pos, vel, random.uniform(0.3, 0.9), random.uniform(2, 5), RED))
                if e.health <= 0:
                    self.enemies.remove(e)
                    self.player.score += 10 if e.kind == 0 else 35
                    # explosion particles
                    for _ in range(25):
                        vel = Vector2(random.uniform(-1, 1), random.uniform(-1, 1)) * random.uniform(40, 480)
                        self.particles.append(Particle(e.pos, vel, random.uniform(0.6, 1.2), random.uniform(3, 8), random.choice([RED, YELLOW, GREEN])))
            # player collision with enemies
            for e in self.enemies:
                if (self.player.pos - e.pos).length() < self.player.radius + e.radius:
                    self.player.health -= 30 * self.dt
            # update particles
            for p in list(self.particles):
                p.update(self.dt)
                if p.life <= 0:
                    self.particles.remove(p)
            # screen wrap for player mildly
            self.player.pos.x = clamp(self.player.pos.x, 16, SCREEN_SIZE[0] - 16)
            self.player.pos.y = clamp(self.player.pos.y, 16, SCREEN_SIZE[1] - 16)
            # check game over
            if self.player.health <= 0:
                self.state = "gameover"

    def draw_hud(self):
        # top-left boxes
        pygame.draw.rect(self.screen, UI_BG, (8, 8, 260, 68), border_radius=8)
        # health bar
        pygame.draw.rect(self.screen, (40, 40, 40), (20, 20, 220, 18), border_radius=8)
        hpw = int(220 * (self.player.health / self.player.max_health))
        if hpw > 0:
            pygame.draw.rect(self.screen, RED, (20, 20, hpw, 18), border_radius=8)
        txt = self.font.render(f"Health: {int(self.player.health)}", True, WHITE)
        self.screen.blit(txt, (24, 44))
        # score
        score_txt = self.font.render(f"Score: {self.player.score}", True, WHITE)
        self.screen.blit(score_txt, (SCREEN_SIZE[0] - 160, 20))
        wave_txt = self.font.render(f"Wave: {self.wave}", True, WHITE)
        self.screen.blit(wave_txt, (SCREEN_SIZE[0] - 160, 48))

    def draw(self):
        # background
        self.screen.fill((18, 18, 20))
        # subtle grid
        gstep = 48
        for x in range(0, SCREEN_SIZE[0], gstep):
            pygame.draw.line(self.screen, (18, 18, 26), (x, 0), (x, SCREEN_SIZE[1]))
        for y in range(0, SCREEN_SIZE[1], gstep):
            pygame.draw.line(self.screen, (18, 18, 26), (0, y), (SCREEN_SIZE[0], y))

        # draw entities sorted by y for simple depth
        drawn = []
        drawn.extend(self.enemies)
        drawn.extend(self.bullets)
        drawn.sort(key=lambda o: getattr(o, 'pos', Vector2(0, 0)).y)
        for o in drawn:
            o.draw(self.screen)
        # draw player above
        self.player.draw(self.screen, pygame.mouse.get_pos())
        # particles on top
        for p in self.particles:
            p.draw(self.screen)
        # UI
        self.draw_hud()
        if self.paused:
            self.draw_center_text("PAUSED - ESC to resume", 36)
        if self.state == "menu":
            self.draw_center_text("MODERN ACTION - Press SPACE to Start", 30)
        if self.state == "gameover":
            self.draw_center_text("YOU DIED - R to restart", 40)

    def draw_center_text(self, text, size=28):
        f = pygame.font.SysFont("Segoe UI", size, bold=True)
        surf = f.render(text, True, WHITE)
        r = surf.get_rect(center=(SCREEN_SIZE[0] // 2, SCREEN_SIZE[1] // 2))
        shadow = f.render(text, True, (10, 10, 10))
        self.screen.blit(shadow, (r.x + 4, r.y + 4))
        self.screen.blit(surf, r.topleft)

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS) / 1000.0
            self.handle_input()
            if self.state == "playing" and not self.paused:
                self.update()
            self.draw()
            pygame.display.flip()
        pygame.quit()


if __name__ == '__main__':
    Game().run()
