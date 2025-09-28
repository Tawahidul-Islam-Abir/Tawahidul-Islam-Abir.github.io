# pubg_proto.py
from ursina import *
from ursina.prefabs.first_person_controller import FirstPersonController
import random
import math

app = Ursina()

# --- Lighting & environment ---
window.title = "PUBG-like Prototype (Ursina)"
Sky()
DirectionalLight(rotation=Vec3(45, -30, 0), shadows=True)
ground = Entity(model='plane', scale=(200,200,1), texture='grass', collider='box', texture_scale=(40,40))

# --- Player (first-person) ---
player = FirstPersonController()
player.speed = 7
player.gravity = 0.5
player.cursor.visible = True
player.jump_height = 1.8
player.health = 100
player.weapon = 'Pistol'
player.ammo = 18

# --- HUD ---
health_text = Text(f'HP: {player.health}', position=Vec2(-0.85,0.42), scale=1.5)
ammo_text = Text(f'{player.weapon} Ammo: {player.ammo}', position=Vec2(0.7,0.42), scale=1.2)
crosshair = Entity(model='quad', color=color.white, scale=.01, always_on_top=True)

# --- Weapon / shooting ---
bullet_speed = 100
bullets = []

class Bullet(Entity):
    def __init__(self, position, direction):
        super().__init__(
            model='sphere',
            scale=0.08,
            color=color.yellow,
            position=position,
            collider='sphere',
            double_sided=True
        )
        self.direction = direction.normalized()
    def update(self):
        self.position += self.direction * bullet_speed * time.dt
        # despawn far away bullets
        if distance(self.position, player.position) > 200:
            destroy(self)

# --- Enemies ---
enemies = []
def spawn_enemy(pos=None):
    if pos is None:
        pos = Vec3(random.uniform(-40,40),1, random.uniform(-40,40))
    e = Entity(model='cube', color=color.rgb(200,50,50), scale=(1,2,1), collider='box', position=pos)
    e.health = 40
    e.walk_speed = random.uniform(1.2, 3)
    enemies.append(e)
    return e

for _ in range(8):
    spawn_enemy()

# --- Simple loot (ammo pickups) ---
pickups = []
def spawn_pickup(pos=None):
    if pos is None:
        pos = Vec3(random.uniform(-40,40),0.5, random.uniform(-40,40))
    p = Entity(model='sphere', color=color.azure, scale=0.6, position=pos, collider='sphere')
    p.kind = 'ammo'
    pickups.append(p)
    return p

for _ in range(6):
    spawn_pickup()

# --- Helper functions ---
def distance(a,b):
    return math.sqrt((a.x-b.x)**2 + (a.y-b.y)**2 + (a.z-b.z)**2)

# --- Shoot handling ---
def input(key):
    if key == 'left mouse down':
        if player.ammo > 0:
            player.ammo -= 1
            ammo_text.text = f'{player.weapon} Ammo: {player.ammo}'
            # spawn bullet from camera
            origin = camera.world_position + camera.forward * 1.2
            dir = camera.forward
            b = Bullet(position=origin, direction=dir)
            bullets.append(b)
        else:
            # click - empty
            pass
    if key == 'r':
        player.ammo = 18
        ammo_text.text = f'{player.weapon} Ammo: {player.ammo}'

# --- Update loop ---
def update():
    # update HUD health
    health_text.text = f'HP: {player.health}'
    # bullets collision vs enemies
    for b in bullets[:]:
        for e in enemies[:]:
            if b.intersects(e).hit:
                e.health -= 20
                try:
                    destroy(b)
                    bullets.remove(b)
                except:
                    pass
                if e.health <= 0:
                    # create ragdoll-ish effect and remove
                    explosion = Entity(model='sphere', color=color.orange, scale=2, position=e.position, lifespan=0.35)
                    enemies.remove(e)
                    destroy(e)
                    # spawn another enemy after delay
                    invoke(spawn_enemy, delay=2)
                break

    # simple enemy AI: wander + chase if close
    for e in enemies:
        d = distance(e.position, player.position)
        if d < 12:
            # chase
            dir = (player.position - e.position).normalized()
            e.position += dir * e.walk_speed * time.dt
        else:
            # wander randomly
            if not hasattr(e, 'target') or distance(e.position, e.target) < 1:
                e.target = Vec3(random.uniform(-40,40),1, random.uniform(-40,40))
            dir = (e.target - e.position).normalized()
            e.position += dir * (e.walk_speed * 0.6) * time.dt

    # pickups
    for p in pickups[:]:
        if p.intersects(player).hit:
            if p.kind == 'ammo':
                player.ammo += 12
                ammo_text.text = f'{player.weapon} Ammo: {player.ammo}'
            pickups.remove(p)
            destroy(p)
            invoke(spawn_pickup, delay=5)

    # player hit if enemy too close (simple)
    for e in enemies:
        if distance(e.position, player.position) < 1.5:
            player.health -= 20 * time.dt  # continuous damage
            if player.health <= 0:
                # respawn
                player.health = 100
                player.position = Vec3(0,2,0)
                # clear enemies and respawn a few
                for en in enemies[:]:
                    destroy(en)
                enemies.clear()
                for _ in range(6):
                    spawn_enemy()

    # small crosshair bob
    crosshair.rotation_z = math.sin(time.time()) * 1.2

# --- Debug camera toggle ---
def toggle_debug():
    if mouse.middle:
        from ursina.prefabs.orbit_camera import EditorCamera
        EditorCamera(position=(20,20,20))

# run
app.run()
