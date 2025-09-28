"""
Neon Runner — Modern Endless Runner (single-file)
Requirements: Python 3.8+, pygame
Install: pip install pygame
Run: python modern_action_game.py

This replaces the previous action demo with a different game: an endless side-scrolling neon runner.
Features:
- Smooth platforming with run, jump, double-jump, and dash
- Procedural parallax background and neon particle effects
- Obstacles, collectible orbs, and score/combos
- Simple level generator (endless) with difficulty ramping
- Pause, restart, and crisp UI
- All visuals are procedural (no external assets required)

Controls:
- Move right automatically (camera scrolls)
- Jump: SPACE or W
- Dash (air/stamina): LSHIFT
- Pause: ESC
"""


import random

import pygame
from pygame import Vector2

# -------- CONFIG --------
SCREEN_SIZE = (1100, 600)
FPS = 60
GRAVITY = 2200
PLAYER_RUN_SPEED = 320
JUMP_V = -740
DASH_SPEED = 700
DASH_TIME = 0.18
MAX_DOUBLE_JUMP = 1
SPAWN_INTERVAL = 1.0

# Colors
BG = (12, 12, 16)
NEON = (80, 200, 255)
PINK = (255, 88, 200)
ACCENT = (120, 255, 140)
WHITE = (240, 240, 250)

# -------- UTIL --------

def clamp(a, b, c):
    return max(b, min(c, a))


# -------- PARTICLES --------
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
        self.vel *= 0.98

    def draw(self, surf):
        if self.life <= 0:
            return
        a = clamp(self.life / self.max_life, 0, 1)
        r = int(self.size * (0.6 + 0.4 * a))
        col = tuple(int(c * (0.35 + 0.65 * a)) for c in self.color)
        pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), r)


# -------- GAME OBJECTS --------
class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.vel = Vector2(0, 0)
        self.on_ground = False
        self.double_jumps = MAX_DOUBLE_JUMP
        self.width = 44
        self.height = 56
        self.color = NEON
        self.dashing = False
        self.dash_timer = 0
        self.stamina = 1.0
        self.score = 0
        self.combo = 0

    def rect(self):
        return pygame.Rect(self.pos.x - self.width/2, self.pos.y - self.height, self.width, self.height)

    def jump(self):
        if self.on_ground:
            self.vel.y = JUMP_V
            self.on_ground = False
            self.double_jumps = MAX_DOUBLE_JUMP
            return True
        elif self.double_jumps > 0:
            self.vel.y = JUMP_V * 0.9
            self.double_jumps -= 1
            return True
        return False

    def start_dash(self):
        if self.stamina > 0.15 and not self.dashing:
            self.dashing = True
            self.dash_timer = DASH_TIME
            self.stamina -= 0.35
            return True
        return False

    def update(self, dt):
        # gravity
        if not self.on_ground:
            self.vel.y += GRAVITY * dt
        # dash mechanics
        if self.dashing:
            self.dash_timer -= dt
            self.vel.x = DASH_SPEED
            if self.dash_timer <= 0:
                self.dashing = False
        else:
            # run forward at fixed speed
            self.vel.x = PLAYER_RUN_SPEED
            # stamina regen
            self.stamina = clamp(self.stamina + dt * 0.25, 0.0, 1.0)
        self.pos += self.vel * dt

    def draw(self, surf, cam_x):
        r = self.rect()
        r.x -= cam_x
        # neon rectangle with glow
        glow = pygame.Surface((r.width+16, r.height+16), pygame.SRCALPHA)
        for i in range(6, 0, -1):
            a = int(40 * (i/6))
            pygame.draw.rect(glow, (*self.color, a), (8-i, 8-i, r.width + i*2, r.height + i*2), border_radius=8)
        surf.blit(glow, (r.x-8, r.y-8), special_flags=pygame.BLEND_ADD)
        pygame.draw.rect(surf, self.color, r, border_radius=6)
        # eyes
        eye_w = 6
        eye_h = 10
        left = (r.x + r.width*0.28, r.y + r.height*0.3)
        right = (r.x + r.width*0.72 - eye_w, r.y + r.height*0.3)
        pygame.draw.rect(surf, WHITE, (*left, eye_w, eye_h))
        pygame.draw.rect(surf, WHITE, (*right, eye_w, eye_h))


class Platform:
    def __init__(self, x, y, w, h=24, color=None):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.color = color or (30, 30, 40)

    def rect(self):
        return pygame.Rect(self.x, self.y, self.w, self.h)

    def draw(self, surf, cam_x):
        r = self.rect().copy()
        r.x -= cam_x
        pygame.draw.rect(surf, self.color, r)
        # neon edge
        pygame.draw.rect(surf, PINK, r, 2)


class Obstacle:
    def __init__(self, x, y, size=36):
        self.pos = Vector2(x, y)
        self.size = size

    def rect(self):
        return pygame.Rect(self.pos.x - self.size/2, self.pos.y - self.size, self.size, self.size)

    def draw(self, surf, cam_x):
        r = self.rect()
        r.x -= cam_x
        # spiky neon
        pygame.draw.polygon(surf, PINK, [(r.x, r.y+r.height), (r.x+r.width/2, r.y), (r.x+r.width, r.y+r.height)])


class Orb:
    def __init__(self, x, y):
        self.pos = Vector2(x, y)
        self.radius = 10

    def draw(self, surf, cam_x):
        p = (int(self.pos.x - cam_x), int(self.pos.y))
        for s in range(4, 0, -1):
            a = int(30 * (s/4))
            pygame.draw.circle(surf, (*ACCENT, a), p, self.radius + s)
        pygame.draw.circle(surf, ACCENT, p, self.radius)


# -------- LEVEL GENERATION --------
class Level:
    def __init__(self):
        self.platforms = []
        self.obstacles = []
        self.orbs = []
        self.farthest_x = 0
        self.difficulty = 0.0
        self.reset()

    def reset(self):
        self.platforms = []
        self.obstacles = []
        self.orbs = []
        self.farthest_x = -100
        self.difficulty = 0.0
        # starting ground
        self.add_platform(-200, 460, 1400)
        # initial platforms
        x = 600
        for i in range(6):
            h = 380 - i*20
            self.add_platform(x, h, 220)
            x += 300

    def add_platform(self, x, y, w):
        p = Platform(x, y, w)
        self.platforms.append(p)
        self.farthest_x = max(self.farthest_x, x + w)

    def add_obstacle(self, x, y):
        self.obstacles.append(Obstacle(x, y))

    def add_orb(self, x, y):
        self.orbs.append(Orb(x, y))

    def update(self, player_x):
        # increase difficulty as player progresses
        self.difficulty = player_x / 1200.0
        # generate until farthest_x is sufficiently ahead
        while self.farthest_x < player_x + 1600:
            gap = clamp(180 + random.randint(-40, 60) - int(self.difficulty*60), 100, 380)
            next_w = clamp(120 + random.randint(-30, 60) - int(self.difficulty*30), 80, 340)
            next_h = clamp(360 - int(self.difficulty*80) + random.randint(-70, 70), 220, 460)
            self.add_platform(self.farthest_x + gap, next_h, next_w)
            # obstacles occasionally
            if random.random() < 0.45 + self.difficulty*0.25:
                ox = self.farthest_x + gap + next_w*0.5
                oy = next_h
                self.add_obstacle(ox, oy)
            # orbs
            if random.random() < 0.6:
                self.add_orb(self.farthest_x + gap + random.randint(40, next_w-40), next_h - 40)

    def cleanup(self, cam_x):
        # remove objects that are far left of camera
        left_bound = cam_x - 400
        self.platforms = [p for p in self.platforms if p.x + p.w > left_bound]
        self.obstacles = [o for o in self.obstacles if o.pos.x > left_bound]
        self.orbs = [o for o in self.orbs if o.pos.x > left_bound]

    def draw(self, surf, cam_x):
        for p in self.platforms:
            p.draw(surf, cam_x)
        for o in self.obstacles:
            o.draw(surf, cam_x)
        for b in self.orbs:
            b.draw(surf, cam_x)


# -------- GAME --------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Neon Runner")
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        self.clock = pygame.time.Clock()
        self.dt = 0
        self.player = Player(Vector2(220, 320))
        self.level = Level()
        self.particles = []
        self.cam_x = 0
        self.running = True
        self.paused = False
        self.state = "menu"  # menu, playing, gameover
        self.font = pygame.font.SysFont("Arial", 20)
        self.spawn_timer = 0

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == 'playing':
                        self.paused = not self.paused
                    else:
                        self.running = False
                if event.key == pygame.K_SPACE or event.key == pygame.K_w:
                    if self.state == 'menu':
                        self.start()
                    elif self.state == 'gameover':
                        self.start()
                    else:
                        jumped = self.player.jump()
                        if jumped:
                            for _ in range(12):
                                self.particles.append(Particle(self.player.pos + Vector2(random.uniform(-6,6), 18), Vector2(random.uniform(-120,120), random.uniform(-280,-60)), random.uniform(0.4,0.9), random.uniform(2,5), PINK))
                if event.key == pygame.K_LSHIFT:
                    if self.state == 'playing':
                        dashed = self.player.start_dash()
                        if dashed:
                            for _ in range(16):
                                self.particles.append(Particle(self.player.pos + Vector2(0, 10), Vector2(random.uniform(-280,280), random.uniform(-120,120)), random.uniform(0.2,0.5), random.uniform(2,6), NEON))

    def start(self):
        self.player = Player(Vector2(220, 320))
        self.level = Level()
        self.particles = []
        self.cam_x = 0
        self.state = 'playing'
        self.paused = False

    def update(self):
        if self.state != 'playing' or self.paused:
            return
        self.player.update(self.dt)
        # camera follows player x
        self.cam_x = self.player.pos.x - 220
        # update level
        self.level.update(self.player.pos.x)
        self.level.cleanup(self.cam_x)
        # collisions with platforms
        self.player.on_ground = False
        pr = self.player.rect()
        for p in self.level.platforms:
            r = p.rect()
            if pr.colliderect(r):
                # simple resolution - place player on top if falling
                if self.player.vel.y > 0 and pr.bottom - self.player.vel.y * self.dt <= r.top + 6:
                    self.player.pos.y = r.top
                    self.player.vel.y = 0
                    self.player.on_ground = True
                    self.player.double_jumps = MAX_DOUBLE_JUMP
        # obstacle collision
        for o in list(self.level.obstacles):
            if pr.colliderect(o.rect()):
                self.state = 'gameover'
        # orb pickup
        for orb in list(self.level.orbs):
            if (Vector2(orb.pos) - self.player.pos).length() < 44:
                self.player.score += 10
                self.player.combo += 1
                self.level.orbs.remove(orb)
                for _ in range(10):
                    self.particles.append(Particle(orb.pos, Vector2(random.uniform(-120,120), random.uniform(-200,-40)), random.uniform(0.3,0.8), random.uniform(2,5), ACCENT))
        # particle updates
        for p in list(self.particles):
            p.update(self.dt)
            if p.life <= 0:
                self.particles.remove(p)
        # slightly move player forward if dashing
        if not self.player.dashing:
            # ensure player keeps running speed
            pass
        # small camera shake on high combo
        if self.player.combo > 0 and random.random() < 0.01:
            self.particles.append(Particle(self.player.pos + Vector2(random.uniform(-8,8), random.uniform(-8,8)), Vector2(random.uniform(-120,120), random.uniform(-120,120)), 0.4, random.uniform(2,5), PINK))

    def draw_background(self):
        self.screen.fill(BG)
        # parallax bands
        w, h = SCREEN_SIZE
        for i, depth in enumerate([0.2, 0.45, 0.75]):
            offset = int((self.cam_x * depth) % 700)
            for x in range(-700, w+700, 140):
                cx = x - offset
                y = 120 + i*90
                pygame.draw.circle(self.screen, (20 + i*6, 18 + i*6, 28 + i*6), (cx, y), 60)
        # horizon line
        pygame.draw.rect(self.screen, (18,18,24), (0, 460, w, h-460))

    def draw_ui(self):
        # top-left score
        score_surf = self.font.render(f"Score: {self.player.score}", True, WHITE)
        self.screen.blit(score_surf, (18, 12))
        combo_surf = self.font.render(f"Combo: {self.player.combo}", True, PINK)
        self.screen.blit(combo_surf, (18, 40))
        # stamina
        pygame.draw.rect(self.screen, (30,30,36), (18, 70, 200, 12), border_radius=6)
        pygame.draw.rect(self.screen, NEON, (18, 70, int(200*self.player.stamina), 12), border_radius=6)

    def draw(self):
        self.draw_background()
        # level geometry
        self.level.draw(self.screen, self.cam_x)
        # particles
        for p in self.particles:
            p.draw(self.screen)
        # player
        self.player.draw(self.screen, self.cam_x)
        # UI
        self.draw_ui()
        if self.state == 'menu':
            self.draw_center_text('NEON RUNNER - PRESS SPACE TO START', 34)
        if self.paused:
            self.draw_center_text('PAUSED - ESC TO RESUME', 32)
        if self.state == 'gameover':
            self.draw_center_text(f'GAME OVER - SCORE {self.player.score}  - PRESS SPACE TO RESTART', 26)

    def draw_center_text(self, text, size=28):
        f = pygame.font.SysFont('Arial', size, bold=True)
        surf = f.render(text, True, WHITE)
        r = surf.get_rect(center=(SCREEN_SIZE[0]//2, SCREEN_SIZE[1]//2))
        shadow = f.render(text, True, (4,4,6))
        self.screen.blit(shadow, (r.x+4, r.y+4))
        self.screen.blit(surf, r.topleft)

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS)/1000.0
            self.handle_input()
            if self.state == 'playing' and not self.paused:
                self.update()
            self.draw()
            pygame.display.flip()
        pygame.quit()


if __name__ == '__main__':
    Game().run()
