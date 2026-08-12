"""
Subway Surfers-style endless runner -- 3D Perspective Fitness Build (Human Timing Window).
"""

import math
import random
import sys
from dataclasses import dataclass

import pygame

# ---------------------------------------------------------------------------
# Config & 3D Perspective Constants
# ---------------------------------------------------------------------------
WIDTH, HEIGHT = 420, 700
LANE_COUNT = 3

VANISH_X = WIDTH // 2
VANISH_Y = 220  
START_Y = 240   
GROUND_Y = 620  

PLAYER_BASE_W, PLAYER_BASE_H = 80, 110
DUCK_BASE_H = 65

GRAVITY = 96.0            
JUMP_VELOCITY = -1320.0   
DUCK_DURATION = 0.46      

# Time configurations (Measured in seconds)
EASY_DURATION = 5.0 * 60.0    
MED_DURATION = 7.0 * 60.0     
FAST_DURATION = 3.0 * 60.0    
ACTIVE_CYCLE_TIME = EASY_DURATION + MED_DURATION + FAST_DURATION

BREAK_DURATION = 45.0         
TOTAL_CYCLE_TIME = ACTIVE_CYCLE_TIME + BREAK_DURATION

# Subway Surfers style curve bounds
SPEED_START = 2.56            
SPEED_MAX = 5.0               

FPS = 60

CAL_PER_JUMP = 0.25
CAL_PER_SQUAT = 0.32
CAL_PER_SECOND_ACTIVE = 0.045

WHITE = (222, 224, 228)     
DIM_WHITE = (168, 170, 180)
LANE_LINE = (80, 83, 100)

SHIRT_COLOR = (78, 150, 205)    
SHIRT_SHADOW = (52, 108, 155)
SHORTS_COLOR = (48, 58, 82)
SKIN_COLOR = (230, 188, 150)
HAIR_COLOR = (58, 44, 40)

CRATE_COLOR = (165, 90, 78)     
CRATE_LIGHT = (190, 112, 98)
HAZARD_ACCENT = (215, 175, 70)  
WHEEL_COLOR = (40, 40, 45)

BAR_COLOR = (205, 172, 80)      
BAR_LIGHT = (222, 195, 120)
POLE_COLOR = (110, 110, 122)

COIN_COLOR = (218, 178, 70)
COIN_SHADOW = (170, 132, 45)
COIN_SHINE = (238, 220, 175)


def project_3d(lane, z, local_y_offset=0.0):
    factor = 1.0 - z
    screen_y = VANISH_Y + (GROUND_Y - VANISH_Y) * factor
    
    lane_width_at_z = (WIDTH * 1.3) * factor
    left_bound = VANISH_X - lane_width_at_z / 2
    lane_step = lane_width_at_z / LANE_COUNT
    
    screen_x = left_bound + (lane + 0.5) * lane_step
    screen_y -= local_y_offset * factor
    
    return int(screen_x), int(screen_y), factor


# ---------------------------------------------------------------------------
# Input layer
# ---------------------------------------------------------------------------
@dataclass
class ActionState:
    move_left: bool = False
    move_right: bool = False
    jump: bool = False
    duck: bool = False


class InputProvider:
    def poll(self, events) -> ActionState:
        raise NotImplementedError


class KeyboardInput(InputProvider):
    def poll(self, events) -> ActionState:
        state = ActionState()
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_a):
                    state.move_left = True
                elif event.key in (pygame.K_RIGHT, pygame.K_d):
                    state.move_right = True
                elif event.key in (pygame.K_UP, pygame.K_w, pygame.K_SPACE):
                    state.jump = True
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    state.duck = True
        return state


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------
class Player:
    def __init__(self):
        self.lane = 1.0  
        self.target_lane = 1
        self.y_offset = 0.0
        self.vel_y = 0.0
        self.jumping = False
        self.duck_timer = 0.0
        self.run_animation_tick = 0.0  

    @property
    def height_profile(self):
        return DUCK_BASE_H if self.duck_timer > 0.0 else PLAYER_BASE_H

    def apply(self, action: ActionState, is_break: bool):
        jumped = False
        ducked = False
        if is_break:
            return jumped, ducked
            
        if action.move_left and self.target_lane > 0:
            self.target_lane -= 1
        if action.move_right and self.target_lane < LANE_COUNT - 1:
            self.target_lane += 1
        if action.jump and not self.jumping and self.duck_timer <= 0.0:
            self.jumping = True
            self.vel_y = JUMP_VELOCITY
            jumped = True
        if action.duck and not self.jumping and self.duck_timer <= 0.0:
            self.duck_timer = DUCK_DURATION
            ducked = True
        return jumped, ducked

    def update(self, dt, current_speed_ratio, is_break: bool):
        self.lane += (self.target_lane - self.lane) * (1.0 - math.exp(-15 * dt))

        if self.jumping:
            self.y_offset -= self.vel_y * dt
            self.vel_y += GRAVITY * 60.0 * dt
            if self.y_offset <= 0.0:
                self.y_offset = 0.0
                self.jumping = False
                self.vel_y = 0.0

        if self.duck_timer > 0.0:
            self.duck_timer -= dt

        if not self.jumping and self.duck_timer <= 0.0 and not is_break:
            self.run_animation_tick += dt * 20.0 * current_speed_ratio

    def draw(self, surf):
        cx, cy, scale = project_3d(self.lane, 0.05, self.y_offset)
        
        w = int(PLAYER_BASE_W * scale)
        h = int(self.height_profile * scale)
        top, bottom = cy - h, cy

        pose = "jump" if self.jumping else ("duck" if self.duck_timer > 0.0 else "run")

        # --- legs ---
        leg_w = max(4, int(8 * scale))
        if pose == "run":
            offset = int(math.sin(self.run_animation_tick) * (12 * scale))
            pygame.draw.line(surf, SHORTS_COLOR, (cx - 9, bottom - 4), (cx - 9 + offset, bottom + int(14 * scale)), leg_w)
            pygame.draw.line(surf, SHORTS_COLOR, (cx + 9, bottom - 4), (cx + 9 - offset, bottom + int(14 * scale)), leg_w)
        elif pose == "jump":
            pygame.draw.line(surf, SHORTS_COLOR, (cx - 9, bottom - 4), (cx - int(15 * scale), bottom + int(8 * scale)), leg_w)
            pygame.draw.line(surf, SHORTS_COLOR, (cx + 9, bottom - 4), (cx + int(15 * scale), bottom + int(8 * scale)), leg_w)
        else:
            pygame.draw.line(surf, SHORTS_COLOR, (cx - 9, bottom - 2), (cx - int(13 * scale), bottom + int(6 * scale)), leg_w)
            pygame.draw.line(surf, SHORTS_COLOR, (cx + 9, bottom - 2), (cx + int(13 * scale), bottom + int(6 * scale)), leg_w)

        # --- torso ---
        torso_h = int((bottom - top) * 0.65)
        torso_rect = pygame.Rect(cx - w // 2 + 4, bottom - torso_h, w - 8, torso_h)
        pygame.draw.rect(surf, SHIRT_SHADOW, torso_rect.move(0, 3), border_radius=6)
        pygame.draw.rect(surf, SHIRT_COLOR, torso_rect, border_radius=6)

        # --- arms ---
        arm_w = max(3, int(6 * scale))
        if pose == "run":
            offset = int(math.sin(self.run_animation_tick + math.pi) * (10 * scale))
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.left, torso_rect.top + 6), (torso_rect.left - 5, torso_rect.top + 6 + offset), arm_w)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.right, torso_rect.top + 6), (torso_rect.right + 5, torso_rect.top + 6 - offset), arm_w)
        elif pose == "jump":
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.left, torso_rect.top + 4), (torso_rect.left - 7, torso_rect.top - int(12 * scale)), arm_w)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.right, torso_rect.top + 4), (torso_rect.right + 7, torso_rect.top - int(12 * scale)), arm_w)
        else:
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.left, torso_rect.top + 4), (torso_rect.left - 7, torso_rect.top + int(10 * scale)), arm_w)
            pygame.draw.line(surf, SKIN_COLOR, (torso_rect.right, torso_rect.top + 4), (torso_rect.right + 7, torso_rect.top + int(10 * scale)), arm_w)

        # --- head ---
        head_r = max(6, int(w * 0.25))
        head_center = (cx, torso_rect.top - head_r + 3)
        pygame.draw.circle(surf, HAIR_COLOR, (head_center[0], head_center[1] - int(head_r * 0.3)), int(head_r * 1.1))
        pygame.draw.circle(surf, SKIN_COLOR, head_center, head_r)


class Obstacle:
    def __init__(self, lane, kind, z):
        self.lane = lane
        self.kind = kind
        self.z = float(z)
        self.dodged = False  # NEW: Prevents duplicate triggers inside the timing window

    def get_hitbox(self):
        cx, cy, scale = project_3d(self.lane, self.z)
        if self.kind == "ground":
            w = int(90 * scale)
            h = int(45 * scale)
            return pygame.Rect(cx - w // 2, cy - h, w, h)
        else:
            w = int(100 * scale)
            h = int(24 * scale)
            return pygame.Rect(cx - w // 2, cy - int(105 * scale), w, h)

    def draw(self, surf):
        cx, cy, scale = project_3d(self.lane, self.z)
        rect = self.get_hitbox()

        if self.kind == "ground":
            pygame.draw.rect(surf, CRATE_COLOR, rect, border_radius=max(2, int(6 * scale)))
            pygame.draw.rect(surf, CRATE_LIGHT, rect.inflate(-int(10 * scale), -int(12 * scale)), border_radius=max(1, int(4 * scale)))
            accent_rect = pygame.Rect(rect.left + int(6 * scale), rect.centery - int(2 * scale), rect.width - int(12 * scale), max(2, int(5 * scale)))
            pygame.draw.rect(surf, HAZARD_ACCENT, accent_rect, border_radius=2)
        else:
            p_left_x, p_left_y, _ = project_3d(self.lane - 0.42, self.z)
            p_right_x, p_right_y, _ = project_3d(self.lane + 0.42, self.z)
            
            pygame.draw.line(surf, POLE_COLOR, (p_left_x, rect.top), (p_left_x, p_left_y), max(2, int(5 * scale)))
            pygame.draw.line(surf, POLE_COLOR, (p_right_x, rect.top), (p_right_x, p_right_y), max(2, int(5 * scale)))
            
            pygame.draw.rect(surf, BAR_COLOR, rect, border_radius=max(2, int(5 * scale)))
            pygame.draw.rect(surf, BAR_LIGHT, rect.inflate(-int(10 * scale), -int(6 * scale)), border_radius=max(1, int(3 * scale)))


class Coin:
    def __init__(self, lane, z):
        self.lane = lane
        self.z = float(z)
        self.collected = False

    def draw(self, surf):
        if self.collected:
            return
        cx, cy, scale = project_3d(self.lane, self.z)
        cy -= int(14 * scale)
        
        t = pygame.time.get_ticks() * 0.0025 + cx * 0.05
        pulse = 1.0 + 0.08 * math.sin(t)
        r = max(4, int(13 * scale * pulse))
        
        pygame.draw.circle(surf, COIN_SHADOW, (cx, cy), r + max(1, int(2 * scale)))
        pygame.draw.circle(surf, COIN_COLOR, (cx, cy), r)
        pygame.draw.circle(surf, COIN_SHINE, (cx - r // 3, cy - r // 3), max(1, r // 3))


# ---------------------------------------------------------------------------
# Game
# ---------------------------------------------------------------------------
class Game:
    def __init__(self, input_provider: InputProvider):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Subway Surfers Clone")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("arial", 24, bold=True)
        self.small_font = pygame.font.SysFont("arial", 18, bold=True)
        self.big_font = pygame.font.SysFont("arial", 44, bold=True)

        self.input_provider = input_provider
        self.reset()

    def reset(self):
        self.player = Player()
        self.obstacles = []
        self.coins = []
        self.score = 0.0
        self.coins_collected = 0  
        self.time_elapsed = 0.0
        self.game_over = False
        
        self.highest_occupied_z = 1.0  
        self.jump_count = 0
        self.squat_count = 0

    def calories_burned(self):
        return (
            self.jump_count * CAL_PER_JUMP
            + self.squat_count * CAL_PER_SQUAT
            + self.time_elapsed * CAL_PER_SECOND_ACTIVE
        )

    def get_formatted_time(self):
        minutes = int(self.time_elapsed) // 60
        seconds = int(self.time_elapsed) % 60
        return f"{minutes:02d}:{seconds:02d}"

    def spawn_batch(self):
        lane = random.randint(0, LANE_COUNT - 1)
        kind = random.choice(["ground", "overhead"])
        
        base_z = self.highest_occupied_z + random.uniform(0.6, 1.2)
        self.obstacles.append(Obstacle(lane, kind, base_z))

        coin_count = random.randint(3, 5)
        coin_lane = random.choice([l for l in range(LANE_COUNT) if l != lane])
        for i in range(coin_count):
            self.coins.append(Coin(coin_lane, base_z + (i * 0.12)))

        self.highest_occupied_z = base_z + (coin_count * 0.12)

    def get_current_level_info(self):
        cycle_position = self.time_elapsed % TOTAL_CYCLE_TIME
        
        if cycle_position < ACTIVE_CYCLE_TIME:
            progress_ratio = cycle_position / ACTIVE_CYCLE_TIME
            current_speed = SPEED_START + (SPEED_MAX - SPEED_START) * progress_ratio
            
            if cycle_position < EASY_DURATION:
                label = "Easy"
            elif cycle_position < (EASY_DURATION + MED_DURATION):
                label = "Med"
            else:
                label = "Fast"
                
            return label, current_speed, False, 0
        else:
            seconds_remaining = int(TOTAL_CYCLE_TIME - cycle_position)
            return "BREAK", 0.0, True, seconds_remaining

    def update(self, events, dt):
        if self.game_over:
            for event in events:
                if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                    self.reset()
            return

        level_name, speed, is_break, break_secs = self.get_current_level_info()
        
        action = self.input_provider.poll(events)
        jumped, ducked = self.player.apply(action, is_break)
        if jumped:
            self.jump_count += 1
        if ducked:
            self.squat_count += 1
            
        speed_ratio = speed / SPEED_START if speed > 0 else 0.0
        self.player.update(dt, speed_ratio, is_break)

        self.time_elapsed += dt
        
        if is_break:
            return

        self.score += speed * dt * 25.0
        self.highest_occupied_z -= speed * dt * 0.15

        while self.highest_occupied_z < 1.8:
            self.spawn_batch()

        for obs in self.obstacles:
            obs.z -= speed * dt * 0.15
        for coin in self.coins:
            coin.z -= speed * dt * 0.15
            
        self.obstacles = [o for o in self.obstacles if o.z > 0.01]
        self.coins = [c for c in self.coins if c.z > 0.01]

        # REFINED: Human-friendly Dodge Timing Window Logic
        for obs in self.obstacles:
            if not obs.dodged and (0.03 <= obs.z <= 0.12):  # Expanded human interaction zone
                if int(obs.lane) == self.player.target_lane:
                    # Check if the correct dodge stance is active right now
                    is_dodging = (
                        (obs.kind == "ground" and self.player.jumping) or
                        (obs.kind == "overhead" and self.player.duck_timer > 0.0)
                    )
                    
                    if is_dodging:
                        obs.dodged = True  # Safely cleared the hurdle
                    elif obs.z <= 0.065:   # Hit critical close threshold without correct action
                        self.game_over = True

        for coin in self.coins:
            if not coin.collected and (0.03 <= coin.z <= 0.095):
                if int(coin.lane) == self.player.target_lane:
                    if not self.player.jumping:
                        coin.collected = True
                        self.coins_collected += 1  
                        self.score += 25

    def _draw_perspective_tracks(self):
        pygame.draw.rect(self.screen, (24, 25, 30), (0, 0, WIDTH, VANISH_Y))
        pygame.draw.rect(self.screen, (40, 42, 54), (0, VANISH_Y, WIDTH, HEIGHT - VANISH_Y))
        
        for i in range(LANE_COUNT + 1):
            lane_w_bottom = WIDTH * 1.3
            x_start = VANISH_X
            x_end = int((VANISH_X - lane_w_bottom / 2) + i * (lane_w_bottom / LANE_COUNT))
            pygame.draw.line(self.screen, LANE_LINE, (x_start, VANISH_Y), (x_end, HEIGHT), 3)

    def _draw_hud(self):
        panel = pygame.Surface((WIDTH, 92), pygame.SRCALPHA)
        pygame.draw.rect(panel, (0, 0, 0, 140), panel.get_rect())
        self.screen.blit(panel, (0, 0))

        score_surf = self.font.render(f"Score: {int(self.score)}", True, WHITE)
        self.screen.blit(score_surf, (12, 8))

        coin_surf = self.font.render(f"Coins: {self.coins_collected}", True, COIN_COLOR)
        self.screen.blit(coin_surf, (WIDTH - 140, 8))

        level_name, _, is_break, break_secs = self.get_current_level_info()
        if is_break:
            level_surf = self.font.render(f"Level: BREAK ({break_secs}s)", True, COIN_COLOR)
        else:
            level_surf = self.font.render(f"Level: {level_name}", True, WHITE)
        self.screen.blit(level_surf, (12, 38))

        time_surf = self.font.render(f"Time: {self.get_formatted_time()}", True, WHITE)
        self.screen.blit(time_surf, (WIDTH // 2 - time_surf.get_width() // 2, 8))

        stats_surf = self.small_font.render(
            f"Jumps: {self.jump_count}   Squats: {self.squat_count}   "
            f"Cal: {self.calories_burned():.1f}", True, DIM_WHITE
        )
        self.screen.blit(stats_surf, (12, 68))

    def _draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (0, 0, 0, 175), overlay.get_rect())
        self.screen.blit(overlay, (0, 0))

        over_surf = self.big_font.render("GAME OVER", True, WHITE)
        self.screen.blit(over_surf, over_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 190)))

        stats = [
            f"Score: {int(self.score)}",
            f"Coins Collected: {self.coins_collected}",  
            f"Duration: {self.get_formatted_time()}",  
            f"Jumps: {self.jump_count}",
            f"Squats: {self.squat_count}",
            f"Calories burned: {self.calories_burned():.1f} kcal",
        ]
        y = HEIGHT // 2 - 110
        for line in stats:
            surf = self.font.render(line, True, WHITE)
            self.screen.blit(surf, surf.get_rect(center=(WIDTH // 2, y)))
            y += 36

        hint_surf = self.font.render("Press R to restart", True, DIM_WHITE)
        self.screen.blit(hint_surf, hint_surf.get_rect(center=(WIDTH // 2, y + 14)))

    def draw(self):
        self._draw_perspective_tracks()

        entities = []
        for c in self.coins:
            if not c.collected:
                entities.append((c.z, c))
        for o in self.obstacles:
            entities.append((o.z, o))
            
        entities.sort(key=lambda item: item[0], reverse=True)

        for depth, ent in entities:
            if depth > 0.05:
                ent.draw(self.screen)

        self.player.draw(self.screen)

        for depth, ent in entities:
            if depth <= 0.05:
                ent.draw(self.screen)

        self._draw_hud()

        if self.game_over:
            self._draw_game_over()

        pygame.display.flip()

    def run(self):
        while True:
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

            dt = self.clock.tick(FPS) / 1000.0
            if dt > 0.1:
                dt = 0.1
                
            self.update(events, dt)
            self.draw()


def main():
    input_provider = KeyboardInput()
    Game(input_provider).run()


if __name__ == "__main__":
    main()