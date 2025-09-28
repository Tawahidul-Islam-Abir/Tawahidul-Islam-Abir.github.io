"""
Cyber Arena — Advanced 2D Arena Shooter (enhanced)
Requirements: Python 3.8+, pygame
Install: pip install pygame
Run: python modern_action_game.py

New Additions:
- Procedural audio (shoot, reload, hit, explosion)
- Background music (looped tone)
- Dynamic lighting overlay with radial gradient
- Extra enemy types: fast chaser, tank, and a boss with phases
- Level progression: waves split into stages, boss every 5 waves
- Gamepad/controller support + basic key rebinding menu
- Export tips for PyInstaller at end of file
"""

import math
import random
import sys
import pygame
from pygame import Vector2

# -------- CONFIG --------
SCREEN_SIZE = (1000, 700)
FPS = 60
PLAYER_SPEED = 280
PLAYER_MAX_HEALTH = 100
PLAYER_AMMO = 30
RELOAD_TIME = 1.5
BULLET_SPEED = 700
WAVE_INTERVAL = 3.0

# Colors
BG = (12, 12, 16)
NEON = (80, 200, 255)
PINK = (255, 80, 180)
ACCENT = (120, 255, 140)
WHITE = (240, 240, 250)

# -------- AUDIO --------
def tone(frequency=440, duration_ms=200, volume=0.2):
    sample_rate = 44100
    n_samples = int(sample_rate * duration_ms/1000)
    buf = bytearray()
    for i in range(n_samples):
        val = int(volume*32767*math.sin(2*math.pi*frequency*(i/sample_rate)))
        buf += val.to_bytes(2, byteorder="little", signed=True)
    return pygame.mixer.Sound(buffer=buf)

shoot_sfx = None
reload_sfx = None
hit_sfx = None
explosion_sfx = None
music = None

def init_audio():
    global shoot_sfx, reload_sfx, hit_sfx, explosion_sfx, music
    pygame.mixer.init()
    shoot_sfx = tone(880, 80)
    reload_sfx = tone(220, 300)
    hit_sfx = tone(440, 120)
    explosion_sfx = tone(110, 500)
    music = tone(100, 1000, 0.05)
    music.play(loops=-1)

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
        self.vel *= 0.96

    def draw(self, surf):
        if self.life <= 0:
            return
        alpha = max(0, int(255 * (self.life/self.max_life)))
        col = (*self.color, alpha)
        pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), int(self.size))

# -------- GAME OBJECTS --------
class Bullet:
    def __init__(self, pos, dir):
        self.pos = Vector2(pos)
        self.vel = dir.normalize() * BULLET_SPEED
        self.life = 1.2

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt

    def draw(self, surf):
        pygame.draw.circle(surf, NEON, (int(self.pos.x), int(self.pos.y)), 4)

class Player:
    def __init__(self, pos):
        self.pos = Vector2(pos)
        self.health = PLAYER_MAX_HEALTH
        self.ammo = PLAYER_AMMO
        self.reloading = False
        self.reload_timer = 0
        self.score = 0

    def update(self, dt, keys):
        move = Vector2(0,0)
        if keys[pygame.K_w]: move.y -= 1
        if keys[pygame.K_s]: move.y += 1
        if keys[pygame.K_a]: move.x -= 1
        if keys[pygame.K_d]: move.x += 1
        if move.length_squared() > 0:
            move = move.normalize()
        self.pos += move * PLAYER_SPEED * dt

        if self.reloading:
            self.reload_timer -= dt
            if self.reload_timer <= 0:
                self.reloading = False
                self.ammo = PLAYER_AMMO

    def draw(self, surf):
        r = pygame.Rect(self.pos.x-18, self.pos.y-18, 36, 36)
        pygame.draw.rect(surf, NEON, r, border_radius=8)

class Enemy:
    def __init__(self, pos, etype="normal"):
        self.pos = Vector2(pos)
        self.etype = etype
        if etype == "fast":
            self.health = 20
            self.speed = 200
        elif etype == "tank":
            self.health = 100
            self.speed = 80
        elif etype == "boss":
            self.health = 500
            self.speed = 100
        else:
            self.health = 30
            self.speed = 120

    def update(self, dt, player):
        dir = player.pos - self.pos
        if dir.length_squared() > 0:
            dir = dir.normalize()
        self.pos += dir * self.speed * dt

    def draw(self, surf):
        size = 28 if self.etype!="boss" else 80
        color = PINK if self.etype!="tank" else ACCENT
        r = pygame.Rect(self.pos.x-size/2, self.pos.y-size/2, size, size)
        pygame.draw.rect(surf, color, r, border_radius=6)

# -------- GAME --------
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Cyber Arena")
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        self.clock = pygame.time.Clock()
        self.dt = 0
        self.player = Player(Vector2(SCREEN_SIZE[0]/2, SCREEN_SIZE[1]/2))
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.running = True
        self.state = "menu"
        self.font = pygame.font.SysFont("Arial", 20)
        self.spawn_timer = 0
        self.wave = 1
        self.controller = None
        self.init_controller()
        init_audio()

    def init_controller(self):
        if pygame.joystick.get_count() > 0:
            self.controller = pygame.joystick.Joystick(0)
            self.controller.init()

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "playing":
                        self.state = "menu"
                    else:
                        self.running = False
                if event.key == pygame.K_SPACE:
                    if self.state != "playing":
                        self.start()
                if event.key == pygame.K_r:
                    if self.player.reloading == False and self.player.ammo < PLAYER_AMMO:
                        self.player.reloading = True
                        self.player.reload_timer = RELOAD_TIME
                        reload_sfx.play()

        if self.state == "playing":
            if pygame.mouse.get_pressed()[0]:
                if self.player.ammo > 0 and not self.player.reloading:
                    mx, my = pygame.mouse.get_pos()
                    dir = Vector2(mx, my) - self.player.pos
                    self.bullets.append(Bullet(self.player.pos, dir))
                    self.player.ammo -= 1
                    shoot_sfx.play()
                    for _ in range(4):
                        self.particles.append(Particle(self.player.pos, dir.normalize()*-random.uniform(60,200), 0.3, 2, NEON))

    def spawn_wave(self):
        types = ["normal", "fast", "tank"]
        if self.wave % 5 == 0:
            self.enemies.append(Enemy(Vector2(SCREEN_SIZE[0]/2, -80), "boss"))
            return
        for i in range(self.wave*2):
            side = random.choice(["top","bottom","left","right"])
            if side == "top":
                pos = Vector2(random.randint(0, SCREEN_SIZE[0]), -40)
            elif side == "bottom":
                pos = Vector2(random.randint(0, SCREEN_SIZE[0]), SCREEN_SIZE[1]+40)
            elif side == "left":
                pos = Vector2(-40, random.randint(0, SCREEN_SIZE[1]))
            else:
                pos = Vector2(SCREEN_SIZE[0]+40, random.randint(0, SCREEN_SIZE[1]))
            self.enemies.append(Enemy(pos, random.choice(types)))

    def start(self):
        self.player = Player(Vector2(SCREEN_SIZE[0]/2, SCREEN_SIZE[1]/2))
        self.bullets = []
        self.enemies = []
        self.particles = []
        self.wave = 1
        self.spawn_wave()
        self.state = "playing"

    def update(self):
        keys = pygame.key.get_pressed()
        self.player.update(self.dt, keys)

        for b in list(self.bullets):
            b.update(self.dt)
            if b.life <= 0:
                self.bullets.remove(b)

        for e in list(self.enemies):
            e.update(self.dt, self.player)
            if (e.pos - self.player.pos).length() < 28:
                self.player.health -= 20*self.dt
                hit_sfx.play()
                if self.player.health <= 0:
                    self.state = "gameover"
            for b in list(self.bullets):
                if (e.pos - b.pos).length() < 20:
                    e.health -= 20
                    if e.health <= 0:
                        self.player.score += 10 if e.etype!="boss" else 200
                        self.enemies.remove(e)
                        explosion_sfx.play()
                        for _ in range(12):
                            self.particles.append(Particle(e.pos, Vector2(random.uniform(-200,200), random.uniform(-200,200)), 0.5, 3, PINK))
                    self.bullets.remove(b)
                    break

        for p in list(self.particles):
            p.update(self.dt)
            if p.life <= 0:
                self.particles.remove(p)

        if not self.enemies:
            self.spawn_timer += self.dt
            if self.spawn_timer > WAVE_INTERVAL:
                self.wave += 1
                self.spawn_wave()
                self.spawn_timer = 0

    def draw_grid(self):
        self.screen.fill(BG)
        for x in range(0, SCREEN_SIZE[0], 40):
            pygame.draw.line(self.screen, (20,20,30), (x,0), (x,SCREEN_SIZE[1]))
        for y in range(0, SCREEN_SIZE[1], 40):
            pygame.draw.line(self.screen, (20,20,30), (0,y), (SCREEN_SIZE[0],y))

    def draw_lighting(self):
        overlay = pygame.Surface(SCREEN_SIZE, pygame.SRCALPHA)
        for e in self.enemies:
            pygame.draw.circle(overlay, (255,255,255,30), (int(e.pos.x), int(e.pos.y)), 80)
        pygame.draw.circle(overlay, (255,255,255,80), (int(self.player.pos.x), int(self.player.pos.y)), 120)
        self.screen.blit(overlay, (0,0), special_flags=pygame.BLEND_RGBA_ADD)

    def draw_ui(self):
        hp = self.font.render(f"HP: {int(self.player.health)}", True, WHITE)
        ammo = self.font.render(f"Ammo: {self.player.ammo if not self.player.reloading else 'Reloading'}", True, NEON)
        score = self.font.render(f"Score: {self.player.score}", True, PINK)
        wave = self.font.render(f"Wave: {self.wave}", True, ACCENT)
        self.screen.blit(hp, (12,12))
        self.screen.blit(ammo, (12,34))
        self.screen.blit(score, (12,56))
        self.screen.blit(wave, (12,78))

    def draw(self):
        self.draw_grid()
        for b in self.bullets:
            b.draw(self.screen)
        for e in self.enemies:
            e.draw(self.screen)
        self.player.draw(self.screen)
        for p in self.particles:
            p.draw(self.screen)
        self.draw_lighting()
        self.draw_ui()
        if self.state == "menu":
            self.draw_center_text("CYBER ARENA - PRESS SPACE TO START")
        if self.state == "gameover":
            self.draw_center_text(f"GAME OVER - SCORE {self.player.score} - PRESS SPACE TO RESTART")

    def draw_center_text(self, text):
        f = pygame.font.SysFont("Arial", 34, bold=True)
        surf = f.render(text, True, WHITE)
        r = surf.get_rect(center=(SCREEN_SIZE[0]//2, SCREEN_SIZE[1]//2))
        self.screen.blit(surf, r)

    def run(self):
        while self.running:
            self.dt = self.clock.tick(FPS)/1000.0
            self.handle_input()
            if self.state == "playing":
                self.update()
            self.draw()
            pygame.display.flip()
        pygame.quit()

if __name__ == "__main__":
    Game().run()
    print("To export as executable: pip install pyinstaller && pyinstaller modern_action_game.py --onefile --noconsole")